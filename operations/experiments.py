"""Local synthetic dispatch experiments. Does not alter source scenes or observations."""
from __future__ import annotations
import copy
import hashlib
import json
import math
import random
import sqlite3
import statistics
from pathlib import Path
from .adapters.schematic_2d import _load_layout, export_schematic_2d
from .domain.catalog import ProductCatalog
from .domain.timing import validate_duration
from .engine.simulation import run_scenario
from .engine.space import make_space, make_flexible_space
from .engine.reach import apply_reach_policy
from .adapters.isaac_replay import export_replay

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'config/operations'


def number(options, key, default, lo, hi, integer=False):
    value=options.get(key,default)
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi:
        raise ValueError(f'{key} must be between {lo} and {hi}')
    if integer and int(value)!=value:raise ValueError(f'{key} must be an integer')
    return int(value) if integer else float(value)


def prepare_experiment(options:dict, directory:Path) -> tuple[Path,Path]:
    servers=number(options,'servers',4,1,8,True)
    minutes=number(options,'minutes',30,2,120)
    count=number(options,'orders',30,1,150,True)
    arrival_mean=number(options,'arrival_mean_s',30,5,300)
    takeaway=number(options,'takeaway_fraction',.5,0,1)
    seed=number(options,'seed',42,0,2147483647,True)
    space_enabled=options.get('space_enabled',True)
    if not isinstance(space_enabled,bool):raise ValueError('space_enabled must be boolean')
    movement_mode=options.get('movement_mode','flexible')
    if movement_mode not in {'flexible','reserved'}:raise ValueError('Unknown movement mode')
    directory.mkdir(parents=True,exist_ok=True)
    catalog=ProductCatalog.load(CONFIG/'product_catalog.json').raw
    overrides=options.get('product_overrides',{})
    if not isinstance(overrides,dict):raise ValueError('product_overrides must be an object')
    known={p['product_id'] for p in catalog['products']}
    if set(overrides)-known:raise ValueError('unknown product override')
    for p in catalog['products']:
        if p['product_id'] in overrides:
            validate_duration(overrides[p['product_id']])
            p['handling_time']['selection_per_unit_s']=overrides[p['product_id']]
            p['handling_time']['experiment_override']=True
    cp=directory/'products.json';cp.write_text(json.dumps(catalog,ensure_ascii=False,indent=2))
    ProductCatalog.load(cp)
    config=json.loads((CONFIG/'three_order_visual_test.json').read_text())
    config.pop('staffing_profile_file',None)
    profile=json.loads((CONFIG/'staffing_profile.json').read_text())
    worker_template=profile['workers'][0]
    workers=[{**copy.deepcopy(worker_template),'worker_id':f'worker:server{i}','display_code':f'S{i}'} for i in range(1,servers+1)]
    workers += [{**w,'display_code':'CAJA'} for w in profile['workers'] if w['primary_role']=='CASHIER']
    profile['workers']=workers
    profile['constant_positions']=[p for p in profile.get('constant_positions',[]) if p['role']=='CASHIER']
    profile['server_pool']['visual_test_workers']=servers
    config.update(workers=workers,staffing_profile_snapshot=profile,product_catalog_file=str(cp.resolve()),
        menu_price_catalog_file=str((CONFIG/'menu_prices.json').resolve()),
        scenario_id='scenario:customer_flow_experiment',model_version='dispatch_flow_v2',
        stop_time_s=minutes*60,visits=[],customer_flow=True,experiment_options=copy.deepcopy(options))
    config['assumptions'].update({'purpose':'Customer–server–payment–basket handover–next customer flow test',
        'staffing':f'{servers} experimental order servers plus one cashier; no soup or frying roles',
        'customers':'Synthetic patience equals the experiment horizon; no calibrated abandonment behavior',
        'shared_trays':'One assumed shared small-product access point; specific product locations remain unconfirmed',
        'travel':'Fixture-aware center paths at assumed 0.8 m/s when spatial mode is enabled; fixed configured travel otherwise',
        'orders':'Synthetic random baskets, not confirmed commercial picada recipes or measured demand',
        'arrival_process':'Poisson arrivals with editable mean interarrival time; not observed demand',
        'timings':'Reported user estimates with assumed distributions; unconfirmed products keep synthetic defaults',
        'space':'Flexible concurrent passing; no rigid worker obstacles. Fixture center paths and illustrative 20x40 cm torsos are not validated pedestrian mechanics.' if movement_mode=='flexible' else 'Conservative grid reservations, legacy experiment',
        'quantity':'Independent selection and cutting draws per portion; linear scaling is assumed',
        'geometry':'Snapshot hash checked against source; no automatic claim of up-to-date geometry',
        'service_roles':'Order servers plus one cashier only. Soup, frying and replenishment excluded in this first flow test.'})
    for key,default in [('cutting_min_s',3),('cutting_max_s',10),('payment_min_s',20),('payment_max_s',30)]:
        options[key]=number(options,key,default,0,120)
    cut={'distribution':'uniform','min_s':options['cutting_min_s'],'max_s':options['cutting_max_s']}
    pay={'distribution':'uniform','min_s':options['payment_min_s'],'max_s':options['payment_max_s']}
    validate_duration(cut);validate_duration(pay)
    config['durations']['cutting_per_portion_s']=cut;config['durations']['payment_s']=pay
    layout=json.loads((CONFIG/'layout_2d_blender.json').read_text())
    layout['geometry_snapshot_file']=str((CONFIG/layout['geometry_snapshot_file']).resolve())
    layout['notes']=[n for n in layout['notes'] if 'fryer' not in n.lower()]
    layout['notes'].append('Primer test: servidores y caja, productos abundantes. Sin roles de sopas ni frituras.')
    layout['agent_geometry'].update(worker_body_diameter_m=.4,worker_clearance_m=0,worker_torso_width_m=.4,worker_torso_depth_m=.2)
    for i in range(6,servers+1):
        name=f'idle_server_{i}';layout['locations'][name]={'x':-2+(i-5)*.52,'y':-2.1,'label':f'S{i} provisional idle'}
        layout['worker_idle_locations'][f'worker:server{i}']=name
    policy=json.loads((CONFIG/'reach_policy.json').read_text())
    policy['counter_capacity']=number(options,'counter_capacity',policy['counter_capacity'],1,8,True)
    lp=directory/'layout.json';lp.write_text(json.dumps(layout,ensure_ascii=False,indent=2))
    loaded=_load_layout(lp)
    if movement_mode=='flexible':
        apply_reach_policy(config,loaded,policy)
    for key in ['locations','resource_locations','worker_access_locations','reach_zones','notes']:
        if key in loaded:layout[key]=loaded[key]
    lp.write_text(json.dumps(layout,ensure_ascii=False,indent=2))
    config['model_version']='dispatch_reach_v3'
    config['assumptions']['selection']='Available ingredient first; two per tray (morcilla reported; other tray capacities assumed), four at six-tray counter. Basket carried locally; no central return per pick.'
    if space_enabled:
        config['space']=(make_flexible_space if movement_mode=='flexible' else make_space)(loaded,workers)
        config['durations']['travel_s']=0 # grid movement carries the travel time
    snapshot=json.loads(Path(layout['geometry_snapshot_file']).read_text())
    config['replay_floor_z_m']=next(e['bounds_m']['max'][2] for e in snapshot['entities'] if e['entity_id']=='floor:despacho')
    scene=ROOT/snapshot['source_blend']
    config['geometry_snapshot_status']={'snapshot_sha256':snapshot['source_sha256'],
        'current_scene_sha256':hashlib.sha256(scene.read_bytes()).hexdigest(),
        'matches_current_scene':hashlib.sha256(scene.read_bytes()).hexdigest()==snapshot['source_sha256']}
    byid={p['product_id']:p for p in catalog['products']}
    prices=json.loads((CONFIG/'menu_prices.json').read_text())
    sale={p['product_id']:p['sale_option_id'] for p in prices['items']}
    foods=['morcilla','longaniza','costilla_cerdo','sobrebarriga','gallina','chicharron','papa_criolla','arepa','platano']
    resources={'morcilla':'morcilla_access_2p','chicharron':'chicharron_access','papa_criolla':'papa_criolla_access_2p','arepa':'small_tray_group_access','platano':'small_tray_group_access','soup':'soups'}
    if movement_mode=='flexible':
        resources.update({t['product_id'].split(':',1)[1]:t['resource_id'].split(':',1)[1] for t in policy['tray_resources']})
    rng=random.Random(seed);arrival=0.0
    for i in range(1,count+1):
        if i>1:arrival+=rng.expovariate(1/arrival_mean)
        if arrival>=minutes*60:break
        size=rng.choices(['small','medium','large'],[.35,.4,.25])[0]
        chosen=rng.sample(foods,{'small':3,'medium':5,'large':8}[size])
        lines=[]
        for product in chosen:
            pid='product:'+product
            quantity=rng.randint(1,{'small':1,'medium':2,'large':4}[size])
            line={'sale_option_id':sale[pid],'product_id':pid,'quantity':quantity,'unit':byid[pid]['sale_unit'],
                  'resource_id':'resource:'+resources.get(product,'main_tray_access')}
            if product=='soup':line['service_worker_id']='worker:soup1'
            lines.append(line)
        config['visits'].append({'visit_id':f'visit:{i:04d}','arrival_s':arrival,'patience_s':minutes*60,
            'party_size':1,'queue_participants':1,'order':{'order_id':f'order:{i:04d}','size_label':size,
            'channel':'walk_in','fulfillment_mode':'takeaway' if rng.random()<takeaway else 'dine_in','lines':lines}})
    config['experiment_options'].update(options,servers=servers,minutes=minutes,seed=seed,
        actual_generated_orders=len(config['visits']))
    scenario=directory/'scenario.json';scenario.write_text(json.dumps(config,ensure_ascii=False,indent=2))
    return scenario,lp


