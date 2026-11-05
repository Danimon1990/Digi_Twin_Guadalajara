import time
from functools import partial

import carb
import omni.ext
import omni.kit.app
import omni.ui as ui
from omni.kit.menu.utils import MenuItemDescription, add_menu_items, remove_menu_items
from omni.kit.viewport.utility import get_active_viewport
from pxr import UsdGeom

from .replay_panel import ReplayPanel
from .scene import PERSPECTIVE, RoofVisibility, camera_label, cameras

TITLE = 'Guadalajara Scene Controls'


class Extension(omni.ext.IExt):
    def on_startup(self, ext_id):
        self._roof = RoofVisibility()
        self._replay_panel = ReplayPanel(self._viewport)
        self._stage = None
        self._paths = []
        self._last_poll = 0
        self._window = ui.Window(TITLE, width=380, height=480)
        with self._window.frame:
            with ui.VStack(spacing=8):
                ui.Label('Guadalajara', height=28)
                ui.Button('SimPy 3D', height=30, clicked_fn=self._replay_panel.show)
                self._roof_button = ui.Button('Hide roof', height=34, clicked_fn=self._toggle_roof,
                                              tooltip='Roof, roof finishes, and overhead second-floor slab')
                with ui.HStack(height=32, spacing=6):
                    ui.Button('Perspective', clicked_fn=partial(self._switch, PERSPECTIVE))
                    ui.Button('Refresh cameras', clicked_fn=self._refresh)
                self._active = ui.Label('Open a scene in a viewport.', height=36, word_wrap=True)
                with ui.ScrollingFrame():
                    self._camera_frame = ui.Frame()
                self._status = ui.Label('Roof visibility changes are temporary.', height=42, word_wrap=True)
        self._menu = [MenuItemDescription(name=TITLE, onclick_fn=self._show)]
        add_menu_items(self._menu, 'Window')
        self._update_subscription = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
            self._on_update, name='Guadalajara scene controls')
        self._refresh()

    def _show(self):
        self._window.visible = True
        self._refresh()

    def _viewport(self):
        return get_active_viewport()

    def _refresh(self):
        viewport = self._viewport()
        stage = viewport.stage if viewport else None
        if stage != self._stage:
            self._roof.restore()
            self._stage = stage
        self._paths = cameras(stage)
        self._build_camera_buttons()
        self._sync(viewport)

    def _build_camera_buttons(self):
        self._camera_frame.clear()
        with self._camera_frame:
            with ui.VStack(spacing=5, height=0):
                if not self._paths:
                    ui.Label('No scene cameras found.', height=28)
                labels = [camera_label(path) for path in self._paths]
                for path, label in zip(self._paths, labels):
                    if labels.count(label) > 1:
                        label = path
                    ui.Button(label, height=30, tooltip=path, clicked_fn=partial(self._switch, path))

    def _sync(self, viewport):
        self._roof_button.text = 'Show roof' if self._roof.hidden else 'Hide roof'
        self._roof_button.enabled = self._stage is not None
        active = str(viewport.camera_path) if viewport else ''
        label = 'Perspective' if active == PERSPECTIVE else camera_label(active)
        self._active.text = f'Current view: {label}' if active else 'No active viewport.'

    def _on_update(self, event):
        self._replay_panel.update()
        # Poll on Kit's main thread: camera edits may come from any editor/tool.
        if time.monotonic() - self._last_poll < 1:
            return
        self._last_poll = time.monotonic()
        try:
            viewport = self._viewport()
            stage = viewport.stage if viewport else None
            if stage != self._stage or cameras(stage) != self._paths:
                self._refresh()
            else:
                self._sync(viewport)
        except Exception as error:
            self._error(error)

    def _toggle_roof(self):
        try:
            self._refresh()
            if self._roof.hidden:
                self._roof.restore()
                self._status.text = 'Previous roof visibility restored.'
            else:
                count = self._roof.hide(self._stage)
                self._status.text = 'Roof hidden for this session.' if count else 'No Guadalajara roof found in this scene.'
            self._sync(self._viewport())
        except Exception as error:
            self._error(error)

    def _switch(self, path):
        try:
            viewport = self._viewport()
            if viewport is None or viewport.stage is None:
                raise RuntimeError('Open a scene in a viewport first.')
            if path != PERSPECTIVE:
                camera = viewport.stage.GetPrimAtPath(path)
                if not camera or not camera.IsA(UsdGeom.Camera):
                    self._refresh()
                    raise RuntimeError('That camera was removed. Choose another camera.')
            viewport.camera_path = path
            self._status.text = 'Camera changed.'
            self._sync(viewport)
        except Exception as error:
            self._error(error)

    def _error(self, error):
        self._status.text = str(error)
        carb.log_warn(f'{TITLE}: {error}')

    def on_shutdown(self):
        self._update_subscription = None
        self._replay_panel.destroy()
        self._roof.restore()
        remove_menu_items(self._menu, 'Window')
        self._window.destroy()
        self._window = None
        self._stage = None
