"""Build neutral-white tubular fixtures beneath the evaluated room ceilings.

Positions are provisional, derived from room guides, with at most 3 m spacing.
Run in Blender; main(save=True) saves the editable fixtures and emitters.
"""
import math
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

COLLECTION = 'Lighting_Interior_Review'
ZONES = ['DESPACHO', 'COCINA', 'COMEDORES', 'PATIO', 'BEBIDAS',
         'ALMACEN', 'NEVERAS', 'CUARTO_DE_OLLAS', 'BANO_EMPLEADOS',
         'BANO_HOMBRES', 'BANO_MUJERES', 'BASURAS']


def ceiling_tree():
    deps = bpy.context.evaluated_depsgraph_get()
    shells = set()
    for name in ['Roof', 'Roof_Finishes', 'Floors', 'Level_01_Partial']:
        collection = bpy.data.collections.get(name)
        if collection:
            shells.update(o for o in collection.all_objects if o.type == 'MESH' and not o.hide_render)
    vertices, faces = [], []
    for obj in shells:
        evaluated = obj.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        offset = len(vertices)
        vertices.extend(obj.matrix_world @ v.co for v in mesh.vertices)
        faces.extend(tuple(offset + i for i in p.vertices) for p in mesh.polygons)
        evaluated.to_mesh_clear()
    return BVHTree.FromPolygons(vertices, faces)


def placements(guide):
    """Bilinear grids stay inside the scene's convex quadrilateral room guides."""
    for polygon in guide.data.polygons:
        if polygon.normal.z < .5:
            continue
        points = [guide.matrix_world @ guide.data.vertices[i].co for i in polygon.vertices]
        if len(points) != 4:
            raise ValueError('Expected quadrilateral room guide: ' + guide.name)
        a, b, c, d = points
        nx = max(1, math.ceil(max((b-a).length, (c-d).length) / 3))
        ny = max(1, math.ceil(max((d-a).length, (c-b).length) / 3))
        for row in range(ny):
            v = (row + .5) / ny
            left, right = a.lerp(d, v), b.lerp(c, v)
            direction = (right-left).normalized()
            length = min(1.2, (right-left).length / nx - .4)
            if length < .4:
                raise ValueError('Room guide too narrow for tubular fixture')
            for col in range(nx):
                yield left.lerp(right, (col+.5)/nx), direction, length


def main(save=False):
    collection = bpy.data.collections.get(COLLECTION)
    if collection is None:
        collection = bpy.data.collections.new(COLLECTION)
        bpy.context.scene.collection.children.link(collection)
    ceilings = ceiling_tree()
    planned = []
    for zone in ZONES:
        guide = bpy.data.objects.get('FLOOR_' + zone)
        if guide is None:
            raise RuntimeError('Missing room guide: ' + zone)
        for index, (center, direction, length) in enumerate(placements(guide), 1):
            hits = []
            for offset in (-length / 2, 0, length / 2):
                point = center + direction * offset
                hit, _, _, _ = ceilings.ray_cast(Vector((point.x, point.y, 1.8)), Vector((0, 0, 1)), 10)
                if hit is None:
                    break
                hits.append(hit.z)
            if len(hits) != 3:
                print(f'Skipping uncovered position: {zone} {index}')
                continue
            z = min(hits) - .16
            if z < 1.95:
                raise RuntimeError('Unexpected low ceiling in ' + zone)
            planned.append((zone, index, Vector((center.x, center.y, z)), direction, length, min(hits)))

    missing = set(ZONES) - {item[0] for item in planned}
    if missing:
        raise RuntimeError(f'No covered fixture positions for rooms: {sorted(missing)}')

    # Only replace objects owned by this generator or the earlier review-light generator.
    for obj in list(collection.objects):
        if obj.get('lightingZone'):
            bpy.data.objects.remove(obj, do_unlink=True)
    material = bpy.data.materials.get('MAT_Linear_Light_Diffuser') or bpy.data.materials.new('MAT_Linear_Light_Diffuser')
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (.92, .96, 1, 1)
    shader.inputs['Roughness'].default_value = .35
    shader.inputs['Emission Color'].default_value = (.92, .96, 1, 1)
    shader.inputs['Emission Strength'].default_value = 2
    report = []
    for zone, index, center, direction, length, ceiling_z in planned:
        name = f'LIGHT_Interior_{zone}_{index:02d}'
        light = bpy.data.lights.new(name, 'AREA')
        light.shape = 'RECTANGLE'
        light.size = length
        light.size_y = .08
        light.energy = 85 if zone.startswith('BANO') else 140
        light.color = (.92, .96, 1.0)
        obj = bpy.data.objects.new(name, light)
        collection.objects.link(obj)
        obj.location = center - Vector((0, 0, .035))
        obj.rotation_euler.z = math.atan2(direction.y, direction.x)
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=.025, depth=length, location=center)
        tube = bpy.context.object
        tube.name = f'FIXTURE_Interior_{zone}_{index:02d}'
        for existing in list(tube.users_collection):
            existing.objects.unlink(tube)
        collection.objects.link(tube)
        tube.rotation_mode = 'QUATERNION'
        tube.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(direction)
        tube.data.materials.append(material)
        for face in tube.data.polygons:
            face.use_smooth = len(face.vertices) == 4
        for item in (obj, tube):
            item['lightingZone'] = zone
            item['generatedBy'] = 'build_interior_lighting.py'
            item['placementEvidence'] = 'provisional room grid below evaluated ceiling'
            item['ceilingHitZ'] = ceiling_z
            item['fixtureLength'] = length
        report.append({'name':name, 'zone':zone, 'location':list(center), 'length':length, 'ceiling_z':ceiling_z})
    bpy.context.view_layer.update()
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    return report


if __name__ == '__main__':
    print(main(save=True))
