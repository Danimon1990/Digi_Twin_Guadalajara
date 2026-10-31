from __future__ import annotations
import json
import math
import random
import sqlite3
import statistics
import tempfile
import unittest
from pathlib import Path
from operations.domain.timing import sample_duration, sample_portions, validate_duration
from operations.experiments import prepare_experiment, run_experiment


class TimingTests(unittest.TestCase):
    def test_reported_means_match_explicit_triangular_assumptions(self):
        catalog=json.loads((Path(__file__).resolve().parents[2]/'config/operations/product_catalog.json').read_text())
        products={p['product_id']:p for p in catalog['products']}
        for id,expected in [('product:papa_criolla',8),('product:gallina',12)]:
            spec=products[id]['handling_time']['selection_per_unit_s']
            self.assertEqual((spec['min_s']+spec['mode_s']+spec['max_s'])/3,expected)

    def test_triangular_bounds_mean_and_seed(self):
        spec={'distribution':'triangular','min_s':4,'mode_s':6,'max_s':10}
        rng=random.Random(17);values=[sample_duration(spec,rng) for _ in range(15000)]
        self.assertGreaterEqual(min(values),4);self.assertLessEqual(max(values),10)
        self.assertAlmostEqual(statistics.mean(values),20/3,delta=.04)
        self.assertGreater(len({round(v,3) for v in values}),100)
        self.assertEqual(sample_portions(spec,3,random.Random(9)),sample_portions(spec,3,random.Random(9)))
        self.assertEqual(sample_portions(4,3,random.Random(9)),12)

    def test_invalid_specs_fail_before_simulation(self):
        for spec in [-1,float('nan'),{'distribution':'uniform','min_s':10,'max_s':4},
                     {'distribution':'triangular','min_s':4,'mode_s':12,'max_s':10},True]:
            with self.assertRaises(ValueError):validate_duration(spec)


