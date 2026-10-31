"""Experimental fixture-aware worker movement.

FlexibleSpace permits concurrent passing with illustrative 20 x 40 cm torsos.
FloorSpace retains the earlier conservative 50 cm occupancy experiment. Neither
mode is validated pedestrian routing or an ergonomic clearance assessment.
"""
from __future__ import annotations
from collections import deque
import math
import simpy


def make_space(layout: dict, workers: list[dict], body_m: float = .5) -> dict:
    pitch = body_m + .02
    room = next(f for f in layout['fixtures'] if f['class'] == 'room')
    fixtures = [f for f in layout['fixtures'] if f['class'] not in {'room','door'}]
    cells = {}
    for i in range(int(room['width'] / pitch)):
        for j in range(int(room['height'] / pitch)):
            x=room['x'] + (i+.5)*pitch; y=room['y'] + (j+.5)*pitch
            if any(abs(x-(f['x']+f['width']/2)) < (body_m+f['width'])/2 and
                   abs(y-(f['y']+f['height']/2)) < (body_m+f['height'])/2 for f in fixtures):
                continue
            cells[f'{i},{j}']=[round(x,6),round(y,6)]
    # Retain the largest connected component, so every initial worker can move.
    components=[];remaining=set(cells)
    while remaining:
        first=next(iter(remaining)); comp={first}; pending=[first];remaining.remove(first)
        while pending:
            for n in neighbors(pending.pop()):
                if n in remaining:remaining.remove(n);comp.add(n);pending.append(n)
        components.append(comp)
    connected=max(components,key=len,default=set());cells={k:v for k,v in cells.items() if k in connected}
    if len(cells) < len(workers)+4:
        raise ValueError('Not enough connected fixture-clear cells for selected staffing and envelope')
    initial={}; available=set(cells)
    for worker in workers:
        loc=layout['locations'][layout['worker_idle_locations'].get(worker['worker_id'],'aisle')]
        chosen=min(available,key=lambda c:(math.dist(cells[c],[loc['x'],loc['y']]),c))
        initial[worker['worker_id']]=chosen;available.remove(chosen)
    return {'cells':cells,'initial':initial,'locations':layout['locations'],
            'resource_locations':layout['resource_locations'],'activity_locations':layout['activity_locations'],
            'pitch_m':pitch,'body_width_m':body_m,'body_depth_m':body_m,'proxy_height_m':body_m,
            'speed_m_s':.8,'evidence':'synthetic_provisional_grid',
            'note':'Conservative single movement lane. 0.5 m proxy envelope, 0.02 m gap. Not measured routes or human stature.'}


def neighbors(key):
    i,j=map(int,key.split(','))
    return [f'{i+1},{j}',f'{i-1},{j}',f'{i},{j+1}',f'{i},{j-1}']


