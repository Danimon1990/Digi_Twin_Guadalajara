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
