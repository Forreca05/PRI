import json
import os
from urllib.parse import unquote, urlparse

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DATA = os.path.join(ROOT, 'data')

RAW_JOLPICA = os.path.join(DATA, 'raw', 'jolpica')
RAW_WIKIPEDIA = os.path.join(DATA, 'raw', 'wikipedia')
INTERIM = os.path.join(DATA, 'interim')
PROCESSED = os.path.join(DATA, 'processed')
ANALYSIS = os.path.join(DATA, 'analysis')

RACES_STRUCTURED_PATH = os.path.join(INTERIM, 'races_structured.json')
DRIVERS_STRUCTURED_PATH = os.path.join(INTERIM, 'drivers_structured.json')
TEAMS_STRUCTURED_PATH = os.path.join(INTERIM, 'teams_structured.json')
CIRCUITS_STRUCTURED_PATH = os.path.join(INTERIM, 'circuits_structured.json')
DOCUMENTS_PATH = os.path.join(PROCESSED, 'documents.json')
DOCUMENTS_CSV_PATH = os.path.join(PROCESSED, 'documents.csv')
REJECTED_PATH = os.path.join(INTERIM, 'rejected_documents.json')

# Documents whose Wikipedia text has fewer words than this are discarded
MIN_WORDS = 100

JOLPICA_DUMP_URL = 'https://api.jolpi.ca/data/dumps/download/delayed/?dump_type=csv'
JOLPICA_TABLES = [
    'circuit', 'driver', 'driverchampionship', 'round', 'roundentry',
    'season', 'session', 'sessionentry', 'team', 'teamchampionship', 'teamdriver',
]

WIKIPEDIA_API = 'https://en.wikipedia.org/w/api.php'
USER_AGENT = 'PRI-F1-Search/1.0 (FEUP M.EIC academic project; Information Processing and Retrieval)'


def read_json(path: str):
    with open(path, encoding='utf-8') as file:
        return json.load(file)


def write_json(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=2, ensure_ascii=False)


def wikipedia_title(url: str) -> str:
    """'http://en.wikipedia.org/wiki/Kimi_R%C3%A4ikk%C3%B6nen' -> 'Kimi Räikkönen'"""
    path = urlparse(url).path
    return unquote(path.split('/wiki/', 1)[1]).replace('_', ' ')


def safe_filename(title: str) -> str:
    return ''.join(c if c.isalnum() or c in '-_.' else '_' for c in title)
