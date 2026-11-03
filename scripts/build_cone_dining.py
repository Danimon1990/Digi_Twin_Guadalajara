"""Add reduced table/bench point instances at saved cone marker positions.

Markers remain editable; their Z is ignored in favour of the actual floor below.
The dedicated layer can be regenerated after moving the cones and saving.
"""
from pathlib import Path
from pxr import Gf, Sdf, Usd, UsdGeom

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'usd/layers/areas/cone_dining.usda'
BRANCH = '/Guadalajara/Areas/Comedores/Stations/Furniture/ConeDining'


def floor_z(stage, x, y, ceiling):
    hits=[];cache=UsdGeom.XformCache()
    root=stage.GetPrimAtPath('/Guadalajara/Architecture/Floors')
    for prim in Usd.PrimRange(root):
        if not prim.IsA(UsdGeom.Mesh):continue
        mesh=UsdGeom.Mesh(prim);matrix=cache.GetLocalToWorldTransform(prim)
        points=[matrix.Transform(Gf.Vec3d(*p)) for p in mesh.GetPointsAttr().Get()]
        indices=mesh.GetFaceVertexIndicesAttr().Get();offset=0
        for count in mesh.GetFaceVertexCountsAttr().Get():
            face=[points[i] for i in indices[offset:offset+count]];offset+=count
            for i in range(1,len(face)-1):
                a,b,c=face[0],face[i],face[i+1]
                denominator=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
                if abs(denominator)<1e-10:continue
                u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/denominator
                v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/denominator
                if min(u,v,1-u-v)<-1e-6:continue
                z=u*a[2]+v*b[2]+(1-u-v)*c[2]
                if z<=ceiling: hits.append(z)
    if not hits:raise RuntimeError(f'No floor under marker at {x}, {y}')
    return max(hits)


def main():
    source=Usd.Stage.Open(str(ROOT/'usd/guadalajara_base.usda'));cache=UsdGeom.XformCache()
    markers=[p for p in source.Traverse() if p.GetParent().GetPath()==Sdf.Path('/Guadalajara')
             and (p.IsA(UsdGeom.Cone) or p.GetName()=='Cone' or p.GetName().startswith('Cone_'))]
    if not markers:raise RuntimeError('No saved cone markers found')
    all_marker_paths=[str(p.GetPath()) for p in markers]
    from build_marked_dining import inside_marked_area
    markers=[p for p in markers if not inside_marked_area(*cache.GetLocalToWorldTransform(p).ExtractTranslation()[:2])]
    reference=UsdGeom.PointInstancer(source.GetPrimAtPath('/Guadalajara/Areas/Comedores/Stations/Furniture/DiningSets/MainDining'))
    scale=reference.GetScalesAttr().Get()[0];orientation=reference.GetOrientationsAttr().Get()[0]
    asset=Usd.Stage.Open(str(ROOT/'usd/assets/furniture/comedor_bench_table/comedor_bench_table.usdc'))
    bounds=UsdGeom.BBoxCache(0,['default','render']).ComputeWorldBound(asset.GetDefaultPrim()).ComputeAlignedRange()
    positions=[];paths=[]
    for marker in sorted(markers,key=lambda p:str(p.GetPath())):
        pos=cache.GetLocalToWorldTransform(marker).ExtractTranslation()
        ground=floor_z(source,pos[0],pos[1],pos[2])
        positions.append(Gf.Vec3f(pos[0],pos[1],ground-bounds.GetMin()[2]*scale[2]))
        paths.append(str(marker.GetPath()))
        print(marker.GetPath(),'table centre',positions[-1],'floor',ground)
    if OUTPUT.exists():
        stage=Usd.Stage.Open(str(OUTPUT));stage.GetRootLayer().Clear()
    else:stage=Usd.Stage.CreateNew(str(OUTPUT))
    root=UsdGeom.Xform.Define(stage,'/Guadalajara').GetPrim();stage.SetDefaultPrim(root)
    UsdGeom.SetStageMetersPerUnit(stage,1);UsdGeom.SetStageUpAxis(stage,UsdGeom.Tokens.z)
    inst=UsdGeom.PointInstancer.Define(stage,BRANCH)
    prototype=UsdGeom.Xform.Define(stage,BRANCH+'/Prototypes/BenchTable').GetPrim()
    prototype.GetReferences().AddReference('../../assets/furniture/comedor_bench_table/comedor_bench_table.usdc')
    inst.CreatePrototypesRel().SetTargets([prototype.GetPath()]);inst.CreateProtoIndicesAttr([0]*len(positions))
    inst.CreatePositionsAttr(positions);inst.CreateScalesAttr([scale]*len(positions))
    inst.CreateOrientationsAttr([orientation]*len(positions));inst.CreateIdsAttr(list(range(len(positions))))
    inst.GetPrim().CreateAttribute('userProperties:sourceMarkers',Sdf.ValueTypeNames.StringArray).Set(paths)
    for path in all_marker_paths:
        marker=stage.OverridePrim(path)
        UsdGeom.Imageable(marker).CreateVisibilityAttr().Set(UsdGeom.Tokens.invisible)
    stage.GetRootLayer().customLayerData={'generatedBy':'scripts/build_cone_dining.py'}
    stage.GetRootLayer().Save()
    manifest=Sdf.Layer.FindOrOpen(str(ROOT/'usd/layers/areas/comedores.usda'))
    if OUTPUT.name not in manifest.subLayerPaths:
        manifest.subLayerPaths.insert(0,OUTPUT.name);manifest.Save()


if __name__=='__main__':main()
