"""Enable adaptive exposure on the actual active Isaac Sim viewport camera.

Run this file in Isaac Sim's Script Editor while Perspective is selected.
Changes go into the session layer, so they override stale viewport opinions
without saving unrelated scene edits or moving the camera.
"""
from pxr import Sdf, Usd


def configure_camera(stage, camera_path):
    camera = stage.GetPrimAtPath(camera_path)
    if not camera:
        raise RuntimeError(f'Viewport camera does not exist: {camera_path}')
    camera.AddAppliedSchema('OmniRtxCameraAutoExposureAPI_1')
    camera.AddAppliedSchema('OmniRtxCameraExposureAPI_1')
    for name, kind, value in (
        ('omni:rtx:autoExposure:enabled', Sdf.ValueTypeNames.Bool, True),
        # Include dark interior pixels in exposure metering.
        ('omni:rtx:autoExposure:histogramClamping:enabled', Sdf.ValueTypeNames.Bool, False),
        ('exposure', Sdf.ValueTypeNames.Float, 0.0),
    ):
        camera.CreateAttribute(name, kind, custom=name.startswith('omni:')).Set(value)
    return str(camera.GetPath())


def main():
    from omni.kit.viewport.utility import get_active_viewport
    viewport = get_active_viewport()
    if viewport is None or viewport.stage is None:
        raise RuntimeError('Open the scene and select the Perspective viewport first')
    stage = viewport.stage
    with Usd.EditContext(stage, stage.GetSessionLayer()):
        path = configure_camera(stage, viewport.camera_path)
    print(f'Auto exposure enabled on active viewport camera: {path}. Allow a few seconds to adapt.')


if __name__ == '__main__':
    main()
