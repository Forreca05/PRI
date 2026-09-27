"""Step 4: merge structured records with Wikipedia text into the final collection.

The wikitext of each article is converted to plain text (see wikitext.py) and
split into sections. Sections with no prose (references, classification tables,
standings...) are dropped together with their subsections, and the remaining
top-level sections are mapped to fixed fields so that every document of the
same type has the same schema:

    race   -> summary, background, qualifying, race, post_race, other
    driver -> summary, biography
    team   -> summary, history

Documents whose article is missing, is shared with another record, or has fewer
than MIN_WORDS words are rejected (and saved with the reason, for the report).
"""
import os
import re
import unicodedata
from collections import Counter

from utils import (DOCUMENTS_PATH, DRIVERS_STRUCTURED_PATH, MIN_WORDS,
                   RACES_STRUCTURED_PATH, RAW_WIKIPEDIA, REJECTED_PATH,
                   TEAMS_STRUCTURED_PATH, read_json, safe_filename, write_json)
from wikitext import HEADING, wikitext_to_text

TEXT_FIELDS = {
    'race': ['summary', 'background', 'qualifying', 'race', 'post_race', 'other'],
    'driver': ['summary', 'biography'],
    'team': ['summary', 'history'],
}

# Sections that hold no useful prose once tables are stripped
DROP = ['reference', 'note', 'external link', 'further reading', 'see also', 'bibliograph',
        'source', 'footnote', 'classification', 'standings', 'starting grid', 'box score',
        'shared drive', 'supporting race', 'record', 'career summary', 'career result',
        'complete formula one', 'statistics', 'results']

# Race sections, checked in order: the first matching keyword wins
RACE_FIELDS = [
    ('post_race', ['post-race', 'post race', 'after the race', 'aftermath', 'reaction', 'controvers', 'consequence', 'legacy']),
    ('background', ['background', 'entr', 'preview', 'pre-race', 'permutation', 'build-up', 'circuit']),
    ('qualifying', ['qualif', 'practice', 'time trial']),
    ('race', ['race', 'report', 'sprint', 'summary']),
]


def clean(text: str) -> str:
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'[ \t ​]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()


def split_sections(text: str) -> tuple:
    """Return (lead, [(level, title, body), ...]) for every heading level."""
    parts = HEADING.split(text)
    sections = [(len(level), title, body) for level, title, body in zip(parts[1::3], parts[2::3], parts[3::3])]
    return parts[0], sections


def is_dropped(title: str) -> bool:
    title = title.lower()
    return any(key in title for key in DROP)


def race_field(title: str) -> str:
    title = title.lower()
    for field, keys in RACE_FIELDS:
        if any(key in title for key in keys):
            return field
    return 'other'


def text_fields(text: str, kind: str, section_log: Counter) -> dict:
    lead, sections = split_sections(text)
    fields = {'summary': [clean(lead)]}
    field, dropped_level = None, None
    moved_field, moved_level = None, None

    for level, title, body in sections:
        if dropped_level is not None and level > dropped_level:
            continue                                  # subsection of a dropped section
        dropped_level = None
        if is_dropped(title):
            dropped_level = level
            section_log[(kind, 'dropped', title)] += level == 2
            continue

        if moved_level is not None and level <= moved_level:
            moved_field, moved_level = None, None
        if level == 2:
            field = race_field(title) if kind == 'race' else TEXT_FIELDS[kind][1]
            section_log[(kind, field, title)] += 1
        elif field is None:
            continue
        elif kind == 'race' and moved_field is None and race_field(title) == 'post_race':
            # 'Post-race' is often a subsection of 'Race'; it belongs to post_race with its children
            moved_field, moved_level = 'post_race', level

        body = clean(body)
        if body:
            # Subsection titles are kept as a line of text ("Pit stops and virtual safety car.")
            target = moved_field or field
            fields.setdefault(target, []).append(body if level == 2 else f'{title}.\n{body}')

    return {name: '\n\n'.join(fields.get(name, [])) for name in TEXT_FIELDS[kind]}


def build(records: list, kind: str, section_log: Counter) -> tuple:
    accepted, rejected, seen_pages = [], [], {}

    for record in records:
        article = read_json(os.path.join(RAW_WIKIPEDIA, kind, safe_filename(record['id']) + '.json'))

        if article['missing'] or not article['wikitext']:
            rejected.append({'id': record['id'], 'reason': 'missing_article'})
            continue
        if article['pageid'] in seen_pages:
            rejected.append({'id': record['id'], 'reason': f'same_article_as_{seen_pages[article["pageid"]]}'})
            continue
        seen_pages[article['pageid']] = record['id']

        text = text_fields(wikitext_to_text(article['wikitext']), kind, section_log)
        word_count = sum(len(value.split()) for value in text.values())
        if word_count < MIN_WORDS:
            rejected.append({'id': record['id'], 'reason': 'too_short', 'word_count': word_count})
            continue

        accepted.append({
            **record,
            **text,
            'word_count': word_count,
            'wikipedia_title': article['title'],
            'wikipedia_pageid': article['pageid'],
            'wikipedia_revid': article['revid'],
        })
    return accepted, rejected


def link(races: list, drivers: list, teams: list):
    """Keep only links to documents present in the collection, and add the
    reverse links from drivers and teams to the races they took part in."""
    present = {doc['id'] for doc in races + drivers + teams}
    for doc in races + drivers + teams:
        for key in ['driver_ids', 'team_ids']:
            if key in doc:
                doc[key] = [i for i in doc[key] if i in present]

    races_of = {doc['id']: [] for doc in drivers + teams}
    for race in races:
        for other in race['driver_ids'] + race['team_ids']:
            races_of[other].append(race['id'])
    for doc in drivers + teams:
        doc['race_ids'] = races_of[doc['id']]


if __name__ == '__main__':
    section_log = Counter()
    documents, rejected = {}, []
    for kind, path in [('race', RACES_STRUCTURED_PATH), ('driver', DRIVERS_STRUCTURED_PATH),
                       ('team', TEAMS_STRUCTURED_PATH)]:
        documents[kind], rejected_kind = build(read_json(path), kind, section_log)
        rejected += rejected_kind
        print(f'{kind + "s:":8} {len(documents[kind])} accepted, {len(rejected_kind)} rejected')
    link(documents['race'], documents['driver'], documents['team'])

    collection = documents['race'] + documents['driver'] + documents['team']
    write_json(DOCUMENTS_PATH, collection)
    write_json(REJECTED_PATH, rejected)
    write_json(os.path.join(os.path.dirname(REJECTED_PATH), 'section_mapping.json'),
               [{'type': k, 'field': f, 'section': s, 'count': n} for (k, f, s), n in section_log.most_common()])
    print(f'total:   {len(collection)} documents -> {DOCUMENTS_PATH}')
