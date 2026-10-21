"""Owned disposable background Blender instance for host/stdio E2E verification only."""
import os
from pathlib import Path
import time
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from blender_connector.bridge import Bridge

config=Path(os.environ['JARVIS_BLENDER_CONFIG'])
bpy.ops.wm.read_factory_settings(use_empty=True)
for name,size,offset in [('Medium',125,0),('Large',500,3)]:
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=size,y_subdivisions=size,location=(offset,0,0))
    bpy.context.object.name=name
bridge=Bridge(port=int(os.environ['JARVIS_BLENDER_PORT'])).start()
deadline=time.monotonic()+300
try:
    while time.monotonic()<deadline and not config.with_suffix('.stop').exists():
        bridge.pump()
        time.sleep(.01)
finally:bridge.stop()