class ExperimentTests(unittest.TestCase):
    def test_crowded_workers_can_yield_without_permanent_gridlock(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=run_experiment({'servers':8,'orders':10,'minutes':15,'arrival_mean_s':30,'space_enabled':True,'movement_mode':'reserved'},Path(tmp))
            self.assertEqual(result['completed'],10)
            self.assertEqual(result['incomplete_activities'],0)

    def test_default_customer_flow_holds_four_servers_until_paid_and_delivered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            result=run_experiment({'orders':12,'minutes':15,'arrival_mean_s':20},root)
            scenario=json.loads((root/'scenario.json').read_text())
            self.assertEqual(len(scenario['workers']),5)
            self.assertEqual([w['primary_role'] for w in scenario['workers']].count('ORDER_SERVER'),4)
            self.assertEqual([w['primary_role'] for w in scenario['workers']].count('CASHIER'),1)
            self.assertEqual(scenario['space']['movement_mode'],'flexible')
            self.assertTrue(all(line['product_id']!='product:soup' for v in scenario['visits'] for line in v['order']['lines']))
            self.assertEqual(result['completed'],12)
            c=sqlite3.connect(root/'events.sqlite3');c.row_factory=sqlite3.Row
            rows=c.execute('select * from events order by recording_cursor').fetchall()
            links={}
            for r in c.execute('select * from event_objects'):
                links.setdefault(r['recording_cursor'],{})[r['object_type']]=r['object_id']
            active={};started={};paid={};received={};completed={}
            for r in rows:
                o=links.get(r['recording_cursor'],{});a=r['activity'];t=r['sim_time_s']
                if a=='service_assigned':
                    self.assertNotIn(o['worker'],active)
                    active[o['worker']]=o['visit'];started[o['visit']]=t
                elif a=='payment_confirmed':paid[o['order']]=t
                elif a=='handover' and r['lifecycle']=='complete':received[o['order']]=t
                elif a=='service_completed':
                    self.assertEqual(active[o['worker']],o['visit'])
                    self.assertLessEqual(paid[o['order']],t);self.assertLessEqual(received[o['order']],t)
                    self.assertAlmostEqual(json.loads(r['payload_json'])['service_elapsed_s'],t-started[o['visit']])
                    completed[o['visit']]=t
                elif a=='server_released':
                    v=active.pop(o['worker']);self.assertIn(v,completed)
            self.assertEqual(active,{})
            self.assertEqual(len(started),12);self.assertEqual(len(completed),12)
            # Independent motion has overlapping worker intervals, rather than a global lane.
            moves=c.execute("select e.sim_time_s,e.payload_json,o.object_id from events e join event_objects o using(recording_cursor) where e.activity='space_move' and e.lifecycle='start' and o.object_type='worker' order by e.sim_time_s").fetchall()
            self.assertTrue(any(b[0]<a[0]+json.loads(a[1])['duration_s'] and a[2]!=b[2] for a,b in zip(moves,moves[1:])))
            c.close()

    def test_generation_repeats_same_demand_when_staffing_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,_=prepare_experiment({'servers':2,'orders':12,'seed':10,'space_enabled':False},Path(tmp)/'a')
            b,_=prepare_experiment({'servers':5,'orders':12,'seed':10,'space_enabled':False},Path(tmp)/'b')
            self.assertEqual(json.loads(a.read_text())['visits'],json.loads(b.read_text())['visits'])
            for invalid in [{'servers':0},{'servers':2.5},{'minutes':float('nan')},{'orders':9999},{'space_enabled':'yes'}]:
                with self.assertRaises(ValueError):prepare_experiment(invalid,Path(tmp)/'bad')

    def test_shared_cutting_scaled_by_portions_and_payments_in_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);r=run_experiment({'servers':3,'orders':8,'minutes':15,'arrival_mean_s':10,'space_enabled':False},root)
            self.assertGreater(r['completed'],0)
            c=sqlite3.connect(root/'events.sqlite3');c.row_factory=sqlite3.Row
            rows=c.execute("select activity,lifecycle,sim_time_s,activity_id,payload_json from events where activity in ('cutting','payment','product_pick') order by sim_time_s,recording_cursor").fetchall()
            busy=0;maxbusy=0
            for row in rows:
                p=json.loads(row['payload_json'])
                if row['activity']=='cutting':
                    if row['lifecycle']=='start':
                        self.assertGreaterEqual(p['duration_s'],3*p['cut_portions'])
                        self.assertLessEqual(p['duration_s'],10*p['cut_portions']);busy+=1;maxbusy=max(maxbusy,busy)
                    elif row['lifecycle']=='complete':busy-=1
                if row['activity']=='payment' and row['lifecycle']=='start':
                    self.assertGreaterEqual(p['duration_s'],20);self.assertLessEqual(p['duration_s'],30)
            self.assertEqual(maxbusy,1)
            self.assertEqual(c.execute('pragma integrity_check').fetchone()[0],'ok')
            self.assertTrue((root/'replay.html').is_file());self.assertTrue((root/'summary.json').is_file())
            self.assertTrue(all(0<=v<=1 for v in r['worker_active_fraction'].values()));c.close()

    def test_spatial_footprints_do_not_overlap_during_interpolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);result=run_experiment({'servers':3,'orders':6,'minutes':8,'arrival_mean_s':10,'space_enabled':True,'movement_mode':'reserved'},root)
            self.assertGreater(result['completed'],0)
            cfg=json.loads((root/'scenario.json').read_text());space=cfg['space']
            initial={w:space['cells'][cell] for w,cell in space['initial'].items()}
            c=sqlite3.connect(root/'events.sqlite3')
            moves=[]
            for time,payload,worker in c.execute("select e.sim_time_s,e.payload_json,o.object_id from events e join event_objects o using(recording_cursor) where e.activity='space_move' and e.lifecycle='start' and o.object_type='worker' order by e.sim_time_s"):
                moves.append((time,json.loads(payload),worker))
            self.assertGreater(len(moves),0)
            # Every moving square is checked against every parked square at each leg's midpoint.
            positions=dict(initial);previous_end=-1
            for time,p,w in moves:
                self.assertGreaterEqual(time+1e-8,previous_end)
                midpoint=[(a+b)/2 for a,b in zip(p['from_xy_m'],p['to_xy_m'])]
                for other,xy in positions.items():
                    if other==w:continue
                    self.assertTrue(abs(xy[0]-midpoint[0])>=.5-1e-6 or abs(xy[1]-midpoint[1])>=.5-1e-6)
                positions[w]=p['to_xy_m'];previous_end=time+p['duration_s']
            self.assertEqual(c.execute('pragma integrity_check').fetchone()[0],'ok');c.close()
            html=(root/'replay.html').read_text();self.assertIn('spatialPosition',html)


if __name__=='__main__':unittest.main()
