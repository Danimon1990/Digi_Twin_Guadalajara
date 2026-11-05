# Guadalajara Scene Controls

A small Isaac Sim / Omniverse Kit extension for reviewing this scene.

- **Hide roof / Show roof:** hides Roof, Roof_Finishes and the second-floor slab
  over the downstairs rooms. Restores the original visibility on Show, stage
  switch, or extension shutdown. Writes only temporary session visibility.
- **Camera buttons:** discovers every active USD Camera in the current viewport's
  stage, including newly created cameras. The list refreshes automatically once
  per second; Refresh cameras updates it immediately. Full paths appear in tooltips.
- **Perspective:** returns to the normal free-navigation Perspective view.
- Reopen the panel from **Window > Guadalajara Scene Controls**.

Camera switching uses the existing camera transforms and exposure settings.
It does not reposition cameras, change their exposure, or save the scene.

## Enable in the running app

Run this in Isaac Sim's Script Editor:

```python
import runpy
runpy.run_path('/home/daniel/Documents/Guadalajara/Digi_Twin_Guadalajara/scripts/enable_scene_controls.py', run_name='__main__')
```

For future sessions, add the following extension search folder in the Extension
Manager settings, then find **Guadalajara Scene Controls** and enable it:

```text
/home/daniel/Documents/Guadalajara/Digi_Twin_Guadalajara/exts
```

Choose the parent `exts` folder, not the individual extension directory. Enable
Autoload in the Extension Manager if you want it to start with Isaac Sim.

## Validation

The USD logic has five automated tests covering dynamic camera discovery,
roof toggles, preservation of session visibility animation, stage switching,
subsequent user visibility edits, and the actual Guadalajara stage. Run:

```bash
/home/daniel/scene-venv/bin/python -m unittest discover -s tests/scene_controls -v
```

Live UI validation still requires Isaac Sim: enable the extension, click each
camera, return to Perspective, hide/show the roof, create another camera, and
confirm it appears. Disable the extension while the roof is hidden to confirm
restoration. No live Isaac Sim UI test has been performed in this environment.

## Extending the panel

`guadalajara_scene_controls/scene.py` contains USD-only scene operations.
`extension.py` owns the Kit panel, viewport changes, menu and subscriptions.
Add further controls without coupling scene logic to UI callbacks.

API references:
- [Viewport camera controls](https://docs.omniverse.nvidia.com/dev-guide/latest/programmer_ref/viewport/camera.html)
- [Built-in Perspective viewport camera](https://docs.omniverse.nvidia.com/kit/docs/omni.kit.viewport.docs/109.0.0/viewport_api.html)

## SimPy in 3D (experimental)

1. In the local dispatch lab, run a simulation with **Flexible** movement.
   Download **Descargar para Isaac Sim** from the run history. For an existing
   spatial run, use `python -m operations.adapters.isaac_replay /path/to/events.sqlite3 /path/to/isaac_replay.json`.
   Add `--run-id` when the database contains multiple runs.
2. Copy the JSON to the computer running Isaac Sim. Use the same repository
   revision for the scene and extension. Open `usd/guadalajara_base.usda`.
3. Enable **Guadalajara Scene Controls** as described above. If it was already
   enabled before updating the files, disable and re-enable it.
4. Use **Hide roof** and choose a top or angled camera. Click **SimPy 3D**,
   paste the local JSON path into the text field, click **Cargar JSON**, then
   **Play**. Use the slider to scrub, **Velocidad ×** to change playback speed,
   or **Quitar** to remove the overlay.

To generate a demo directly on Linux without starting the web lab, run these
commands from the repository root with Python 3.11 or newer:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python - <<'PYTHON'
from pathlib import Path
from uuid import uuid4
from operations.experiments import run_experiment

out = Path("outputs/operations/isaac_demo") / uuid4().hex[:8]
run_experiment({"servers": 4, "minutes": 12, "orders": 10, "seed": 42}, out)
print((out / "isaac_replay.json").resolve())
PYTHON
```

Paste the printed path into **SimPy 3D**. The virtual environment is only for
generating the run; Isaac Sim uses its own Python runtime.

The panel shows simulation time, worker count, queue and completion counts,
mean service time for completed orders, and the assigned customer's elapsed
service time and current task for each worker. The 3D figures replay recorded
worker XY movement in meters. Their body shapes, heading, and baskets are
visual proxies. Customer state is shown in the panel; no customer routes,
arm animation, collisions, or physics are inferred.

SimPy runs outside Isaac Sim. The extension consumes JSON with no SimPy or
database dependency and writes only an anonymous USD session sublayer. Unload
the replay, switch stages, or disable the extension to remove it. Do not use a
stale geometry snapshot to draw conclusions about the current layout.

To verify the USD behavior without the Kit UI:

```bash
./python.sh /path/to/repo/scripts/validate_isaac_replay.py /path/to/isaac_replay.json
```

This checks interpolation against recorded coordinates, the completed-service
count, rewind, and cleanup against the canonical USD stage. The interactive
panel still needs a smoke test in Isaac Sim.
