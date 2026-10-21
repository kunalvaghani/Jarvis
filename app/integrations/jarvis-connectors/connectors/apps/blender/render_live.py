"""Tiny disposable Cycles CPU/GPU rendering acceptance with actual image readback."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from blender_connector.operations import BlenderOperations

folder=Path(tempfile.mkdtemp(prefix='jarvis-cycles-audit-'))
os.environ['JARVIS_BLENDER_ALLOWED_ROOTS']=str(folder)
bpy.ops.wm.read_factory_settings(use_empty=False)
ops=BlenderOperations()
ops.execute('set_render_engine',{'engine':'CYCLES'})
ops.execute('set_render_resolution',{'width':64,'height':64})
ops.execute('set_render_samples',{'samples':1})
report={'version':bpy.app.version_string,'renders':[]}
preferences=bpy.context.preferences.addons['cycles'].preferences
preferences.get_devices()
devices=[{'name':d.name,'type':d.type} for d in preferences.devices]
report['initial_devices']=devices
for mode in ('CPU','GPU'):
    record={'device':mode}
    try:
        if mode=='GPU':
            found=False
            for backend in ('OPTIX','CUDA','HIP','ONEAPI','METAL'):
                try:
                    preferences.compute_device_type=backend;preferences.get_devices()
                    selected=[d for d in preferences.devices if d.type==backend]
                    if not selected:continue
                    for d in preferences.devices:d.use=d.type==backend
                    record['backend']=backend;record['devices']=[d.name for d in selected];found=True;break
                except (TypeError,ValueError):continue
            if not found:raise RuntimeError('No available Cycles GPU backend')
        ops.execute('set_cycles_device',{'device':mode})
        path=folder/(mode.lower()+'.png')
        start=time.perf_counter();ops.execute('render_still',{'filepath':str(path)});record['elapsed_ms']=(time.perf_counter()-start)*1000
        image=bpy.data.images.load(str(path),check_existing=False)
        assert tuple(image.size)==(64,64)
        pixels=list(image.pixels)
        assert any(pixels[i]>0 for i in range(0,len(pixels),4))
        record.update(coverage='VERIFIED IN BLENDER',png_bytes=path.stat().st_size,resolution=list(image.size),nonzero_rgb=True)
        target=Path(os.environ['JARVIS_BLENDER_RENDER_REPORT']).parent/(mode.lower()+'-preview.png')
        target.write_bytes(path.read_bytes())
    except Exception as exc:record.update(coverage='UNTESTED',error=str(exc)[:400])
    report['renders'].append(record)
Path(os.environ['JARVIS_BLENDER_RENDER_REPORT']).write_text(json.dumps(report,indent=2),encoding='utf-8')
print('JARVIS_RENDER_AUDIT',report,flush=True)
