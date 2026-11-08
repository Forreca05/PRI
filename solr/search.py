"""Runs every information need of queries.json on every system and prepares the judgements.

Outputs:
    results/<system>.json   - top 10 ids per need, in rank order
    qrels/<need>.csv        - one row per retrieved document; fill the 'relevant' column with 1 or 0.
                              Judgements already made are kept, new documents are appended.
"""
import csv
import json
import os
import urllib.parse
import urllib.request

SOLR = 'http://localhost:8983/solr/f1/select'
HERE = os.path.dirname(os.path.abspath(__file__))
TOP = 10
SNIPPET_FIELDS = 'summary,background,qualifying,race,post_race,other,biography,history,layout,events'


def search(params: dict, need: dict) -> list:
    params = dict(params)
    filter_type = params.pop('filter_type', True)  # the baseline searches the whole collection
    query = {**params, 'q': need['q'], 'fl': 'id,title,score',
             'rows': TOP, 'hl': 'true', 'hl.fl': SNIPPET_FIELDS, 'hl.snippets': 2,
             'hl.fragsize': 160, 'hl.method': 'unified'}
    if filter_type:
        query['fq'] = f'type:{need["type"]}'
    with urllib.request.urlopen(f'{SOLR}?{urllib.parse.urlencode(query)}') as response:
        data = json.load(response)
    docs = data['response']['docs']
    for doc in docs:
        fragments = [f for field in data['highlighting'].get(doc['id'], {}).values() for f in field]
        doc['snippet'] = ' '.join(' ... '.join(fragments[:2]).replace('<em>', '[').replace('</em>', ']').split())
    return docs


def update_qrels(need_id: str, docs: list):
    path = os.path.join(HERE, 'qrels', f'{need_id}.csv')
    rows = {}
    if os.path.exists(path):
        with open(path, encoding='utf-8') as file:
            rows = {row['id']: row for row in csv.DictReader(file)}
    for doc in docs:
        rows.setdefault(doc['id'], {'id': doc['id'], 'title': doc['title'], 'relevant': '',
                                    'snippet': doc['snippet']})
    with open(path, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=['id', 'title', 'relevant', 'snippet'])
        writer.writeheader()
        writer.writerows(rows.values())
    return sum(1 for row in rows.values() if row['relevant'] == '')


if __name__ == '__main__':
    with open(os.path.join(HERE, 'queries.json'), encoding='utf-8') as file:
        config = json.load(file)
    os.makedirs(os.path.join(HERE, 'results'), exist_ok=True)
    os.makedirs(os.path.join(HERE, 'qrels'), exist_ok=True)

    retrieved = {need['id']: [] for need in config['needs']}
    for system, params in config['systems'].items():
        results = {}
        for need in config['needs']:
            docs = search(params, need)
            results[need['id']] = [doc['id'] for doc in docs]
            retrieved[need['id']] += docs
        with open(os.path.join(HERE, 'results', f'{system}.json'), 'w', encoding='utf-8') as file:
            json.dump(results, file, indent=2)
        print(f'{system}: {len(results)} needs -> results/{system}.json')

    for need in config['needs']:
        missing = update_qrels(need['id'], retrieved[need['id']])
        print(f'{need["id"]:4} {need["need"]:50} {missing} to judge in qrels/{need["id"]}.csv')
