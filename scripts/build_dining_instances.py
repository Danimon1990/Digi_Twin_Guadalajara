"""Place reusable table/bench components in both dining rooms as USD points.

Layout is provisional. Floor polygons and surface heights come from the stage;
asset bounds determine grounding and footprint checks. No source meshes copied.
"""
import math
from pathlib import Path
from pxr import Gf, Sdf, Usd, UsdGeom, Vt

ROOT = Path(__file__).resolve().parents[1]
LAYER = ROOT / 'usd/layers/areas/dining_instances.usda'
ASSET = ROOT / 'usd/assets/furniture/comedor_bench_table/comedor_bench_table.usdc'
BRANCH = '/Guadalajara/Areas/Comedores/Stations/Furniture/DiningSets'
ROOMS = (
    ('MainDining', 'FLOOR_COMEDOR_MAIN_FINISH'),
    ('RaisedDining', 'FLOOR_COMEDOR_RAISED'),
)

TARGET_SHORT_SIDE = 1.25
ROW_COUNT = 3
COLUMNS = (2.2, 5.1, 8.0)
BOUNDARY_CLEARANCE = .32


def row_limits(region, columns, half_width, half_depth):
    """Intersect convex-room halfplanes for all corners of every column.

    Room coordinates have U along the partition and V perpendicular to it.
    Return the range of permissible row centres, retaining boundary clearance.
    """
    lower, upper = -math.inf, math.inf
    for column in columns:
        for dx in (-half_width, half_width):
            for dy in (-half_depth, half_depth):
                for a, b in zip(region, region[1:] + region[:1]):
                    ex, ey = b[0]-a[0], b[1]-a[1]
                    rhs = BOUNDARY_CLEARANCE * math.hypot(ex, ey) + ey*(column+dx-a[0]) - ex*(dy-a[1])
                    if abs(ex) < 1e-9:
                        if rhs > 1e-8:
                            raise RuntimeError('Column footprint does not fit room boundary')
                    elif ex > 0:
                        lower = max(lower, rhs/ex)
                    else:
                        upper = min(upper, rhs/ex)
    if not math.isfinite(lower+upper) or lower >= upper:
        raise RuntimeError('No valid row-centre interval')
    return lower, upper


def hull(points):
    points = sorted(set(points))
    def cross(a,b,c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def half(items):
        result=[]
        for p in items:
            while len(result)>1 and cross(result[-2],result[-1],p)<=0: result.pop()
            result.append(p)
        return result
    return half(points)[:-1]+half(points[::-1])[:-1]


def clearance(point, polygon):
    return min(((b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0]))/math.dist(a,b)
               for a,b in zip(polygon,polygon[1:]+polygon[:1]))


