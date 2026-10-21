"""Load in Blender Scripting > Text Editor > Run Script, or via blender --python.
No external dependencies inside Blender.
"""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import bpy
from blender_connector.bridge import Bridge

namespace=bpy.app.driver_namespace
previous=namespace.get('jarvis_blender_bridge')
if previous:
    try:previous.stop()
    except Exception:pass
bridge=Bridge(port=int(__import__('os').environ.get('JARVIS_BLENDER_PORT','8769')))
bridge.start()
namespace['jarvis_blender_bridge']=bridge
bpy.app.timers.register(bridge.pump,first_interval=.05,persistent=True)
print(f'Jarvis Blender bridge running on 127.0.0.1:{bridge.port} ({len(__import__("blender_connector.catalog",fromlist=["ACTIONS"]).ACTIONS)} allowlisted actions)')
