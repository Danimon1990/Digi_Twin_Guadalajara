"""Pack table point instances into saved cube footprints with walking gaps.

Footprints survive marker deletion in config/usd/dining_areas.json. The layout
checks projected boundaries, floor support, and wall/stair/column geometry.
"""
import json
import math
from pathlib import Path
from pxr import Gf, Sdf, Usd, UsdGeom
from build_dining_instances import hull, clearance
from build_cone_dining import floor_z

ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'config/usd/dining_areas.json'
OUTPUT=ROOT/'usd/layers/areas/marked_dining.usda'
BRANCH='/Guadalajara/Areas/Comedores/Stations/Furniture/MarkedDining'


def inside_marked_area(x,y):
    if not CONFIG.exists():return False
    return any(clearance((x,y),hull([tuple(p) for p in a['polygon']]))>=0
               for a in json.loads(CONFIG.read_text())['areas'])


def separated(a,b):
    for polygon in (a,b):
        for p,q in zip(polygon,polygon[1:]+polygon[:1]):
            axis=(q[1]-p[1],p[0]-q[0])
            if abs(axis[0])+abs(axis[1])<1e-8:continue
            aa=[v[0]*axis[0]+v[1]*axis[1] for v in a]
            bb=[v[0]*axis[0]+v[1]*axis[1] for v in b]
            if max(aa)<min(bb)-1e-6 or max(bb)<min(aa)-1e-6:return True
    return False


def clip(poly,z,above):
    result=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        ain=(a[2]>=z) if above else (a[2]<=z)
        bin=(b[2]>=z) if above else (b[2]<=z)
        if ain:result.append(a)
        if ain!=bin:result.append(a+(b-a)*((z-a[2])/(b[2]-a[2])))
    return result


def obstacles(stage):
    cache=UsdGeom.XformCache();result=[]
    for p in stage.Traverse():
        if not p.IsA(UsdGeom.Mesh) or not any(part in str(p.GetPath()) for part in
                ('/Architecture/Walls/','/Architecture/Stairs/','/Architecture/Columns/')):continue
        m=UsdGeom.Mesh(p);matrix=cache.GetLocalToWorldTransform(p)
        points=[matrix.Transform(Gf.Vec3d(*v)) for v in m.GetPointsAttr().Get()]
        indices=m.GetFaceVertexIndicesAttr().Get();offset=0
        for count in m.GetFaceVertexCountsAttr().Get():
            face=[points[i] for i in indices[offset:offset+count]];offset+=count
            for i in range(1,len(face)-1):result.append([face[0],face[i],face[i+1]])
    return result