def main():
    source=Usd.Stage.Open(str(ROOT/'usd/guadalajara_base.usda'))
    asset=Usd.Stage.Open(str(ASSET))
    bounds=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render']).ComputeWorldBound(asset.GetDefaultPrim()).ComputeAlignedRange()
    low, high=bounds.GetMin(),bounds.GetMax()
    footprint_scale = TARGET_SHORT_SIDE / (high[0]-low[0])
    scale = Gf.Vec3f(footprint_scale, footprint_scale, 1.0)
    low = Gf.Vec3d(low[0]*scale[0], low[1]*scale[1], low[2])
    high = Gf.Vec3d(high[0]*scale[0], high[1]*scale[1], high[2])
    # Align all sets with the shared dining-room partition, using the floor edge.
    floor=source.GetPrimAtPath('/Guadalajara/Architecture/Floors/FLOOR_COMEDOR_MAIN_FINISH')
    def floor_points(prim):
        points=[];cache=UsdGeom.XformCache()
        for child in Usd.PrimRange(prim):
            if child.IsA(UsdGeom.Mesh):
                matrix=cache.GetLocalToWorldTransform(child)
                points.extend(matrix.Transform(Gf.Vec3d(*p)) for p in UsdGeom.Mesh(child).GetPointsAttr().Get())
        return points
    main_points=floor_points(floor)
    polygon=hull([(p[0],p[1]) for p in main_points])
    a,b=sorted(zip(polygon,polygon[1:]+polygon[:1]),key=lambda edge:(edge[0][1]+edge[1][1])/2)[0]
    if a[0]>b[0]:a,b=b,a
    angle=math.atan2(b[1]-a[1],b[0]-a[0]);u=(math.cos(angle),math.sin(angle));v=(-u[1],u[0])
    yaw=angle+math.pi/2
    cs,sn=math.cos(yaw),math.sin(yaw)
    planned=[]
    for name,floor_name in ROOMS:
        points=floor_points(source.GetPrimAtPath('/Guadalajara/Architecture/Floors/'+floor_name))
        region=hull([(p[0],p[1]) for p in points]);surface=max(p[2] for p in points)
        local_region = hull([((p[0]-a[0])*u[0]+(p[1]-a[1])*u[1],
                              (p[0]-a[0])*v[0]+(p[1]-a[1])*v[1]) for p in region])
        start, end = row_limits(local_region, COLUMNS, (high[1]-low[1])/2, (high[0]-low[0])/2)
        pitch = (end-start)/(ROW_COUNT-1)
        gap = pitch - (high[0]-low[0])
        if gap < .25:
            raise RuntimeError(f'{name}: three-row trial leaves less than 0.25 m between sets')
        rows = [start + i*pitch for i in range(ROW_COUNT)]
        positions=[]
        for row in rows:
            for column in COLUMNS:
                x=a[0]+u[0]*column+v[0]*row;y=a[1]+u[1]*column+v[1]*row
                corners=[(x+cs*i-sn*j,y+sn*i+cs*j) for i in (low[0],high[0]) for j in (low[1],high[1])]
                margin=min(clearance(p,region) for p in corners)
                if margin<.30:raise RuntimeError(f'{name}: footprint too close to boundary ({margin:.3f}m)')
                positions.append(Gf.Vec3f(x,y,surface-low[2]))
        planned.append((name,positions,surface,gap))
    if LAYER.exists():
        stage=Usd.Stage.Open(str(LAYER));stage.GetRootLayer().Clear()
    else:
        stage=Usd.Stage.CreateNew(str(LAYER))
    root=UsdGeom.Xform.Define(stage,'/Guadalajara').GetPrim();stage.SetDefaultPrim(root)
    UsdGeom.SetStageMetersPerUnit(stage,1);UsdGeom.SetStageUpAxis(stage,UsdGeom.Tokens.z)
    for name,positions,surface,gap in planned:
        inst=UsdGeom.PointInstancer.Define(stage,BRANCH+'/'+name)
        prototype=UsdGeom.Xform.Define(stage,str(inst.GetPath())+'/Prototypes/BenchTable').GetPrim()
        prototype.GetReferences().AddReference('../../assets/furniture/comedor_bench_table/comedor_bench_table.usdc')
        inst.CreatePrototypesRel().SetTargets([prototype.GetPath()])
        inst.CreateProtoIndicesAttr([0]*len(positions));inst.CreatePositionsAttr(positions)
        inst.CreateOrientationsAttr([Gf.Quath(math.cos(yaw/2),0,0,math.sin(yaw/2))]*len(positions))
        inst.CreateIdsAttr(list(range(len(positions))))
        inst.CreateScalesAttr([scale]*len(positions))
        inst.GetPrim().SetCustomDataByKey('layoutStatus','three-row visual trial; reduced footprint, original heights; narrow row gaps')
        inst.GetPrim().SetCustomDataByKey('floorSurfaceZ',surface)
        inst.GetPrim().SetCustomDataByKey('rowGapMeters',gap)
        inst.GetPrim().SetCustomDataByKey('footprintMeters',Gf.Vec2d(high[0]-low[0],high[1]-low[1]))
        print(name,len(positions),'sets; footprint',high[0]-low[0],high[1]-low[1],'row gap',round(gap,3),'m; floor Z',surface)
    stage.GetRootLayer().customLayerData={'generatedBy':'scripts/build_dining_instances.py'}
    stage.GetRootLayer().Save()
    manifest=Sdf.Layer.FindOrOpen(str(ROOT/'usd/layers/areas/comedores.usda'))
    if 'dining_instances.usda' not in manifest.subLayerPaths:
        manifest.subLayerPaths.insert(0,'dining_instances.usda');manifest.Save()


if __name__=='__main__':main()
