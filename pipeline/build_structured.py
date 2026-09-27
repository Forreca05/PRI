"""Step 2: join the Jolpica tables into one structured record per race, driver and team.

Jolpica schema (only the parts used here):
    season 1-* round 1-* session (type 'R' = race) 1-* sessionentry
    round 1-* roundentry *-1 teamdriver *-1 driver / team
    sessionentry -> roundentry links a race result to a driver and a team

Jolpica has one team row per chassis-engine name ('Cooper', 'Cooper-Climax',
'Cooper-Maserati'...), several pointing to the same Wikipedia article. A team
document stands for one article, so those rows are grouped into one team.
"""
import html
import os
from datetime import date

import pandas as pd

from utils import (DRIVERS_STRUCTURED_PATH, RACES_STRUCTURED_PATH, RAW_JOLPICA,
                   TEAMS_STRUCTURED_PATH, wikipedia_title, write_json)

# sessionentry.status codes, inferred from the 'detail' column
STATUS = {0: 'finished', 1: 'lapped', 10: 'accident', 11: 'mechanical', 20: 'disqualified', 30: 'did_not_start'}
RETIRED = {'accident', 'mechanical'}


def load(table: str) -> pd.DataFrame:
    return pd.read_csv(os.path.join(RAW_JOLPICA, f'formula_one_{table}.csv'))


def none_if_nan(value):
    return None if pd.isna(value) else value


def teams() -> pd.DataFrame:
    """Jolpica team rows plus 'team_doc': the id of the team document (one per Wikipedia article),
    named after the row without an engine suffix ('McLaren' rather than 'McLaren-Ford'), else the oldest."""
    team = load('team')
    team['name'] = team['name'].map(html.unescape)          # 'Lotus-Pratt &amp; Whitney'
    team['with_engine'] = team['name'].str.contains('-')
    team = team.sort_values(['with_engine', 'id'])
    canonical = team.groupby('wikipedia')['reference'].first()
    team['team_doc'] = 'team_' + team['wikipedia'].map(canonical)
    return team


def race_results() -> pd.DataFrame:
    """One row per (race, driver) with everything needed for both document types."""
    session = load('session')
    races = session[session['type'] == 'R'][['id', 'round_id']].rename(columns={'id': 'session_id'})

    rounds = load('round').rename(columns={'id': 'round_id', 'name': 'race_name', 'wikipedia': 'race_wikipedia'})
    rounds = rounds[rounds['is_cancelled'] == 'f']
    season = load('season').rename(columns={'id': 'season_id'})[['season_id', 'year']]
    circuit = load('circuit').rename(columns={'id': 'circuit_id', 'name': 'circuit_name'})

    entry = load('sessionentry')
    round_entry = load('roundentry').rename(columns={'id': 'round_entry_id'})
    team_driver = load('teamdriver').rename(columns={'id': 'team_driver_id'})[['team_driver_id', 'driver_id', 'team_id']]
    driver = load('driver').rename(columns={'id': 'driver_id', 'reference': 'driver_ref'})
    driver['driver_name'] = driver['forename'] + ' ' + driver['surname']
    team = teams().rename(columns={'id': 'team_id', 'name': 'team_name'})[['team_id', 'team_name', 'team_doc']]

    df = (entry.merge(races, on='session_id')
          .merge(rounds[['round_id', 'race_name', 'number', 'date', 'season_id', 'circuit_id', 'race_wikipedia']], on='round_id')
          .merge(season, on='season_id')
          .merge(circuit[['circuit_id', 'circuit_name', 'locality', 'country']], on='circuit_id')
          .merge(round_entry[['round_entry_id', 'team_driver_id']], on='round_entry_id')
          .merge(team_driver, on='team_driver_id')
          .merge(driver[['driver_id', 'driver_ref', 'driver_name']], on='driver_id')
          .merge(team, on='team_id'))

    # Only races that already happened (the dump also contains the current season's calendar)
    df = df[df['date'] <= date.today().isoformat()]
    df['status_class'] = df['status'].map(STATUS)
    return df


def build_races(results: pd.DataFrame) -> list:
    races = []
    for (year, number), group in results.groupby(['year', 'number']):
        first = group.iloc[0]
        group = group.sort_values('position')
        started = group[group['status_class'] != 'did_not_start']
        retired = group[group['status_class'].isin(RETIRED)]

        races.append({
            'id': f'race_{year}_{int(number):02d}',
            'type': 'race',
            'title': f'{year} {first["race_name"]}',
            'season': int(year),
            'round': int(number),
            'date': first['date'],
            'circuit': first['circuit_name'],
            'locality': first['locality'],
            'country': first['country'],
            'winner': group[group['position'] == 1]['driver_name'].tolist(),
            'winning_team': group[group['position'] == 1]['team_name'].unique().tolist(),
            'pole_position': group[group['grid'] == 1]['driver_name'].tolist(),
            'podium': group[group['position'] <= 3]['driver_name'].tolist(),
            'fastest_lap': group[group['fastest_lap_rank'] == 1]['driver_name'].tolist(),
            'starters': int(len(started)),
            'finishers': int(group['status_class'].isin(['finished', 'lapped']).sum()),
            'retirements': [f'{r.driver_name}: {r.detail}' for r in retired.itertuples()],
            'retirement_reasons': sorted(retired['detail'].unique().tolist()),
            'drivers': group['driver_name'].tolist(),
            'driver_ids': [f'driver_{ref}' for ref in group['driver_ref']],
            'teams': group['team_name'].unique().tolist(),
            'team_ids': group['team_doc'].dropna().unique().tolist(),
            'wikipedia_url': first['race_wikipedia'],
            'wikipedia_title': wikipedia_title(first['race_wikipedia']),
        })
    return races


