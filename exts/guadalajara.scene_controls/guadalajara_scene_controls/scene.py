"""USD-only scene controls; no dependency on the Kit UI."""
from pxr import Sdf, Usd, UsdGeom

ROOF_PATHS = (
    '/Guadalajara/Architecture/Roof',
    '/Guadalajara/Architecture/Roof_Finishes',
    '/Guadalajara/Architecture/SecondFloor/Cube_012',
)
PERSPECTIVE = '/OmniverseKit_Persp'


def cameras(stage):
    if stage is None:
        return []
    return sorted((str(p.GetPath()) for p in stage.Traverse()
                   if p.IsA(UsdGeom.Camera) and not str(p.GetPath()).startswith('/OmniverseKit_')),
                  key=lambda path: (path.rsplit('/', 1)[-1].casefold(), path))


def camera_label(path):
    parts = path.split('/')
    return parts[-2] if parts[-1].endswith('_DATA') else parts[-1]


class RoofVisibility:
    """Temporary session edits, with exact original visibility-property backup."""
    def __init__(self):
        self.stage = None
        self.backup = None
        self.properties = []

    @property
    def hidden(self):
        return bool(self.properties)

    def hide(self, stage):
        if self.hidden and self.stage == stage:
            return len(self.properties)
        self.restore()
        if stage is None:
            return 0
        targets = [stage.GetPrimAtPath(path) for path in ROOF_PATHS]
        targets = [p for p in targets if p and UsdGeom.Imageable(p)]
        if not targets:
            return 0
        self.stage = stage
        self.backup = Sdf.Layer.CreateAnonymous('roof_visibility_backup')
        session = stage.GetSessionLayer()
        try:
            with Usd.EditContext(stage, session):
                for prim in targets:
                    prop_path = prim.GetPath().AppendProperty('visibility')
                    original = session.GetPropertyAtPath(prop_path)
                    if original:
                        Sdf.CreatePrimInLayer(self.backup, prim.GetPath())
                        Sdf.CopySpec(session, prop_path, self.backup, prop_path)
                        session.GetPrimAtPath(prim.GetPath()).RemoveProperty(original)
                    self.properties.append(prop_path)
                    UsdGeom.Imageable(prim).CreateVisibilityAttr().Set(UsdGeom.Tokens.invisible)
        except Exception:
            self.restore()
            raise
        return len(self.properties)

    def restore(self):
        if self.stage is None:
            return
        session = self.stage.GetSessionLayer()
        for path in self.properties:
            current = session.GetPropertyAtPath(path)
            # Respect a later user edit to this visibility attribute.
            if current is None or current.default != UsdGeom.Tokens.invisible:
                continue
            if session.ListTimeSamplesForPath(path):
                continue
            session.GetPrimAtPath(path.GetPrimPath()).RemoveProperty(current)
            if self.backup.GetPropertyAtPath(path):
                Sdf.CopySpec(self.backup, path, session, path)
        self.stage = None
        self.backup = None
        self.properties = []