class FloorSpace:
    def __init__(self, env, config):
        self.env=env;self.config=config;self.positions=dict(config['initial'])
        self.traffic=simpy.Resource(env,capacity=1);self.changed=env.event()
        self.busy=set()

    def notify(self):
        old=self.changed;self.changed=self.env.event();old.succeed()

    def set_busy(self,worker,value):
        if value:self.busy.add(worker)
        else:self.busy.discard(worker)
        self.notify()

    def reachable(self, worker):
        occupied=set(self.positions.values())-{self.positions[worker]}
        start=self.positions[worker]; seen={start:None};todo=deque([start])
        while todo:
            c=todo.popleft()
            for n in neighbors(c):
                if n in self.config['cells'] and n not in occupied and n not in seen:
                    seen[n]=c;todo.append(n)
        return seen

    def route(self, worker, target):
        seen=self.reachable(worker);start=self.positions[worker]
        loc=self.config['locations'].get(target,self.config['locations']['aisle'])
        candidates=[c for c in seen if math.dist(self.config['cells'][c],[loc['x'],loc['y']]) <= .95]
        if not candidates:return None
        goal=min(candidates,key=lambda c:(math.dist(self.config['cells'][c],[loc['x'],loc['y']]),c))
        route=[goal]
        while route[0]!=start:route.insert(0,seen[route[0]])
        return route

    def move(self, worker, target, emit, order_id):
        while True:
            with self.traffic.request() as claim:
                yield claim
                route=self.route(worker,target)
                if route is None:
                    # Yielding experiment: an idle/waiting blocker may step into
                    # a free adjacent cell. Never move someone actively handling food.
                    candidates=[];original_reach=len(self.reachable(worker))
                    for other,cell in self.positions.items():
                        if other==worker or other in self.busy:continue
                        reachable=self.reachable(other)
                        for neighbor in reachable:
                            if neighbor==cell:continue
                            self.positions[other]=neighbor
                            cleared=self.route(worker,target)
                            gain=len(self.reachable(worker))-original_reach
                            self.positions[other]=cell
                            if cleared is not None or gain>0:
                                path=[neighbor]
                                while path[0]!=cell:path.insert(0,reachable[path[0]])
                                candidates.append((cleared is None,-gain,len(path),other,path))
                    if candidates:
                        _,_,_,other,path=sorted(candidates)[0]
                        for a,b in zip(path,path[1:]):
                            pa=self.config['cells'][a];pb=self.config['cells'][b]
                            yield from emit(other,None,pa,pb,math.dist(pa,pb)/self.config['speed_m_s'])
                            self.positions[other]=b;self.notify()
                        route=self.route(worker,target)
                        if route is None:
                            # Re-evaluate after opening additional floor cells.
                            continue
                if route is not None:
                    for a,b in zip(route,route[1:]):
                        pa=self.config['cells'][a];pb=self.config['cells'][b]
                        duration=math.dist(pa,pb)/self.config['speed_m_s']
                        yield from emit(worker,order_id,pa,pb,duration)
                        self.positions[worker]=b
                        self.notify()
                    return
                changed=self.changed
            yield changed


def make_flexible_space(layout: dict, workers: list[dict]) -> dict:
    """Fixture-aware center paths with concurrent passing, not hard body boxes.

    Other workers do not become immovable obstacles. The 20 x 40 cm torso and
    reaching arms are visual proxies; person-person clearance is not calibrated.
    """
    config = make_space(layout, workers, body_m=.20)
    config.update(movement_mode='flexible',body_width_m=.40,body_depth_m=.20,
                  proxy_height_m=None,evidence='synthetic_flexible_passing',
                  note='Concurrent fixture-aware paths. Workers can pass; torso/arms are illustrative, not collision or ergonomic certification.')
    return config


class FlexibleSpace(FloorSpace):
    """Move independently; keep equipment constraints without a global lane."""
    def __init__(self, env, config):
        super().__init__(env, config)
        self.targets = {}

    def reachable(self, worker):
        start=self.positions[worker];seen={start:None};todo=deque([start])
        while todo:
            cell=todo.popleft()
            for other in neighbors(cell):
                if other in self.config['cells'] and other not in seen:
                    seen[other]=cell;todo.append(other)
        return seen

    def route(self, worker, target):
        seen=self.reachable(worker);start=self.positions[worker]
        loc=self.config['locations'].get(target,self.config['locations']['aisle'])
        candidates=[cell for cell in seen if math.dist(self.config['cells'][cell],[loc['x'],loc['y']])<=.95]
        if not candidates:
            raise ValueError(f'No fixture-clear access to {target!r}')
        occupied={c for w,c in self.positions.items() if w!=worker}
        reserved={c for w,c in self.targets.items() if w!=worker}
        # Prefer separate resting positions, without creating a hard human queue.
        goal=min(candidates,key=lambda c:(c in reserved or c in occupied,
                    math.dist(self.config['cells'][c],[loc['x'],loc['y']]),c))
        self.targets[worker]=goal
        route=[goal]
        while route[0]!=start:route.insert(0,seen[route[0]])
        return route

    def move(self, worker, target, emit, order_id):
        route=self.route(worker,target)
        try:
            for a,b in zip(route,route[1:]):
                pa=self.config['cells'][a];pb=self.config['cells'][b]
                yield from emit(worker,order_id,pa,pb,math.dist(pa,pb)/self.config['speed_m_s'])
                self.positions[worker]=b
        finally:
            self.targets.pop(worker,None)
