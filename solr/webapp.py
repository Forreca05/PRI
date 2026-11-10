"""Local web interface for the F1 Solr collection."""
import difflib
import json
import os
import re
from collections import Counter
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(HERE, 'web')
SOLR_URL = os.environ.get('SOLR_URL', 'http://localhost:8983/solr/f1/select')
with open(os.path.join(HERE, 'queries.json'), encoding='utf-8') as file:
    CONFIG = json.load(file)
SYSTEMS = CONFIG['systems']
NEEDS = [{'id': n['id'], 'need': n['need'], 'type': n['type'], 'q': n['q']} for n in CONFIG['needs']]

TYPES = ('race', 'driver', 'team', 'circuit')
ROWS = 10
TEXT_FIELDS = 'summary,background,qualifying,race,post_race,other,biography,history,layout,events'
FIELDS = ('id,title,type,score,summary,season,date,circuit,country,locality,nationality,winner,'
          'winning_team,wins,championships,first_season,last_season,word_count,wikipedia_url')
# Private-use characters mark highlighted words; the browser turns them into <mark> safely.
HL_PRE, HL_POST = '', ''
# Name fields keep words whole (no stemming), so they are where misspelled names are matched.
NAME_FIELDS = 'title,drivers,teams,winner,podium,circuit,locality,names,grands_prix'


def season_filter(start, end):
    """Races have one season; drivers and teams have the list of seasons they took part in."""
    if start is None and end is None:
        return None
    span = f'[{start if start is not None else "*"} TO {end if end is not None else "*"}]'
    return f'season:{span} OR seasons:{span}'


def solr(params):
    with urlopen(f'{SOLR_URL}?{urlencode(params)}', timeout=10) as response:
        return json.load(response)


TOKEN = re.compile(r'"[^"]*"|\S+')
WORD = re.compile(r"^[^\W\d_][\w'-]{3,}$")  # plain words of 4+ letters, no operators or syntax


def unknown_words(query):
    """Words of the query that appear in no document, found with one request (a count per word)."""
    words = sorted({t for t in TOKEN.findall(query)
                    if WORD.match(t) and t not in ('AND', 'OR', 'NOT')})
    if not words:
        return []
    params = [('q', '*:*'), ('rows', 0), ('facet', 'true'), ('wt', 'json')]
    for i, word in enumerate(words):
        params += [('facet.query', f'{{!edismax qf=all_text v=$w{i}}}'), (f'w{i}', word)]
    counts = list(solr(params)['facet_counts']['facet_queries'].values())
    return [word for word, count in zip(words, counts) if count == 0]


def fuzzy_query(query, words):
    """Allows one typo in short words and two in longer ones, only for the unknown words."""
    return ''.join(f'{t}~{1 if len(t) <= 5 else 2}' if t in words else t
                   for t in re.split(r'("[^"]*"|\s+)', query))


def correct(query, words):
    """Replaces each unknown word by the most similar word found in the collection.

    A fuzzy search over the name fields and the text lists the words within one or two letters
    of each unknown word, and the
    closest one wins (ties go to the most frequent), so "hmlton" becomes "hamilton" and not
    "chilton". The corrected query is then searched normally, keeping the usual ranking.
    """
    data = solr([('q', fuzzy_query(query, words)), ('defType', 'edismax'),
                 ('qf', f'{NAME_FIELDS.replace(",", " ")} all_text'),
                 ('rows', 50), ('fl', 'id'), ('wt', 'json'), ('hl', 'true'), ('hl.method', 'unified'),
                 ('hl.fl', f'{NAME_FIELDS},{TEXT_FIELDS}'), ('hl.snippets', 5), ('hl.requireFieldMatch', 'false'),
                 ('hl.tag.pre', HL_PRE), ('hl.tag.post', HL_POST)])
    text = ' '.join(f for doc in data.get('highlighting', {}).values() for field in doc.values() for f in field)
    marks = re.findall(f'{HL_PRE}(.*?){HL_POST}', text)
    counts = Counter(re.sub(r"['’]s$", '', m.lower()) for m in marks)
    fixed = query
    for word in words:
        # Similarity rounded to 0.1, so that a common spelling beats a rare near-identical typo.
        options = [(round(difflib.SequenceMatcher(None, word.lower(), m).ratio(), 1), n, m)
                   for m, n in counts.items() if ' ' not in m]
        options = [o for o in options if o[0] >= 0.6]
        if options:
            fixed = re.sub(rf'(?<![\w"]){re.escape(word)}(?![\w~])', max(options)[2], fixed)
    return fixed if fixed != query else None