def season_champions(table: str, id_column: str) -> dict:
    """year -> id of the champion (driver or team), only for seasons already finished."""
    standings = load(table)
    rounds = load('round').merge(load('season').rename(columns={'id': 'season_id'}), on='season_id')
    last_race = rounds.groupby('year')['date'].max()
    finished = set(last_race[last_race <= date.today().isoformat()].index)

    champions = {}
    for year, group in standings.groupby('year'):
        if year not in finished:
            continue
        final = group[(group['round_number'] == group['round_number'].max())]
        final = final[final['session_number'] == final['session_number'].max()]
        champions[year] = final[final['position'] == 1][id_column].iloc[0]
    return champions


def build_drivers(results: pd.DataFrame) -> list:
    driver = load('driver')
    champions = season_champions('driverchampionship', 'driver_id')

    drivers = []
    for row in driver.itertuples():
        if pd.isna(row.wikipedia):
            continue
        races = results[results['driver_id'] == row.id]
        if races.empty:
            continue
        started = races[races['status_class'] != 'did_not_start']
        titles = sorted(int(year) for year, champion in champions.items() if champion == row.id)

        drivers.append({
            'id': f'driver_{row.reference}',
            'type': 'driver',
            'title': f'{row.forename} {row.surname}',
            'nationality': row.nationality,
            'date_of_birth': none_if_nan(row.date_of_birth),
            'code': none_if_nan(row.abbreviation),
            'permanent_number': None if pd.isna(row.permanent_car_number) else int(row.permanent_car_number),
            'first_season': int(races['year'].min()),
            'last_season': int(races['year'].max()),
            'seasons': sorted(int(y) for y in races['year'].unique()),
            'teams': races.sort_values('date')['team_name'].unique().tolist(),
            'team_ids': races.sort_values('date')['team_doc'].dropna().unique().tolist(),
            'race_entries': int(len(races)),
            'race_starts': int(len(started)),
            'wins': int((races['position'] == 1).sum()),
            'podiums': int((races['position'] <= 3).sum()),
            'pole_positions': int((races['grid'] == 1).sum()),
            'championships': len(titles),
            'championship_years': titles,
            'wikipedia_url': row.wikipedia,
            'wikipedia_title': wikipedia_title(row.wikipedia),
        })
    return drivers


def build_teams(results: pd.DataFrame) -> list:
    team = teams()
    champions = season_champions('teamchampionship', 'team_id')
    doc_of = dict(zip(team['id'], team['team_doc']))

    records = []
    for doc_id, rows in team.dropna(subset=['wikipedia']).groupby('team_doc', sort=False):
        races = results[results['team_doc'] == doc_id]
        if races.empty:
            continue
        first = rows.iloc[0]
        titles = sorted(int(year) for year, champion in champions.items() if doc_of.get(champion) == doc_id)
        per_race = races.groupby(['year', 'number'])

        records.append({
            'id': doc_id,
            'type': 'team',
            'title': first['name'],
            'names': rows['name'].tolist(),
            'nationality': first['nationality'],
            'first_season': int(races['year'].min()),
            'last_season': int(races['year'].max()),
            'seasons': sorted(int(y) for y in races['year'].unique()),
            'race_entries': int(per_race.ngroups),
            'wins': int(per_race['position'].min().eq(1).sum()),
            'podiums': int((races['position'] <= 3).sum()),
            'pole_positions': int(per_race['grid'].min().eq(1).sum()),
            'championships': len(titles),
            'championship_years': titles,
            'drivers': races.sort_values('date')['driver_name'].unique().tolist(),
            'driver_ids': [f'driver_{ref}' for ref in races.sort_values('date')['driver_ref'].unique()],
            'wikipedia_url': first['wikipedia'],
            'wikipedia_title': wikipedia_title(first['wikipedia']),
        })
    return records


if __name__ == '__main__':
    results = race_results()
    races = build_races(results)
    drivers = build_drivers(results)
    team_records = build_teams(results)
    write_json(RACES_STRUCTURED_PATH, races)
    write_json(DRIVERS_STRUCTURED_PATH, drivers)
    write_json(TEAMS_STRUCTURED_PATH, team_records)
    print(f'{len(races)} races, {len(drivers)} drivers, {len(team_records)} teams')
