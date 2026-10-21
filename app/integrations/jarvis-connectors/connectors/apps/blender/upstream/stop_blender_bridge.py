import bpy
bridge=bpy.app.driver_namespace.pop('jarvis_blender_bridge',None)
if bridge:bridge.stop()
print('Jarvis Blender bridge stopped')
