"""Session-only USD replay; usable independently of Kit UI."""
from bisect import bisect_right
import math

from pxr import Gf, Sdf, Usd, UsdGeom

ROOT = '/GuadalajaraSimPyReplay'
COLORS = [(0.12,.42,.85),(.82,.24,.12),(.25,.65,.22),(.59,.25,.78),(.84,.55,.12)]


class Replay:
    def __init__(self, stage, data):
        if data.get('schema') != 'guadalajara_simpy_replay_v1' or data.get('evidence') != 'synthetic':
            raise ValueError('Unsupported replay file.')
        if not stage.GetPrimAtPath('/Guadalajara') or UsdGeom.GetStageUpAxis(stage) != 'Z' or UsdGeom.GetStageMetersPerUnit(stage) != 1:
            raise ValueError('Open the Guadalajara meter-scale, Z-up stage first.')
        if stage.GetPrimAtPath(ROOT):
            raise ValueError('A replay overlay already exists.')
        self.stage, self.data = stage, data
        self.duration = float(data['duration_s'])
        if not math.isfinite(self.duration) or self.duration <= 0:
            raise ValueError('Invalid replay duration.')
        self.layer = Sdf.Layer.CreateAnonymous('Guadalajara_SimPy_Replay.usda')
        stage.GetSessionLayer().subLayerPaths.insert(0,self.layer.identifier)
        self.actors = {}
        try:
            with Usd.EditContext(stage, self.layer):
                UsdGeom.Xform.Define(stage, ROOT)
                for i,w in enumerate(data['workers']):
                    path = f'{ROOT}/Worker_{i+1}'
                    actor = UsdGeom.Xform.Define(stage,path)
                    actor.GetPrim().SetDisplayName(w['label'])
                    move = actor.AddTranslateOp()
                    turn = actor.AddRotateZOp()
                    color = COLORS[i % len(COLORS)] if w['role'] != 'CASHIER' else (.25,.28,.31)
                    for name,kind,xyz,scale,rgb in [
                        ('Body',UsdGeom.Capsule,(0,0,.67),(.18,.15,.53),color),
                        ('Head',UsdGeom.Sphere,(0,0,1.42),(.13,.13,.13),(.78,.53,.32)),
                        ('Basket',UsdGeom.Sphere,(.29,0,.92),(.19,.19,.07),(.57,.31,.12)),
                    ]:
                        shape=kind.Define(stage,f'{path}/{name}')
                        shape.CreateRadiusAttr(1)
                        if kind == UsdGeom.Capsule:
                            shape.CreateHeightAttr(1)
                            shape.CreateAxisAttr('Z')
                        shape.AddTranslateOp().Set(Gf.Vec3d(*xyz))
                        shape.AddScaleOp().Set(Gf.Vec3f(*scale))
                        shape.CreateDisplayColorAttr([Gf.Vec3f(*rgb)])
                    basket = UsdGeom.Imageable(stage.GetPrimAtPath(path+'/Basket')).CreateVisibilityAttr()
                    self.actors[w['id']] = (w, [m[0] for m in w['moves']], move, turn, basket)
            self.seek(0)
        except Exception:
            self.close()
            raise

    def seek(self, seconds):
        t = max(0,min(self.duration,float(seconds)))
        self.time = t
        active, activity, completed, queue = {}, {}, {}, set()
        for event in self.data['events']:
            if event['t'] > t:
                break
            a,w,c = event['activity'],event['worker'],event['customer']
            if a == 'visit_arrival':
                queue.add(c)
            elif a == 'visit_abandoned':
                queue.discard(c)
            elif a == 'service_assigned':
                queue.discard(c)
                active[w] = (c,event['t'])
            elif a == 'service_completed':
                started = active.pop(w,None)
                if started:
                    completed[c] = event['t']-started[1]
            elif a == 'server_released':
                activity.pop(w,None)
            elif w and event['life'] in {'start','request'}:
                activity[w] = event
            elif w and event['life']=='complete' and activity.get(w,{}).get('key')==event['key']:
                activity.pop(w,None)
        rows = []
        with Usd.EditContext(self.stage,self.layer):
            for wid,(worker,times,move,turn,basket) in self.actors.items():
                x,y = worker['initial']
                angle = 0
                j = bisect_right(times,t)-1
                if j>=0:
                    start,end,p,q = worker['moves'][j]
                    f = min(1,(t-start)/(end-start)) if end>start else 1
                    x,y = [a+(b-a)*f for a,b in zip(p,q)]
                    angle = math.degrees(math.atan2(q[1]-p[1],q[0]-p[0]))
                move.Set(Gf.Vec3d(x,y,self.data['floor_z_m']))
                turn.Set(angle)
                basket.Set('inherited' if wid in active else 'invisible')
                e = activity.get(wid,{})
                rows.append((worker['label'], active.get(wid), e.get('activity','idle'),e.get('product')))
        return {'rows':rows,'waiting':len(queue),'completed':completed}

    def close(self):
        paths = self.stage.GetSessionLayer().subLayerPaths
        if self.layer.identifier in paths:
            paths.remove(self.layer.identifier)
