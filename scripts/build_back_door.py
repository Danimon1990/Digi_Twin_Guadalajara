"""Fit a neutral door assembly into WALL_002's existing back-door opening.

Local opening limits measured from the evaluated wall's jamb/header vertices.
No wall geometry or existing material definitions are changed. Rotate the
HingedLeaf rotateZ operation to pose the door; no physics is authored.
"""
from pathlib import Path
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'usd/layers/architecture/back_door.usda'
WALL='/Guadalajara/Architecture/Walls/WALL_002'
DOOR=WALL+'/BackDoor'
# Conservative opening bounds shared by both wall faces, in WALL_002 space.
LEFT, RIGHT, BOTTOM, TOP = 5.8890, 6.8733, -1.1, .9437
PAINT='/Guadalajara/Materials/MAT_Wall_Paint_White'
METAL='/Guadalajara/Materials/MAT_Equipment_Stainless_Steel'


def main():
    source=Usd.Stage.Open(str(ROOT/'usd/guadalajara_base.usda'))
    assert source.GetPrimAtPath(WALL+'/Cube_002').IsA(UsdGeom.Mesh)
    for path in (PAINT,METAL):
        assert source.GetPrimAtPath(path).IsA(UsdShade.Material),path
    if OUTPUT.exists():stage=Usd.Stage.Open(str(OUTPUT));stage.GetRootLayer().Clear()
    else:stage=Usd.Stage.CreateNew(str(OUTPUT))
    root=UsdGeom.Xform.Define(stage,'/Guadalajara').GetPrim();stage.SetDefaultPrim(root)
    UsdGeom.SetStageMetersPerUnit(stage,1);UsdGeom.SetStageUpAxis(stage,UsdGeom.Tokens.z)
    assembly=UsdGeom.Xform.Define(stage,DOOR)
    assembly.AddTranslateOp().Set(Gf.Vec3d((LEFT+RIGHT)/2,0,BOTTOM))
    assembly.GetPrim().SetCustomDataByKey('sourceOpening','OPENING_DOOR_WALL_002_01')
    assembly.GetPrim().SetCustomDataByKey('dimensionsStatus','fitted to existing provisional opening')
    width,height=RIGHT-LEFT,TOP-BOTTOM
    def box(path,location,dimensions,material):
        cube=UsdGeom.Cube.Define(stage,path);cube.CreateSizeAttr(1)
        cube.AddTranslateOp().Set(Gf.Vec3d(*location));cube.AddScaleOp().Set(Gf.Vec3f(*dimensions))
        binding=UsdShade.MaterialBindingAPI.Apply(cube.GetPrim())
        binding.GetDirectBindingRel().SetTargets([Sdf.Path(material)])
        return cube
    for name,sign in [('LeftJamb',-1),('RightJamb',1)]:
        box(DOOR+'/'+name,(sign*(width-.045)/2,0,height/2),(.045,.10,height),PAINT)
    box(DOOR+'/Header',(0,0,height-.0225),(width,.10,.045),PAINT)
    box(DOOR+'/Threshold',(0,0,.0075),(width,.11,.015),METAL)
    leaf_width=width-.106;leaf_height=height-.078
    pivot=UsdGeom.Xform.Define(stage,DOOR+'/HingedLeaf')
    pivot.AddTranslateOp().Set(Gf.Vec3d(-width/2+.053,0,.025))
    pivot.AddRotateZOp().Set(0)
    box(str(pivot.GetPath())+'/Panel',(leaf_width/2,0,leaf_height/2),(leaf_width,.04,leaf_height),PAINT)
    for side in (-1,1):
        suffix='Inside' if side<0 else 'Outside'
        box(str(pivot.GetPath())+'/HandlePlate'+suffix,(leaf_width-.09,side*.024,.98),(.045,.008,.16),METAL)
        box(str(pivot.GetPath())+'/HandleStem'+suffix,(leaf_width-.09,side*.045,.99),(.02,.04,.02),METAL)
        box(str(pivot.GetPath())+'/Lever'+suffix,(leaf_width-.145,side*.065,.99),(.13,.02,.022),METAL)
    for index,z in enumerate((.22,height/2,height-.22),1):
        hinge=UsdGeom.Cylinder.Define(stage,DOOR+f'/Hinge{index}')
        hinge.CreateRadiusAttr(.012);hinge.CreateHeightAttr(.09);hinge.CreateAxisAttr('Z')
        hinge.AddTranslateOp().Set(Gf.Vec3d(-width/2+.05,.027,z))
        UsdShade.MaterialBindingAPI.Apply(hinge.GetPrim()).GetDirectBindingRel().SetTargets([Sdf.Path(METAL)])
    stage.GetRootLayer().customLayerData={'generatedBy':'scripts/build_back_door.py'}
    stage.GetRootLayer().Save()
    manifest=Sdf.Layer.FindOrOpen(str(ROOT/'usd/layers/architecture.usda'))
    relative='architecture/back_door.usda'
    if relative not in manifest.subLayerPaths:manifest.subLayerPaths.insert(0,relative);manifest.Save()
    print('BACK_DOOR_CREATED',DOOR,'local opening',width,height)


if __name__=='__main__':main()
