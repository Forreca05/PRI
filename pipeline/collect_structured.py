"""Step 1: download the Jolpica F1 database dump (structured data source).

Jolpica (https://github.com/jolpica/jolpica-f1) is the community successor of
the Ergast API. The dump is a zip of CSV files, one per database table; only
the tables needed for the collection are kept.
"""
import io
import os
import zipfile
from datetime import date

import requests

from utils import JOLPICA_DUMP_URL, JOLPICA_TABLES, RAW_JOLPICA, write_json


def collect():
    os.makedirs(RAW_JOLPICA, exist_ok=True)

    response = requests.get(JOLPICA_DUMP_URL, timeout=120)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        for table in JOLPICA_TABLES:
            name = f'formula_one_{table}.csv'
            with open(os.path.join(RAW_JOLPICA, name), 'wb') as file:
                file.write(archive.read(name))

    # The dump URL always points to the latest dump, so record which one was used
    write_json(os.path.join(RAW_JOLPICA, 'metadata.json'), {
        'source': JOLPICA_DUMP_URL,
        'resolved_url': response.url.split('?')[0],
        'downloaded_on': date.today().isoformat(),
        'tables': JOLPICA_TABLES,
    })
    print(f'Saved {len(JOLPICA_TABLES)} tables to {RAW_JOLPICA}')


if __name__ == '__main__':
    collect()
