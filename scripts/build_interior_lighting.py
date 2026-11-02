"""Create repeatable review lighting beneath existing ceilings, without altering geometry.

Run in the current Blender scene; call main(save=True) explicitly to save.
Positions and powers are presentation assumptions, never surveyed fixture locations.
"""
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

COLLECTION = 'Lighting_Interior_Review'
ZONES = ['DESPACHO', 'COCINA', 'COMEDORES', 'PATIO', 'BEBIDAS',
         'ALMACEN', 'NEVERAS', 'CUARTO_DE_OLLAS', 'BANO_EMPLEADOS',
         'BANO_HOMBRES', 'BANO_MUJERES', 'BASURAS']


def main(save=False):
    collection = bpy.data.collections.get(COLLECTION)
    if collection is None:
        collection = bpy.data.collections.new(COLLECTION)
        bpy.context.scene.collection.children.link(collection)
    deps = bpy.context.evaluated_depsgraph_get()
    shells = set()
    for name in ['Roof', 'Roof_Finishes', 'Floors']:
        c = bpy.data.collections.get(name)
        if c:
            shells.update(o for o in c.all_objects if o.type == 'MESH')
    vertices, faces = [], []
    for o in shells:
        evaluated = o.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        offset = len(vertices)
        vertices.extend(o.matrix_world @ v.co for v in mesh.vertices)
        faces.extend(tuple(offset + i for i in p.vertices) for p in mesh.polygons)
        evaluated.to_mesh_clear()
    ceilings = BVHTree.FromPolygons(vertices, faces)
    report = []
    for zone in ZONES:
        guide = bpy.data.objects.get('FLOOR_' + zone)
        if guide is None:
            continue
        for i, polygon in enumerate(guide.data.polygons):
            if polygon.normal.z < .5:
                continue
            center = guide.matrix_world @ polygon.center
            hit, normal, face, distance = ceilings.ray_cast(Vector((center.x, center.y, 1.8)), Vector((0, 0, 1)), 10)
            z = min(3.0, hit.z - .15) if hit is not None else 2.5
            if z < 1.9:
                raise RuntimeError('Unexpected low ceiling at ' + zone)
            name = f'LIGHT_Interior_{zone}_{i+1:02d}'
            obj = bpy.data.objects.get(name)
            if obj is None:
                light = bpy.data.lights.new(name, 'AREA')
                obj = bpy.data.objects.new(name, light)
                collection.objects.link(obj)
            elif obj.type != 'LIGHT' or obj not in collection.objects.values():
                raise RuntimeError('Existing unrelated object uses managed name: ' + name)
            light = obj.data
            light.type = 'AREA'
            light.shape = 'DISK'
            light.size = 1.2
            # Broad modest fills; no claim of photometric calibration.
            light.energy = 500 if zone in ['DESPACHO', 'COCINA', 'COMEDORES', 'PATIO'] else 120
            light.color = (1.0, .93, .84)
            obj.location = (center.x, center.y, z)
            obj.rotation_euler = (0, 0, 0)  # area lights emit along local -Z
            obj['reviewOnly'] = True
            obj['lightingZone'] = zone
            obj['placementEvidence'] = 'assumed presentation helper; below existing evaluated ceiling'
            obj['ceilingHitZ'] = hit.z if hit is not None else -1.0
            report.append({'name': name, 'location': list(obj.location), 'ceiling_z': hit.z if hit is not None else None, 'watts': light.energy})
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    return report


if __name__ == '__main__':
    print(main(save=True))
