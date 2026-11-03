import importlib.util
from pathlib import Path
import unittest
from pxr import Sdf, Usd, UsdGeom

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT/'exts/guadalajara.scene_controls/guadalajara_scene_controls/scene.py'
spec = importlib.util.spec_from_file_location('scene_controls_core', MODULE)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class SceneControlsTests(unittest.TestCase):
    def make_stage(self):
        stage = Usd.Stage.CreateInMemory()
        for path in core.ROOF_PATHS:
            UsdGeom.Xform.Define(stage, path)
        UsdGeom.Xform.Define(stage, '/Guadalajara/Architecture/Walls')
        return stage

    def test_camera_discovery_tracks_added_removed_and_duplicate_names(self):
        stage = self.make_stage()
        for path in ['/A/Camera', '/B/Camera', '/Guadalajara/Patio', core.PERSPECTIVE]:
            UsdGeom.Camera.Define(stage, path)
        self.assertEqual(len(core.cameras(stage)), 3)
        stage.RemovePrim('/A/Camera')
        UsdGeom.Camera.Define(stage, '/Guadalajara/NewCamera')
        self.assertIn('/Guadalajara/NewCamera', core.cameras(stage))
        self.assertNotIn('/A/Camera', core.cameras(stage))
        self.assertEqual(core.cameras(None), [])

    def test_roof_hide_restore_does_not_change_root_or_walls(self):
        stage = self.make_stage()
        original = stage.GetRootLayer().ExportToString()
        roof = core.RoofVisibility()
        self.assertEqual(roof.hide(stage), 3)
        self.assertEqual(roof.hide(stage), 3)
        for path in core.ROOF_PATHS:
            self.assertEqual(UsdGeom.Imageable(stage.GetPrimAtPath(path)).ComputeVisibility(), 'invisible')
        self.assertEqual(UsdGeom.Imageable(stage.GetPrimAtPath('/Guadalajara/Architecture/Walls')).ComputeVisibility(), 'inherited')
        roof.restore()
        for path in core.ROOF_PATHS:
            self.assertEqual(UsdGeom.Imageable(stage.GetPrimAtPath(path)).ComputeVisibility(), 'inherited')
        self.assertEqual(stage.GetRootLayer().ExportToString(), original)
        self.assertFalse(roof.hidden)

    def test_original_session_animation_is_restored(self):
        stage = self.make_stage()
        path = core.ROOF_PATHS[0]
        with Usd.EditContext(stage, stage.GetSessionLayer()):
            attr = UsdGeom.Imageable(stage.GetPrimAtPath(path)).CreateVisibilityAttr()
            attr.Set('inherited')
            attr.Set('invisible', 5)
        original = stage.GetSessionLayer().GetPropertyAtPath(path+'.visibility')
        expected = dict(original.ListInfoKeys() and [(key, original.GetInfo(key)) for key in original.ListInfoKeys()])
        roof = core.RoofVisibility();roof.hide(stage);roof.restore()
        restored = stage.GetSessionLayer().GetPropertyAtPath(path+'.visibility')
        self.assertEqual({key: restored.GetInfo(key) for key in restored.ListInfoKeys()}, expected)

    def test_stage_switch_and_later_user_edit(self):
        first, second = self.make_stage(), self.make_stage()
        roof = core.RoofVisibility();roof.hide(first);roof.hide(second)
        self.assertEqual(UsdGeom.Imageable(first.GetPrimAtPath(core.ROOF_PATHS[0])).ComputeVisibility(), 'inherited')
        with Usd.EditContext(second, second.GetSessionLayer()):
            UsdGeom.Imageable(second.GetPrimAtPath(core.ROOF_PATHS[0])).GetVisibilityAttr().Set('inherited')
        roof.restore()
        self.assertEqual(second.GetSessionLayer().GetPropertyAtPath(core.ROOF_PATHS[0]+'.visibility').default, 'inherited')

    def test_actual_scene_round_trip(self):
        stage = Usd.Stage.Open(str(ROOT/'usd/guadalajara_base.usda'))
        before = stage.GetRootLayer().ExportToString()
        for name in ('Fachada_frente','Despacho','Sopas','Patio','Cocina','Almacen','Comedor'):
            self.assertIn('/Guadalajara/'+name, core.cameras(stage))
        roof = core.RoofVisibility();self.assertEqual(roof.hide(stage), 3);roof.restore()
        self.assertEqual(stage.GetRootLayer().ExportToString(), before)


if __name__ == '__main__':
    unittest.main()
