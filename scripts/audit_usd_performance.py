"""Read-only USD inventory for performance triage; not a GPU benchmark."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import struct
from pxr import Usd, UsdGeom, UsdLux

ROOT=Path(__file__).resolve().parents[1]


def audit(path):
    stage=Usd.Stage.Open(str(path));types=Counter();meshes=[];groups=defaultdict(list)
    instancers=[];settings={};lights=Counter();prototype_paths=[]
    for prim in stage.Traverse():
        types[prim.GetTypeName() or '(untyped)']+=1
        if prim.IsA(UsdGeom.PointInstancer):
            inst=UsdGeom.PointInstancer(prim)
            targets=list(inst.GetPrototypesRel().GetTargets());prototype_paths.extend(targets)
            instancers.append({'path':str(prim.GetPath()),'instances':len(inst.GetProtoIndicesAttr().Get() or []),
                               'prototype_paths':[str(p) for p in targets],
                               'prototype_indices':list(inst.GetProtoIndicesAttr().Get() or [])})
        if prim.HasAPI(UsdLux.LightAPI):lights[prim.GetTypeName()]+=1
        if prim.IsA(UsdGeom.Mesh):
            mesh=UsdGeom.Mesh(prim);points=mesh.GetPointsAttr().Get() or []
            counts=mesh.GetFaceVertexCountsAttr().Get() or []
            triangles=sum(max(0,n-2) for n in counts)
            row={'path':str(prim.GetPath()),'triangles':triangles,'vertices':len(points)}
            meshes.append(row)
            # Candidate duplicates only: material, UV and normals compatibility not implied.
            data=repr((list(points),list(counts),list(mesh.GetFaceVertexIndicesAttr().Get() or [])))
            groups[hashlib.sha256(data.encode()).hexdigest()].append(row)
        authored={a.GetName():str(a.Get()) for a in prim.GetAttributes()
                  if a.GetName().startswith('omni:rtx:') and a.HasAuthoredValueOpinion()}
        if authored and str(prim.GetPath()).startswith('/Render'):settings[str(prim.GetPath())]=authored
    direct=sum(m['triangles'] for m in meshes if not any(SdfPath(m['path']).HasPrefix(p) for p in prototype_paths))
    expanded=direct
    for inst in instancers:
        tris=[sum(m['triangles'] for m in meshes if SdfPath(m['path']).HasPrefix(SdfPath(p))) for p in inst['prototype_paths']]
        inst['prototype_triangles']=tris
        expanded+=sum(tris[i] for i in inst.pop('prototype_indices'))
    textures=[]
    for texture in sorted((ROOT/'usd/textures').glob('*.png')):
        data=texture.read_bytes();width,height=struct.unpack('>II',data[16:24])
        textures.append({'path':str(texture.relative_to(ROOT)), 'bytes':len(data),'width':width,'height':height})
    duplicates=sorted(({'copies':len(rows),'triangles_per_mesh':rows[0]['triangles'],
                       'potential_repeated_triangles':(len(rows)-1)*rows[0]['triangles'],
                       'example':rows[0]['path']} for rows in groups.values() if len(rows)>1),
                      key=lambda row:row['potential_repeated_triangles'],reverse=True)
    return {'scope':'Static composition inventory, not a live RTX/GPU profile. Includes hidden meshes and all point prototypes; triangle estimates exclude tessellation and analytic primitives.',
            'stage':str(path.relative_to(ROOT)), 'types':dict(types),
            'mesh_triangles_including_each_prototype_once':sum(m['triangles'] for m in meshes),
            'approx_expanded_triangles':expanded,'vertices':sum(m['vertices'] for m in meshes),
            'lights':dict(lights),'point_instancers':instancers,
            'top_meshes':sorted(meshes,key=lambda m:m['triangles'],reverse=True)[:15],
            'geometry_duplicate_candidates':duplicates[:15],
            'native_instance_roots':sum(p.IsInstance() for p in stage.Traverse()),
            'payload_prims':sum(p.HasPayload() for p in stage.Traverse()),
            'loaded_layers':len(stage.GetUsedLayers())-1,
            'usd_directory_bytes':sum(p.stat().st_size for p in (ROOT/'usd').rglob('*') if p.is_file()),
            'textures':textures,'authored_render_settings':settings}


from pxr import Sdf
SdfPath=Sdf.Path

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=audit(ROOT/'usd/guadalajara_base.usda');text=json.dumps(result,indent=2)+'\n'
    if args.output:args.output.write_text(text)
    else:print(text,end='')
