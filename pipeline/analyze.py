"""Step 5: characterise the collection (numbers and plots for the M1 report).

Outputs, in data/analysis/:
    stats.json                 - document counts, word statistics, term metrics, quality report
    *.png                      - plots
"""
import os
import re
from collections import Counter

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from build_documents import TEXT_FIELDS
from utils import (ANALYSIS, CIRCUITS_STRUCTURED_PATH, DOCUMENTS_PATH, DRIVERS_STRUCTURED_PATH,
                   MIN_WORDS, RACES_STRUCTURED_PATH, RAW_WIKIPEDIA, REJECTED_PATH,
                   TEAMS_STRUCTURED_PATH, read_json, safe_filename, write_json)

KINDS = list(TEXT_FIELDS)
TOKEN = re.compile(r"[a-zà-ÿ]+(?:'[a-z]+)?")

plt.rcParams.update({'figure.dpi': 150, 'axes.spines.top': False, 'axes.spines.right': False})
COLORS = {'race': '#2a6fdb', 'driver': '#e8793a', 'team': '#1f9e74', 'circuit': '#9b59b6'}


def save(name: str):
    plt.tight_layout()
    plt.savefig(os.path.join(ANALYSIS, name))
    plt.close()


def tokens(text: str) -> list:
    return TOKEN.findall(text.lower())


def full_text(doc: dict) -> str:
    return '\n'.join(doc.get(field) or '' for field in TEXT_FIELDS[doc['type']])


def word_stats(series: pd.Series) -> dict:
    return {k: round(float(v), 1) for k, v in series.describe().items()}


def plot_word_counts(df: pd.DataFrame):
    fig, axes = plt.subplots(1, len(KINDS), figsize=(4.4 * len(KINDS), 3.5))
    for ax, kind in zip(axes, KINDS):
        values = df[df['type'] == kind]['word_count']
        ax.hist(values, bins=np.logspace(np.log10(MIN_WORDS), np.log10(values.max()), 30), color=COLORS[kind])
        ax.set_xscale('log')
        ticks = [t for t in [100, 300, 1000, 3000, 10000] if t <= values.max()]
        ax.set_xticks(ticks, [str(t) for t in ticks])
        ax.minorticks_off()
        ax.set_title(f'{kind.capitalize()} documents (n={len(values)})')
        ax.set_xlabel('words per document (log scale)')
        ax.set_ylabel('documents')
    save('word_count_distribution.png')


