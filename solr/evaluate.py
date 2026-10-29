"""Evaluates every system in results/ against the judgements in qrels/.

Relevant documents are those judged 1 among everything retrieved by any system (pooling),
so recall is relative to that pool.

Outputs:
    results/metrics.csv          - P@10 and AP per need and system, MAP per system
    results/precision_recall.png - interpolated precision-recall curve of each system
"""
import csv
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = 10
RECALL_LEVELS = [i / 10 for i in range(11)]


def read_qrels() -> dict:
    qrels = {}
    for name in sorted(os.listdir(os.path.join(HERE, 'qrels'))):
        with open(os.path.join(HERE, 'qrels', name), encoding='utf-8') as file:
            qrels[name.removesuffix('.csv')] = {row['id']: row['relevant'].strip() for row in csv.DictReader(file)}
    return qrels


def average_precision(ranking: list, relevant: set) -> float:
    hits, total = 0, 0.0
    for rank, doc in enumerate(ranking, 1):
        if doc in relevant:
            hits += 1
            total += hits / rank
    return total / len(relevant) if relevant else 0.0


def interpolated_curve(ranking: list, relevant: set) -> list:
    points, hits = [], 0
    for rank, doc in enumerate(ranking, 1):
        hits += doc in relevant
        points.append((hits / len(relevant) if relevant else 0.0, hits / rank))
    return [max([p for r, p in points if r >= level], default=0.0) for level in RECALL_LEVELS]


if __name__ == '__main__':
    with open(os.path.join(HERE, 'queries.json'), encoding='utf-8') as file:
        config = json.load(file)
    needs = [need['id'] for need in config['needs']]
    systems = list(config['systems'])
    qrels = read_qrels()

    unjudged = {n: [d for d, r in qrels.get(n, {}).items() if r not in ('0', '1')] for n in needs}
    if any(unjudged.values()):
        print('Warning: unjudged documents count as not relevant:',
              ', '.join(f'{n} ({len(d)})' for n, d in unjudged.items() if d))

    rows, curves = [], {}
    for system in systems:
        with open(os.path.join(HERE, 'results', f'{system}.json'), encoding='utf-8') as file:
            results = json.load(file)
        aps, curves[system] = [], []
        for need in needs:
            relevant = {d for d, r in qrels.get(need, {}).items() if r == '1'}
            ranking = results[need][:TOP]
            ap = average_precision(ranking, relevant)
            aps.append(ap)
            curves[system].append(interpolated_curve(ranking, relevant))
            rows.append({'system': system, 'need': need, 'P@10': sum(d in relevant for d in ranking) / TOP,
                         'AP': ap})
        rows.append({'system': system, 'need': 'MAP', 'P@10': '', 'AP': sum(aps) / len(aps)})

    with open(os.path.join(HERE, 'results', 'metrics.csv'), 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=['system', 'need', 'P@10', 'AP'])
        writer.writeheader()
        writer.writerows(rows)

    print(f'{"need":6}' + ''.join(f'{s + " P@10":>16}{s + " AP":>14}' for s in systems))
    for need in needs + ['MAP']:
        line = f'{need:6}'
        for system in systems:
            row = next(r for r in rows if r['system'] == system and r['need'] == need)
            p10 = f'{row["P@10"]:.2f}' if row['P@10'] != '' else ''
            line += f'{p10:>16}{row["AP"]:>14.3f}'
        print(line)

    plt.figure(figsize=(5, 4))
    for system, per_need in curves.items():
        mean = [sum(c[i] for c in per_need) / len(per_need) for i in range(len(RECALL_LEVELS))]
        plt.plot(RECALL_LEVELS, mean, marker='o', label=system)
    plt.xlabel('Recall')
    plt.ylabel('Interpolated precision')
    plt.ylim(0, 1.05)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(HERE, 'results', 'precision_recall.png'))
    print('-> results/metrics.csv, results/precision_recall.png')