def main():
    config=json.loads(CONFIG.read_text());stage=Usd.Stage.Open(str(ROOT/'usd/guadalajara_base.usda'))
    ref=UsdGeom.PointInstancer(stage.GetPrimAtPath('/Guadalajara/Areas/Comedores/Stations/Furniture/DiningSets/MainDining'))
    scale=ref.GetScalesAttr().Get()[0]
    asset=Usd.Stage.Open(str(ROOT/'usd/assets/furniture/comedor_bench_table/comedor_bench_table.usdc'))
    box=UsdGeom.BBoxCache(0,['default','render']).ComputeWorldBound(asset.GetDefaultPrim()).ComputeAlignedRange()
    lo,hi=box.GetMin(),box.GetMax();width=(hi[0]-lo[0])*scale[0];depth=(hi[1]-lo[1])*scale[1]
    height=(hi[2]-lo[2])*scale[2];wall_faces=obstacles(stage);plans=[]
    for area in config['areas']:
        polygon=hull([tuple(p) for p in area['polygon']]);a,b=area['polygon'][:2]
        base=math.atan2(b[1]-a[1],b[0]-a[0]);best=None
        for yaw in (base,base+math.pi/2):
            c,s=math.cos(yaw),math.sin(yaw)
            local=[(x*c+y*s,-x*s+y*c) for x,y in polygon]
            mins=[min(p[i] for p in local) for i in (0,1)];maxs=[max(p[i] for p in local) for i in (0,1)]
            margin=config['boundaryMargin'];gap=config['minimumGap']
            nx=math.floor((maxs[0]-mins[0]-2*margin+gap)/(width+gap))
            ny=math.floor((maxs[1]-mins[1]-2*margin+gap)/(depth+gap))
            if min(nx,ny)<1:continue
            usedx=nx*width+(nx-1)*gap;usedy=ny*depth+(ny-1)*gap
            for fx in (.5,.25,.75,0,1):
                for fy in (.5,.25,.75,0,1):
                    startx=mins[0]+margin+(maxs[0]-mins[0]-2*margin-usedx)*fx+width/2
                    starty=mins[1]+margin+(maxs[1]-mins[1]-2*margin-usedy)*fy+depth/2
                    accepted=[]
                    for row in range(ny):
                        for col in range(nx):
                            u=startx+col*(width+gap);v=starty+row*(depth+gap)
                            x,y=u*c-v*s,u*s+v*c
                            corners=[((u+dx)*c-(v+dy)*s,(u+dx)*s+(v+dy)*c)
                                     for dx,dy in [(-width/2,-depth/2),(width/2,-depth/2),(width/2,depth/2),(-width/2,depth/2)]]
                            if min(clearance(p,polygon) for p in corners)<margin-1e-6:continue
                            try:
                                ground=floor_z(stage,x,y,area['floorSearchCeiling'])
                                if any(abs(floor_z(stage,*p,area['floorSearchCeiling'])-ground)>.03 for p in corners):continue
                            except RuntimeError:continue
                            blocked=False
                            for face in wall_faces:
                                trimmed=clip(clip(face,ground+.02,True),ground+height,False)
                                if trimmed and not separated(corners,[(p[0],p[1]) for p in trimmed]):
                                    blocked=True;break
                            if not blocked:accepted.append(Gf.Vec3f(x,y,ground-lo[2]*scale[2]))
                    if best is None or len(accepted)>len(best[1]):best=(yaw,accepted)
        if not best or not best[1]:raise RuntimeError('No valid dining placements in '+area['name'])
        plans.append((area,best));print(area['name'],len(best[1]),'tables; minimum grid gap',config['minimumGap'],'m')
    if OUTPUT.exists():out=Usd.Stage.Open(str(OUTPUT));out.GetRootLayer().Clear()
    else:out=Usd.Stage.CreateNew(str(OUTPUT))
    root=UsdGeom.Xform.Define(out,'/Guadalajara').GetPrim();out.SetDefaultPrim(root)
    UsdGeom.SetStageMetersPerUnit(out,1);UsdGeom.SetStageUpAxis(out,UsdGeom.Tokens.z)
    for area,(yaw,positions) in plans:
        inst=UsdGeom.PointInstancer.Define(out,BRANCH+'/'+area['name'])
        proto=UsdGeom.Xform.Define(out,str(inst.GetPath())+'/Prototypes/BenchTable').GetPrim()
        proto.GetReferences().AddReference('../../assets/furniture/comedor_bench_table/comedor_bench_table.usdc')
        inst.CreatePrototypesRel().SetTargets([proto.GetPath()]);inst.CreateProtoIndicesAttr([0]*len(positions))
        inst.CreatePositionsAttr(positions);inst.CreateScalesAttr([scale]*len(positions))
        inst.CreateOrientationsAttr([Gf.Quath(math.cos(yaw/2),0,0,math.sin(yaw/2))]*len(positions))
        inst.CreateIdsAttr(list(range(len(positions))))
        inst.GetPrim().SetCustomDataByKey('sourceMarker',area['sourceMarker'])
        inst.GetPrim().SetCustomDataByKey('minimumGridGapMeters',config['minimumGap'])
    out.GetRootLayer().customLayerData={'generatedBy':'scripts/build_marked_dining.py','layoutStatus':'provisional packing; not a surveyed capacity plan'}
    out.GetRootLayer().Save()
    manifest=Sdf.Layer.FindOrOpen(str(ROOT/'usd/layers/areas/comedores.usda'))
    if OUTPUT.name not in manifest.subLayerPaths:manifest.subLayerPaths.insert(0,OUTPUT.name);manifest.Save()


if __name__=='__main__':main()
