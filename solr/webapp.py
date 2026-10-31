"""Local web interface for the F1 Solr collection."""
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(HERE, 'web')
SOLR_URL = os.environ.get('SOLR_URL', 'http://localhost:8983/solr/f1/select')
with open(os.path.join(HERE, 'queries.json'), encoding='utf-8') as file:
    SYSTEMS = json.load(file)['systems']


class SearchHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        if urlsplit(self.path).path != '/api/search':
            return super().do_GET()

        params = parse_qs(urlsplit(self.path).query)
        query = params.get('q', [''])[0].strip()
        doc_type = params.get('type', ['all'])[0]
        system = params.get('system', ['boosted'])[0]
        try:
            page = int(params.get('page', ['1'])[0])
            if not query:
                raise ValueError('Enter a search term.')
            if doc_type not in {'all', 'race', 'driver', 'team', 'circuit'}:
                raise ValueError('Choose a valid document type.')
            if system not in SYSTEMS:
                raise ValueError('Choose a valid ranking system.')
            if page < 1:
                raise ValueError('Page must be greater than zero.')
        except ValueError as error:
            return self.send_json(400, {'error': str(error)})

        rows = 10
        query_params = {
            **SYSTEMS[system],
            'q': query,
            'start': (page - 1) * rows,
            'rows': rows,
            'fl': 'id,title,type,score,summary,season,date,country,nationality,wins,championships,'
                  'word_count,wikipedia_url,circuit',
            'sort': 'score desc',
            'wt': 'json',
        }
        if doc_type != 'all':
            query_params['fq'] = f'type:{doc_type}'

        try:
            with urlopen(f'{SOLR_URL}?{urlencode(query_params)}', timeout=10) as response:
                data = json.load(response)
        except HTTPError as error:
            message = error.read().decode('utf-8', errors='replace')
            return self.send_json(502, {'error': f'Solr rejected the search: {message[:500]}'})
        except (URLError, TimeoutError) as error:
            return self.send_json(
                503, {'error': f'Cannot reach Solr at {SOLR_URL}: {error}'})
        except (json.JSONDecodeError, KeyError) as error:
            return self.send_json(502, {'error': f'Unexpected response from Solr: {error}'})

        try:
            results = data['response']
            total = results['numFound']
            documents = results['docs']
        except (KeyError, TypeError) as error:
            return self.send_json(502, {'error': f'Unexpected response from Solr: {error}'})
        self.send_json(200, {
            'total': total,
            'page': page,
            'pages': (total + rows - 1) // rows,
            'results': documents,
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
