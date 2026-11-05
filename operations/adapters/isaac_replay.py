"""Export persisted SimPy tracks for Kit, without importing USD or Kit."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3


def export_replay(database, output, run_id=None):
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        runs = conn.execute('SELECT * FROM runs WHERE run_id=? OR ? IS NULL', (run_id, run_id)).fetchall()
        if len(runs) != 1:
            raise ValueError('Select exactly one run with --run-id.')
        run = runs[0]
        cfg = json.loads(run['effective_config_json'])
        space = cfg.get('space')
        if not space:
            raise ValueError('A spatial SimPy run is required; enable flexible movement.')
        workers = {w['worker_id']: {'id': w['worker_id'], 'label': w['display_code'],
            'role': w.get('primary_role'), 'initial': space['cells'][space['initial'][w['worker_id']]],
            'moves': []} for w in cfg['workers']}
        links = {}
        for row in conn.execute('SELECT eo.* FROM event_objects eo JOIN events e USING(recording_cursor) WHERE e.run_id=?', (run['run_id'],)):
            links.setdefault(row['recording_cursor'], {}).setdefault(row['object_type'], row['object_id'])
        events = []
        names = {row['product_id']: row['name'] for row in conn.execute('SELECT product_id,name FROM products')}
        customers = {}
        for row in conn.execute('SELECT * FROM events WHERE run_id=? ORDER BY sim_time_s,recording_cursor', (run['run_id'],)):
            o = links.get(row['recording_cursor'], {})
            t, a, life = row['sim_time_s'], row['activity'], row['lifecycle']
            w, v = o.get('worker'), o.get('visit')
            if a == 'visit_arrival':
                customers[v] = f'C{len(customers)+1}'
            if a == 'space_move' and life == 'start':
                p = json.loads(row['payload_json'])
                workers[w]['moves'].append([t, t+p['duration_s'], p['from_xy_m'], p['to_xy_m']])
            elif a in {'visit_arrival','service_assigned','service_completed','visit_abandoned','server_released'} or (
                w and life in {'request','start','complete'} and a not in {'space_wait','counter_access','ordering_queue','space_move'}):
                events.append({'t':t,'activity':a,'life':life,'worker':w,'customer':customers.get(v),
                               'product':names.get(o.get('product')), 'key':row['activity_id']})
        payload = {'schema':'guadalajara_simpy_replay_v1','run_id':run['run_id'],
                   'evidence':'synthetic','duration_s':run['analysis_cutoff_s'],
                   'floor_z_m':cfg.get('replay_floor_z_m',-.09),
                   'geometry':cfg.get('geometry_snapshot_status'),
                   'workers':list(workers.values()), 'events':events}
    Path(output).write_text(json.dumps(payload, ensure_ascii=False, separators=(',',':')), encoding='utf-8')
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database')
    parser.add_argument('output')
    parser.add_argument('--run-id')
    args = parser.parse_args()
    result = export_replay(args.database, args.output, args.run_id)
    print(f"{len(result['workers'])} workers exported to {args.output}")