def parse_year(value):
    if not value:
        return None
    year = int(value)
    if not 1950 <= year <= 2100:
        raise ValueError('Seasons must be between 1950 and 2100.')
    return year


class SearchHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        if '/api/' in self.path:
            super().log_message(format, *args)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/needs':
            return self.send_json(200, {'needs': NEEDS})
        if path != '/api/search':
            return super().do_GET()

        params = parse_qs(urlsplit(self.path).query)
        get = lambda name, default='': params.get(name, [default])[0].strip()
        query, doc_type, system = get('q'), get('type', 'all'), get('system', 'boosted')
        try:
            page = int(get('page', '1'))
            start, end = parse_year(get('from')), parse_year(get('to'))
            if not query:
                raise ValueError('Enter a search term.')
            if doc_type not in ('all',) + TYPES:
                raise ValueError('Choose a valid document type.')
            if system not in SYSTEMS:
                raise ValueError('Choose a valid ranking system.')
            if page < 1:
                raise ValueError('Page must be greater than zero.')
            if start and end and start > end:
                raise ValueError('The first season must not be after the last one.')
        except ValueError as error:
            message = str(error) if 'invalid literal' not in str(error) else 'Use numbers for page and seasons.'
            return self.send_json(400, {'error': message})

        settings = {k: v for k, v in SYSTEMS[system].items() if k != 'filter_type'}
        filters = []
        if doc_type != 'all':
            filters.append(f'{{!tag=type}}type:{doc_type}')
        seasons = season_filter(start, end)
        if seasons:
            filters.append(seasons)
        corrected = None
        try:
            typos = unknown_words(query) if get('exact') != '1' else []
            corrected = correct(query, typos) if typos else None
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError):
            pass  # the main search below reports the error
        query_params = [
            *settings.items(),
            ('q', corrected or query),
            ('start', (page - 1) * ROWS),
            ('rows', ROWS),
            ('fl', FIELDS),
            ('sort', 'score desc'),
            ('wt', 'json'),
            ('facet', 'true'),
            ('facet.field', '{!ex=type}type'),
            ('hl', 'true'),
            ('hl.method', 'unified'),
            ('hl.fl', TEXT_FIELDS),
            ('hl.snippets', 2),
            ('hl.fragsize', 180),
            ('hl.fragsizeIsMinimum', 'false'),
            ('hl.tag.pre', HL_PRE),
            ('hl.tag.post', HL_POST),
            *[('fq', f) for f in filters],
        ]

        try:
            data = solr(query_params)
            results = data['response']
            counts = data['facet_counts']['facet_fields']['type']
        except HTTPError as error:
            message = error.read().decode('utf-8', errors='replace')
            return self.send_json(502, {'error': f'Solr rejected the search: {message[:500]}'})
        except (URLError, TimeoutError) as error:
            return self.send_json(503, {'error': f'Cannot reach Solr at {SOLR_URL}: {error}'})
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            return self.send_json(502, {'error': f'Unexpected response from Solr: {error}'})

        highlighting = data.get('highlighting', {})
        for doc in results['docs']:
            fragments = [f for field in highlighting.get(doc['id'], {}).values() for f in field]
            doc['snippet'] = ' … '.join(' '.join(f.split()) for f in fragments[:2])

        total = results['numFound']
        self.send_json(200, {
            'corrected': corrected,
            'total': total,
            'page': page,
            'pages': (total + ROWS - 1) // ROWS,
            'types': dict(zip(counts[::2], counts[1::2])),
            'results': results['docs'],
            'marks': [HL_PRE, HL_POST],
        })

    def send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8000'))
    server = ThreadingHTTPServer(('127.0.0.1', port), SearchHandler)
    print(f'F1 Search is running at http://localhost:{port} (Ctrl+C to stop)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopping F1 Search.')
        server.server_close()
