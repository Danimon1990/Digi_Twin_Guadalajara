"""Run with a pxr-enabled Python (or Blender --background --python ... -- FILE)."""
import importlib.util
import json
from pathlib import Path
import sys

from pxr import Usd, UsdGeom

repo = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('replay', repo / 'exts/guadalajara.scene_controls/guadalajara_scene_controls/replay.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Replay, ROOT = module.Replay, module.ROOT

args = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
data = json.loads(Path(args[0]).read_text(encoding='utf-8'))
stage = Usd.Stage.Open(str(repo/'usd/guadalajara_base.usda'))
root_before = stage.GetRootLayer().ExportToString()
session_before = stage.GetSessionLayer().ExportToString()
target_before = stage.GetEditTarget().GetLayer()
replay = Replay(stage,data)
try:
    worker = next(w for w in data['workers'] if w['moves'])
    index = data['workers'].index(worker)+1
    start,end,p,q = worker['moves'][0]
    replay.seek((start+end)/2)
    actor = stage.GetPrimAtPath(f'{ROOT}/Worker_{index}')
    xyz = UsdGeom.Xformable(actor).GetOrderedXformOps()[0].Get()
    assert all(abs(xyz[i]-(p[i]+q[i])/2)<1e-6 for i in (0,1))
    assert abs(xyz[2]-data['floor_z_m'])<1e-6
    finished = replay.seek(replay.duration)['completed']
    assert len(finished) == sum(e['activity']=='service_completed' for e in data['events'])
    assert not replay.seek(0)['completed']
    assert stage.GetEditTarget().GetLayer() == target_before
finally:
    replay.close()
assert not stage.GetPrimAtPath(ROOT)
assert stage.GetRootLayer().ExportToString() == root_before
assert stage.GetSessionLayer().ExportToString() == session_before
print(f'ISAAC_REPLAY_USD_OK: {len(data["workers"])} workers, {len(finished)} completed services, no saved-stage changes.')
