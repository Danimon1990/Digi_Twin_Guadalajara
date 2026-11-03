"""Author USD daylight and renderer-facing interior exposure, repeatably.

The exposure is an absolute setting, not a cumulative brightness multiplier.
These are presentation defaults; final appearance depends on viewport exposure.
"""
from pathlib import Path
from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux

ROOT = Path(__file__).resolve().parents[1] / 'usd'
INTERIOR_EXPOSURE = 4.0  # 16x exported Blender power in USD renderers.
CAMERA_EXPOSURE = 4.0  # Additional camera compensation for the saved dark interior view.


def main():
    interior = Usd.Stage.Open(str(ROOT / 'layers/lighting/interior.usda'))
    count = 0
    for prim in interior.Traverse():
        if prim.IsA(UsdLux.RectLight):
            UsdLux.LightAPI(prim).CreateExposureAttr(INTERIOR_EXPOSURE)
            count += 1
    if not count:
        raise RuntimeError('No interior emitters found')
    interior.GetRootLayer().Save()

    path = ROOT / 'layers/lighting/daylight.usda'
    if path.exists():
        stage = Usd.Stage.Open(str(path))
        stage.GetRootLayer().Clear()
    else:
        stage = Usd.Stage.CreateNew(str(path))
    root = UsdGeom.Xform.Define(stage, '/Guadalajara').GetPrim()
    stage.SetDefaultPrim(root)
    UsdGeom.SetStageMetersPerUnit(stage, 1)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.Xform.Define(stage, '/Guadalajara/Lighting/Daylight')
    sun = UsdLux.DistantLight.Define(stage, '/Guadalajara/Lighting/Daylight/Sun')
    sun.CreateIntensityAttr(2500)
    sun.CreateAngleAttr(1.0)
    sun.CreateColorAttr(Gf.Vec3f(1.0, .95, .86))
    # USD distant lights emit along local -Z: oblique downward afternoon sun.
    UsdGeom.Xformable(sun).AddRotateXYZOp().Set(Gf.Vec3f(35, -25, -30))
    sky = UsdLux.DomeLight.Define(stage, '/Guadalajara/Lighting/Daylight/SkyFill')
    sky.CreateIntensityAttr(250)
    sky.CreateColorAttr(Gf.Vec3f(.78, .87, 1.0))
    stage.GetRootLayer().customLayerData = {
        'generatedBy': 'scripts/build_stage_daylight.py',
        'lightingPurpose': 'sunlight and soft sky fill; provisional presentation values',
    }
    stage.GetRootLayer().Save()

    # Edit only the sublayer list; retain authored materials, cameras and prims.
    layer = Sdf.Layer.FindOrOpen(str(ROOT / 'guadalajara_base.usda'))
    relative = 'layers/lighting/daylight.usda'
    if relative not in layer.subLayerPaths:
        layer.subLayerPaths.insert(0, relative)
        layer.Save()
    camera_stage = Usd.Stage.Open(str(ROOT / 'guadalajara_base.usda'))
    for camera_path in ('/OmniverseKit_Persp', '/Guadalajara/Camera'):
        camera = camera_stage.GetPrimAtPath(camera_path)
        if not camera:
            continue
        camera.CreateAttribute('exposure', Sdf.ValueTypeNames.Float, custom=False).Set(CAMERA_EXPOSURE)
        camera.CreateAttribute('omni:rtx:autoExposure:enabled', Sdf.ValueTypeNames.Bool, custom=True).Set(False)
    # Perspective navigation needs adaptive exposure between indoors and outdoors.
    from enable_perspective_visibility import configure_camera
    if camera_stage.GetPrimAtPath('/OmniverseKit_Persp'):
        configure_camera(camera_stage, '/OmniverseKit_Persp')
    camera_stage.GetRootLayer().Save()
    print(f'DAYLIGHT_OK: sun + sky fill; {count} interior emitters at +{INTERIOR_EXPOSURE:g} stops')


if __name__ == '__main__':
    main()
