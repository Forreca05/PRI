"""Step 3: download the Wikipedia article (wikitext) for every race, driver and team.

Uses the MediaWiki Action API with prop=revisions, which accepts up to 50 titles
per request, so the ~2150 articles need only ~110 requests (Wikimedia heavily
rate-limits anonymous clients that send one request per page). Redirects are
followed, and the page id / revision id are stored so the exact version of
each article can be retrieved again.

Each article is cached as data/raw/wikipedia/<type>/<document id>.json, so
re-running the step only downloads what is missing.
"""
import os
import re
import sys
import time

import requests

from utils import (DRIVERS_STRUCTURED_PATH, RACES_STRUCTURED_PATH, RAW_WIKIPEDIA,
                   TEAMS_STRUCTURED_PATH, USER_AGENT, WIKIPEDIA_API, read_json,
                   safe_filename, write_json)

BATCH_SIZE = 20  # keeps each response well below the API's size limit
DISAMBIGUATION = re.compile(r'\{\{\s*(disambiguation|disambig|dab|hndis|human name disambiguation)\b', re.I)

session = requests.Session()
session.headers['User-Agent'] = USER_AGENT


def request(params: dict) -> dict:
    for attempt in range(8):
        response = session.get(WIKIPEDIA_API, params=params, timeout=60)
        if response.status_code == 429:
            # Wikimedia rate limit: wait as long as the server asks
            wait = int(response.headers.get('retry-after', 30)) + 1
            print(f'  rate limited, waiting {wait}s', file=sys.stderr)
            time.sleep(wait)
            continue
        if response.status_code == 200 and 'error' not in response.json():
            return response.json()
        time.sleep(2 ** attempt)
    raise RuntimeError(f'Request failed: {params["titles"]}')


def fetch_batch(titles: list) -> dict:
    """requested title -> article, resolving normalisation and redirects."""
    data = request({
        'action': 'query',
        'format': 'json',
        'formatversion': 2,
        'prop': 'revisions',
        'rvprop': 'ids|content',
        'rvslots': 'main',
        'redirects': 1,
        'titles': '|'.join(titles),
        'maxlag': 5,
    })['query']

    renamed = {r['from']: r['to'] for r in data.get('normalized', []) + data.get('redirects', [])}
    pages = {page['title']: page for page in data['pages']}

    articles = {}
    for title in titles:
        final = title
        while final in renamed:
            final = renamed[final]
        page = pages.get(final, {'missing': True})
        revision = (page.get('revisions') or [{}])[0]
        articles[title] = {
            'requested_title': title,
            'title': page.get('title'),
            'pageid': page.get('pageid'),
            'revid': revision.get('revid'),
            'missing': page.get('missing', False),
            'wikitext': revision.get('slots', {}).get('main', {}).get('content', ''),
        }
    return articles


def is_disambiguation(wikitext: str) -> bool:
    return bool(DISAMBIGUATION.search(wikitext)) or 'may refer to' in wikitext[:600]


def racing_entry(wikitext: str) -> str:
    """The title of the disambiguation entry about Formula One / motor racing, if any.

    Entries are ranked: a link whose title names Formula One or a racing driver
    ('Toyota Racing (Formula One team)'), then any link on a line mentioning
    Formula One ('...competed in the 2010 Formula One season'), then a line
    mentioning racing in general ('American race car builder')."""
    tiers = [
        lambda title, line: re.search(r'formula one|racing driver', title, re.I),
        lambda title, line: re.search(r'formula one', line, re.I),
        lambda title, line: re.search(r'racing|racer|race car|motor ?sport', line, re.I),
    ]
    entries = [(link.strip(), line) for line in wikitext.splitlines() if line.startswith('*')
               for link in re.findall(r'\[\[([^|\]#]+)', line)]
    for matches in tiers:
        for title, line in entries:
            if matches(title, line):
                return title
    return None


def resolve_disambiguations(records: list, kind: str):
    """Some Jolpica links point to disambiguation pages ('Tony Brooks may refer to...');
    follow the entry about the racing driver instead."""
    folder = os.path.join(RAW_WIKIPEDIA, kind)
    for record in records:
        path = os.path.join(folder, safe_filename(record['id']) + '.json')
        article = read_json(path)
        if not is_disambiguation(article['wikitext']):
            continue
        target = racing_entry(article['wikitext'])
        if target is None:
            print(f'  {record["id"]}: disambiguation page without a racing entry', file=sys.stderr)
            continue
        resolved = fetch_batch([target])[target]
        resolved['disambiguation_resolved_from'] = article['title']
        write_json(path, resolved)
        print(f'  {record["id"]}: "{article["title"]}" -> "{resolved["title"]}"', file=sys.stderr)
        time.sleep(1)


def collect(records: list, kind: str):
    folder = os.path.join(RAW_WIKIPEDIA, kind)
    os.makedirs(folder, exist_ok=True)

    path = lambda record: os.path.join(folder, safe_filename(record['id']) + '.json')
    pending = [record for record in records if not os.path.exists(path(record))]

    for start in range(0, len(pending), BATCH_SIZE):
        batch = pending[start:start + BATCH_SIZE]
        articles = fetch_batch(list({record['wikipedia_title'] for record in batch}))
        for record in batch:
            article = articles[record['wikipedia_title']]
            # A page without content but not missing was cut from the response; retry it next run
            if article['missing'] or article['wikitext']:
                write_json(path(record), article)
        print(f'  {kind}: {min(start + BATCH_SIZE, len(pending))}/{len(pending)}', file=sys.stderr)
        time.sleep(1)


if __name__ == '__main__':
    for path, kind in [(RACES_STRUCTURED_PATH, 'race'), (DRIVERS_STRUCTURED_PATH, 'driver'),
                       (TEAMS_STRUCTURED_PATH, 'team')]:
        records = read_json(path)
        collect(records, kind)
        resolve_disambiguations(records, kind)
    print('Wikipedia articles downloaded')
