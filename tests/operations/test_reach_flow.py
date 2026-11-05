"""Behavior tests for concurrency, opportunistic picking and reachable endpoints."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from operations.engine.simulation import run_scenario
from operations.experiments import prepare_experiment, run_experiment


def events(path):
    with closing(sqlite3.connect(path)) as c:
        c.row_factory=sqlite3.Row
        links={}
        for r in c.execute('select * from event_objects'):
            links.setdefault(r['recording_cursor'],{})[r['object_type']]=r['object_id']
        return [{**dict(r),'objects':links.get(r['recording_cursor'],{}),
                 'payload':json.loads(r['payload_json'])}
                for r in c.execute('select * from events order by recording_cursor')]


def controlled(root, server_count, baskets):
    path,_=prepare_experiment({'servers':server_count,'orders':server_count,'minutes':5,
        'space_enabled':False,'product_overrides':{'product:morcilla':20,'product:papa_criolla':2}},root)
    cfg=json.loads(path.read_text())
    # Preserve the complete workflow but isolate contention from arrival/random timing.
    template=cfg['visits'][0]
    cfg['visits']=[]
    for i,basket in enumerate(baskets):
        visit=json.loads(json.dumps(template))
        visit.update(visit_id=f'visit:{i}',arrival_s=0)
        visit['order'].update(order_id=f'order:{i}',fulfillment_mode='dine_in',lines=[
            {'sale_option_id':f'sale:{p}:portion','product_id':f'product:{p}',
             'resource_id':r,'quantity':1,'unit':'portion'} for p,r in basket])
        cfg['visits'].append(visit)
    for key in ['order_taking_s','deposit_s','travel_s','seasoning_s','basket_splitting_s','handover_s']:
        cfg['durations'][key]=0
    cfg['durations']['cutting_per_portion_s']=0
    path.write_text(json.dumps(cfg))
    run_scenario(path,root/'events.sqlite3',seed=42)
    return events(root/'events.sqlite3')


class ReachFlowTests(unittest.TestCase):
    def test_third_morcilla_worker_picks_potato_while_two_are_busy(self):
        mor=('morcilla','resource:morcilla_access_2p')
        potato=('papa_criolla','resource:papa_criolla_access_2p')
        with tempfile.TemporaryDirectory() as tmp:
            rows=controlled(Path(tmp),3,[[mor],[mor],[mor,potato]])
        starts=[r for r in rows if r['activity']=='product_pick' and r['lifecycle']=='start']
        mor_starts=[r['sim_time_s'] for r in starts if r['objects']['product']=='product:morcilla']
        self.assertEqual(mor_starts,[0,0,20])
        potato_start=next(r for r in starts if r['objects']['product']=='product:papa_criolla')
        self.assertEqual(potato_start['sim_time_s'],0)
        worker=potato_start['objects']['worker']
        picked=[r['objects']['product'] for r in starts if r['objects']['worker']==worker]
        self.assertEqual(picked,['product:papa_criolla','product:morcilla'])
        wait=[r for r in rows if r['activity']=='ingredient_wait' and r['objects']['worker']==worker]
        self.assertEqual([(r['lifecycle'],r['sim_time_s']) for r in wait],[('start',2),('complete',20)])
        self.assertFalse(any(r['activity']=='selection_travel' for r in rows))
        self.assertEqual(sum(r['activity']=='service_completed' for r in rows),3)

    def test_four_distinct_counter_workers_and_fifth_waits_without_overbooking(self):
        trays=[('gallina','resource:tray_gallina'),('longaniza','resource:tray_longaniza'),
               ('costilla_cerdo','resource:tray_costilla_cerdo'),('sobrebarriga','resource:tray_sobrebarriga'),
               ('morcilla','resource:morcilla_access_2p')]
        with tempfile.TemporaryDirectory() as tmp:
            rows=controlled(Path(tmp),5,[[tray] for tray in trays])
        active=set();maximum=0;four_at_once=False
        for r in rows:
            if r['activity']=='counter_access':
                worker=r['objects']['worker']
                if r['lifecycle']=='start':
                    self.assertNotIn(worker,active);active.add(worker)
                    maximum=max(maximum,len(active))
                elif r['lifecycle']=='complete':active.remove(worker)
                self.assertLessEqual(len(active),4)
            if r['activity']=='product_pick' and r['lifecycle']=='start' and r['sim_time_s']==0:
                four_at_once=len(active)==4
        self.assertEqual(maximum,4);self.assertTrue(four_at_once);self.assertFalse(active)
        self.assertEqual(sum(r['activity']=='service_completed' for r in rows),5)

    def test_picks_use_reach_bands_and_do_not_return_to_assembly_per_portion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            result=run_experiment({'orders':12,'servers':5,'minutes':15,'arrival_mean_s':10},root)
            self.assertEqual(result['completed'],12)
            cfg=json.loads((root/'scenario.json').read_text());space=cfg['space']
            positions={w:space['cells'][c] for w,c in space['initial'].items()}
            rows=events(root/'events.sqlite3');picks=0
            for r in rows:
                worker=r['objects'].get('worker')
                if r['activity']=='space_move' and r['lifecycle']=='complete':
                    positions[worker]=r['payload']['to_xy_m']
                if r['activity']=='product_pick' and r['lifecycle']=='start':
                    loc=space['resource_locations'][r['objects']['resource']]
                    zone=space['reach_zones'].get(loc)
                    if zone:
                        x,y=positions[worker]
                        self.assertTrue(zone['min_x']<=x<=zone['max_x'])
                        self.assertTrue(zone['min_y']<=y<=zone['max_y']);picks+=1
            self.assertGreater(picks,20)
            self.assertFalse(any(r['activity']=='selection_travel' for r in rows))
            # No movement nested in deposit: basket stays at the current access point.
            depositing=set()
            for r in rows:
                worker=r['objects'].get('worker')
                if r['activity']=='product_deposit':
                    if r['lifecycle']=='start':depositing.add(worker)
                    elif r['lifecycle']=='complete':depositing.remove(worker)
                if r['activity']=='space_move':self.assertNotIn(worker,depositing)
            self.assertTrue(all(0<=v<=1 for v in result['worker_active_fraction'].values()))
            self.assertIn('reach-zones',(root/'replay.html').read_text())
