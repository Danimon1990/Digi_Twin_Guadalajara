"""Run this file in Isaac Sim's Script Editor to enable the local extension."""
from pathlib import Path
import omni.kit.app

# Script Editor may not supply __file__; the current workspace is the fallback.
ROOT = (Path(__file__).resolve().parents[1] if '__file__' in globals()
        else Path('/home/daniel/Documents/Guadalajara/Digi_Twin_Guadalajara'))
manager = omni.kit.app.get_app().get_extension_manager()
manager.add_path(str(ROOT / 'exts'))
if not manager.set_extension_enabled_immediate('guadalajara.scene_controls', True):
    raise RuntimeError('Could not enable Guadalajara Scene Controls; check the Isaac Sim console.')
print('Guadalajara Scene Controls enabled. Reopen via Window > Guadalajara Scene Controls.')