def plot_words_by_decade(races: pd.DataFrame):
    races = races.assign(decade=(races['season'] // 10 * 10).astype(int))
    median = races.groupby('decade')['word_count'].median()
    plt.figure(figsize=(7, 3.5))
    plt.bar(median.index.astype(str) + 's', median.values, color=COLORS['race'])
    plt.ylabel('median words per race')
    plt.title('Race article length by decade')
    save('race_words_by_decade.png')


def plot_field_coverage(docs: list) -> dict:
    coverage = {}
    for kind, fields in TEXT_FIELDS.items():
        subset = [d for d in docs if d['type'] == kind]
        coverage[kind] = {f: round(100 * sum(bool(d.get(f)) for d in subset) / len(subset), 1) for f in fields}

    fields = TEXT_FIELDS['race']
    plt.figure(figsize=(7, 3.5))
    plt.barh(fields[::-1], [coverage['race'][f] for f in fields[::-1]], color=COLORS['race'])
    plt.xlabel('% of race documents with the field')
    plt.xlim(0, 100)
    plt.title('Race text field coverage')
    save('race_field_coverage.png')
    return coverage


def plot_zipf(frequencies: Counter):
    counts = np.array(sorted(frequencies.values(), reverse=True))
    ranks = np.arange(1, len(counts) + 1)
    plt.figure(figsize=(5, 4))
    plt.loglog(ranks, counts, '.', markersize=2, color=COLORS['race'])
    plt.loglog(ranks, counts[0] / ranks, '--', color='gray', label='Zipf (1/rank)')
    plt.xlabel('term rank')
    plt.ylabel('term frequency')
    plt.title("Term frequency vs rank (Zipf's law)")
    plt.legend()
    save('zipf.png')


def plot_heaps(docs: list):
    vocabulary, seen, x, y = set(), 0, [], []
    for doc in docs:
        words = tokens(full_text(doc))
        vocabulary.update(words)
        seen += len(words)
        x.append(seen)
        y.append(len(vocabulary))
    plt.figure(figsize=(5, 4))
    plt.plot(x, y, color=COLORS['race'])
    plt.xlabel('tokens processed')
    plt.ylabel('vocabulary size')
    plt.title("Vocabulary growth (Heaps' law)")
    save('heaps.png')


def plot_top_terms(frequencies: dict):
    fig, axes = plt.subplots(1, len(KINDS), figsize=(4.7 * len(KINDS), 4.5))
    for ax, kind in zip(axes, KINDS):
        terms, counts = zip(*frequencies[kind].most_common(20))
        ax.barh(terms[::-1], counts[::-1], color=COLORS[kind])
        ax.set_title(f'Top terms in {kind} documents')
    save('top_terms.png')


def plot_bar(counter: Counter, title: str, name: str, color: str, n: int = 15):
    labels, values = zip(*counter.most_common(n))
    plt.figure(figsize=(7, 4))
    plt.barh(labels[::-1], values[::-1], color=color)
    plt.title(title)
    save(name)


def quality_report(docs: list) -> dict:
    rejected = read_json(REJECTED_PATH)
    structured = {'race': read_json(RACES_STRUCTURED_PATH), 'driver': read_json(DRIVERS_STRUCTURED_PATH),
                  'team': read_json(TEAMS_STRUCTURED_PATH), 'circuit': read_json(CIRCUITS_STRUCTURED_PATH)}
    disambiguations = []
    for kind, records in structured.items():
        for record in records:
            article = read_json(os.path.join(RAW_WIKIPEDIA, kind, safe_filename(record['id']) + '.json'))
            if 'disambiguation_resolved_from' in article:
                disambiguations.append(f'{article["disambiguation_resolved_from"]} -> {article["title"]}')

    reasons = Counter(r['reason'].split('_as_')[0] for r in rejected)
    return {
        'structured_records': {kind: len(records) for kind, records in structured.items()},
        'accepted_documents': dict(Counter(d['type'] for d in docs)),
        'rejected': dict(reasons),
        'rejected_by_type': dict(Counter(r['id'].split('_')[0] for r in rejected)),
        'min_words_threshold': MIN_WORDS,
        'disambiguation_links_fixed': disambiguations,
    }


def analyze():
    os.makedirs(ANALYSIS, exist_ok=True)
    docs = read_json(DOCUMENTS_PATH)
    df = pd.DataFrame([{k: d.get(k) for k in ['id', 'type', 'season', 'word_count']} for d in docs])
    races = df[df['type'] == 'race']

    frequencies = {kind: Counter() for kind in KINDS}
    all_terms, document_frequency = Counter(), Counter()
    for doc in docs:
        words = tokens(full_text(doc))
        all_terms.update(words)
        document_frequency.update(set(words))
        frequencies[doc['type']].update(w for w in words if w not in ENGLISH_STOP_WORDS and len(w) > 2)

    total_tokens = sum(all_terms.values())
    stats = {
        'documents': dict(Counter(df['type'])),
        'total_documents': len(docs),
        'words_per_document': {kind: word_stats(df[df['type'] == kind]['word_count']) for kind in KINDS},
        'total_tokens': total_tokens,
        'vocabulary_size': len(all_terms),
        'hapax_legomena': sum(1 for c in all_terms.values() if c == 1),
        'stopword_token_ratio': round(sum(all_terms[w] for w in ENGLISH_STOP_WORDS) / total_tokens, 3),
        'top_terms': {kind: frequencies[kind].most_common(30) for kind in frequencies},
        'terms_in_most_documents': [(t, round(c / len(docs), 3)) for t, c in document_frequency.most_common(30)
                                    if t not in ENGLISH_STOP_WORDS][:20],
        'race_seasons': [int(races['season'].min()), int(races['season'].max())],
        'field_coverage_percent': plot_field_coverage(docs),
        'quality': quality_report(docs),
    }

    retirement_reasons = Counter(r.split(': ', 1)[1] for d in docs if d['type'] == 'race' for r in d['retirements'])
    nationalities = Counter(d['nationality'] for d in docs if d['type'] == 'driver')
    countries = Counter(d['country'] for d in docs if d['type'] == 'race')
    stats['top_retirement_reasons'] = retirement_reasons.most_common(15)
    stats['top_driver_nationalities'] = nationalities.most_common(15)
    stats['top_race_countries'] = countries.most_common(15)

    plot_word_counts(df)
    plot_words_by_decade(races)
    plot_zipf(all_terms)
    plot_heaps(sorted(docs, key=lambda d: d['id']))
    plot_top_terms(frequencies)
    plot_bar(retirement_reasons, 'Most common retirement reasons', 'retirement_reasons.png', COLORS['race'])
    plot_bar(nationalities, 'Driver nationalities', 'driver_nationalities.png', COLORS['driver'])
    plot_bar(countries, 'Races per country', 'race_countries.png', COLORS['race'])

    write_json(os.path.join(ANALYSIS, 'stats.json'), stats)
    print(f'{len(docs)} documents, {total_tokens} tokens, vocabulary {len(all_terms)} -> {ANALYSIS}')


if __name__ == '__main__':
    analyze()
