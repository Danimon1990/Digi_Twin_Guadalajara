"""Material-only gray corrugated cement-sheet look; no mesh/UV/transform edits.

Wave spacing is illustrative on existing UVs, not a measured product profile.
Texture-backed Preview Surface nodes keep the look portable to OpenUSD.
"""
from pathlib import Path
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ['Cube', 'Cube.011', 'Cube.013', 'Cube.047', 'Cube.048']


def main(save=False):
    size = 2048
    rng = np.random.default_rng(17861)
    y, x = np.mgrid[0:size, 0:size].astype(np.float32) / size
    phase = 2 * np.pi * 56 * x
    grain = rng.normal(0, .012, (size, size)).astype(np.float32)
    mottle = .018 * np.sin(2*np.pi*x*5) * np.cos(2*np.pi*y*7)
    # Gentle visual overlap joints, kept away from the silhouette.
    seam = (np.mod(y * 4, 1) < .009).astype(np.float32)
    gray = np.clip(.49 + grain + mottle - .025*seam, .35, .6)
    color = np.stack([gray, gray*.995, gray*.98, np.ones_like(x)], axis=-1)
    nx = -.75*np.cos(phase) + grain*.7
    ny = grain*.6
    nz = np.ones_like(x)
    norm = np.sqrt(nx*nx+ny*ny+nz*nz)
    normal = np.stack([nx/norm*.5+.5, ny/norm*.5+.5, nz/norm*.5+.5, np.ones_like(x)], axis=-1)
    directory = ROOT/'usd/textures'
    directory.mkdir(parents=True, exist_ok=True)
    images = []
    for name, pixels, space in [('roof_teja_gris_color', color, 'sRGB'), ('roof_teja_gris_normal', normal, 'Non-Color')]:
        image = bpy.data.images.get(name) or bpy.data.images.new(name, size, size)
        image.scale(size, size)
        image.colorspace_settings.name = space
        image.pixels.foreach_set(pixels.astype(np.float32).ravel())
        image.filepath_raw = str(directory/(name+'.png'))
        image.file_format = 'PNG'
        image.save()
        image.filepath = '//../usd/textures/'+name+'.png'
        images.append(image)
    mat = bpy.data.materials.get('MAT_Roof_Teja_Gris_Cemento') or bpy.data.materials.new('MAT_Roof_Teja_Gris_Cemento')
    mat.use_nodes=True;mat.diffuse_color=(.22,.22,.215,1)
    nodes=mat.node_tree.nodes;nodes.clear();links=mat.node_tree.links
    output=nodes.new('ShaderNodeOutputMaterial');output.location=(600,0)
    shader=nodes.new('ShaderNodeBsdfPrincipled');shader.location=(300,0)
    shader.inputs['Metallic'].default_value=0
    shader.inputs['Roughness'].default_value=.88
    links.new(shader.outputs['BSDF'],output.inputs['Surface'])
    uv=nodes.new('ShaderNodeUVMap');uv.uv_map='UVMap';uv.location=(-600,0)
    for i,img in enumerate(images):
        tex=nodes.new('ShaderNodeTexImage');tex.image=img;tex.location=(-350,-i*280);tex.extension='REPEAT'
        links.new(uv.outputs['UV'],tex.inputs['Vector'])
        if i==0:links.new(tex.outputs['Color'],shader.inputs['Base Color'])
        else:
            n=nodes.new('ShaderNodeNormalMap');n.location=(0,-200);n.uv_map='UVMap';n.inputs['Strength'].default_value=.35
            links.new(tex.outputs['Color'],n.inputs['Color']);links.new(n.outputs['Normal'],shader.inputs['Normal'])
    mat['appearance_reference']='https://b2bmarketplace.procolombia.co/es/materiales-de-construccion/cemento/teja-cemento-reforzado-proteja-17861'
    mat['evidence']='Illustrative matte gray corrugated cement appearance; UV spacing is not measured; no displacement'
    for name in TARGETS:
        o=bpy.data.objects[name]
        if not o.data.uv_layers.get('UVMap'):raise RuntimeError('Missing existing UVs: '+name)
        o.data.materials[0]=mat
    if save:bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    return {'material':mat.name,'objects':TARGETS,'geometry_changed':False}

if __name__=='__main__':print(main(save=True))