def summarize(database:Path,run_id:str) -> dict:
    c=sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    run=c.execute('select * from runs where run_id=?',(run_id,)).fetchone()
    cutoff=float(run['analysis_cutoff_s']);config=json.loads(run['effective_config_json'])
    objects={}
    for r in c.execute('select eo.* from event_objects eo join events e using(recording_cursor) where e.run_id=?',(run_id,)):
        objects.setdefault(r['recording_cursor'],{}).setdefault(r['object_type'],r['object_id'])
    activities={};arrivals={};completed={};queue_wait=[];service_starts={};by_resource={};worker_active={};acquisitions={}
    for e in c.execute('select * from events where run_id=? order by sim_time_s,recording_cursor',(run_id,)):
        t=e['sim_time_s'];o=objects.get(e['recording_cursor'],{});a=e['activity'];life=e['lifecycle'];key=e['activity_id']
        if a=='visit_arrival':arrivals[o['visit']]=t
        if a=='ordering_queue' and life=='start':
            queue_wait.append(t-arrivals[o['visit']]);service_starts[o['visit']]=t
        if a in {'visit_departure','visit_to_dining'}:completed[o['visit']]=t
        if a=='resource_access_acquired':acquisitions[json.loads(e['payload_json'])['reservation_activity_id']]=t
        if key:
            record=activities.setdefault(key,{'activity':a,'objects':o})
            record[life]=t
            if life=='start':record['payload']=json.loads(e['payload_json'])
    # Clip open intervals at the cutoff. Do not fabricate completion events.
    for activity_id,record in activities.items():
        a=record['activity'];o=record['objects'];end=record.get('complete',cutoff)
        if 'request' in record and 'resource' in o:
            r=by_resource.setdefault(o['resource'],{'wait_s':0,'busy_s':0,'requests':0,'unfinished':0})
            acquired=acquisitions.get(activity_id,record.get('payload',{}).get('resource_acquired_s',record.get('start',cutoff)))
            r['wait_s']+=acquired-record['request'];r['requests']+=1
            r['busy_s']+=max(0,end-acquired) if 'start' in record or activity_id in acquisitions else 0
            r['unfinished']+=int('complete' not in record)
        if 'start' in record and 'worker' in o and a not in {'ordering_queue','space_wait','counter_access','ingredient_wait'}:
            worker_active[o['worker']]=worker_active.get(o['worker'],0)+max(0,end-record['start'])
    totals=[completed[v]-arrivals[v] for v in completed]
    service=[completed[v]-service_starts[v] for v in completed if v in service_starts]
    waits=[r.get('start',cutoff)-r['request'] for r in activities.values() if r['activity']=='ordering_queue' and 'request' in r]
    result={'run_id':run_id,'evidence':'synthetic','status':run['status'],'horizon_s':cutoff,
      'arrived':len(arrivals),'completed':len(completed),'unfinished_visits':len(arrivals)-len(completed),
      'mean_completed_total_s':statistics.mean(totals) if totals else None,
      'mean_completed_service_s':statistics.mean(service) if service else None,
      'mean_served_queue_s':statistics.mean(queue_wait) if queue_wait else None,
      'queue_person_seconds':sum(waits),'throughput_per_hour':len(completed)*3600/cutoff,
      'ingredient_wait_person_seconds':sum(max(0,r.get('complete',cutoff)-r['start']) for r in activities.values() if r['activity']=='ingredient_wait' and 'start' in r),
      'resources':by_resource,'worker_active_fraction':{k:v/cutoff for k,v in worker_active.items()},
      'geometry':config.get('geometry_snapshot_status'),
      'cashier_queue_person_seconds':sum(r.get('start',cutoff)-r['request'] for r in activities.values() if r['activity']=='payment_queue' and 'request' in r),
      'last_event_s':c.execute('select max(sim_time_s) from events where run_id=?',(run_id,)).fetchone()[0],
      'customer_services':[{"visit_id":v,"service_start_s":service_starts[v],"completion_s":completed.get(v),"service_elapsed_s":completed[v]-service_starts[v] if v in completed else cutoff-service_starts[v],"complete":v in completed} for v in service_starts],
      'assumptions':config['assumptions'],'note':'Completed-order means exclude unfinished orders; inspect unfinished counts and queue person-seconds too.'}
    c.close();return result


def run_experiment(options:dict,directory:Path) -> dict:
    scenario,layout=prepare_experiment(copy.deepcopy(options),directory)
    result=run_scenario(scenario,directory/'events.sqlite3',seed=int(options.get('seed',42)),run_id='run:'+directory.name)
    export_schematic_2d(result.database,result.run_id,layout,directory/'replay.html')
    if options.get('space_enabled',True):
        export_replay(result.database,directory/'isaac_replay.json',result.run_id)
    summary=summarize(result.database,result.run_id)
    summary['incomplete_activities']=result.incomplete_activity_count
    (directory/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary
