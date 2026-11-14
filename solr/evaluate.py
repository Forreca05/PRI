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
LABELS = {'schemaless': 'Schemaless', 'simple': 'Baseline', 'boosted': 'Boosted'}
COLORS = {'schemaless': '#8a8984', 'simple': '#2a78d6', 'boosted': '#eb6834'}
MARKERS = {'schemaless': '^', 'simple': 'o', 'boosted': 's'}
INK, MUTED, AXIS, GRID = '#0b0b0b', '#52514e', '#8a8984', '#e6e5e0'


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

    plt.rcParams.update({'font.size': 9, 'axes.edgecolor': AXIS, 'axes.labelcolor': INK,
                         'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.spines.top': False,
                         'axes.spines.right': False})

    def mean_curve(per_need):
        return [sum(c[i] for c in per_need) / len(per_need) for i in range(len(RECALL_LEVELS))]

    def draw_curves(ax, per_system):
        for system, per_need in per_system.items():
            ax.plot(RECALL_LEVELS, mean_curve(per_need), color=COLORS[system], linewidth=2,
                    marker=MARKERS[system], markersize=5, label=LABELS[system])
        ax.set_ylim(0, 1.05)
        ax.set_xlim(-0.02, 1.02)
        ax.grid(axis='y', color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)

    # Average curve over all needs
    fig, ax = plt.subplots(figsize=(4.2, 3.2))
    draw_curves(ax, curves)
    ax.set_xlabel('Recall')
    ax.set_ylabel('Interpolated precision')
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'results', 'precision_recall.png'), dpi=200)
    plt.close(fig)

    # Average curve by document type
    types = {need['id']: need['type'] for need in config['needs']}
    order = ['race', 'driver', 'team', 'circuit']
    fig, axes = plt.subplots(1, 4, figsize=(10, 2.6), sharey=True)
    for ax, doc_type in zip(axes, order):
        idx = [i for i, n in enumerate(needs) if types[n] == doc_type]
        draw_curves(ax, {s: [c[i] for i in idx] for s, c in curves.items()})
        ax.set_title(f'{doc_type.capitalize()}s ({", ".join(needs[i] for i in idx)})'
                     if len(idx) <= 3 else f'{doc_type.capitalize()}s (N1–N6)', fontsize=9, color=INK)
        ax.set_xlabel('Recall')
    axes[0].set_ylabel('Interpolated precision')
    axes[0].legend(frameon=False, loc='lower left')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'results', 'precision_recall_by_type.png'), dpi=200)
    plt.close(fig)

    # AP of each need
    fig, ax = plt.subplots(figsize=(4.2, 2.3))
    width = 0.8 / len(systems)
    for k, system in enumerate(systems):
        values = [next(r['AP'] for r in rows if r['system'] == system and r['need'] == n) for n in needs]
        offset = (k - (len(systems) - 1) / 2) * width
        ax.bar([i + offset for i in range(len(needs))], values, width, color=COLORS[system],
               label=LABELS[system])
    ax.set_xticks(range(len(needs)), needs, fontsize=8)
    ax.set_ylabel('Average precision')
    ax.set_ylim(0, 1)
    ax.grid(axis='y', color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=len(systems), loc='upper left', fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'results', 'ap_per_need.png'), dpi=200)
    plt.close(fig)
    print('-> results/metrics.csv, precision_recall.png, precision_recall_by_type.png, ap_per_need.png')
