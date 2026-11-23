"""Independent analytic geometry fixtures, never an acceptance-case solution."""
import base64
import hashlib
import json
import struct


def cases():
    vertices=[[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]]
    faces=[[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],
           [1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]]
    binary=struct.pack('<24f',*(v for point in vertices for v in point))+struct.pack('<36H',*(v for face in faces for v in face))
    doc={'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':[0]}],
         'nodes':[{'name':'analytic cube','mesh':0,'translation':[5,0,0]}],
         'meshes':[{'primitives':[{'attributes':{'POSITION':0},'indices':1}]}],
         'buffers':[{'byteLength':len(binary)}],
         'bufferViews':[{'buffer':0,'byteLength':96},{'buffer':0,'byteOffset':96,'byteLength':72}],
         'accessors':[{'bufferView':0,'componentType':5126,'count':8,'type':'VEC3','min':[-1,-1,-1],'max':[1,1,1]},
                      {'bufferView':1,'componentType':5123,'count':36,'type':'SCALAR'}]}
    encoded=json.dumps(doc,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%4)
    raw=struct.pack('<4sII',b'glTF',2,28+len(encoded)+len(binary))+struct.pack('<I4s',len(encoded),b'JSON')+encoded+struct.pack('<I4s',len(binary),b'BIN\0')+binary
    def payload(body,kind):
        return {'format':kind,'body':base64.b64encode(body).decode(),'source_sha256':hashlib.sha256(body).hexdigest(),
                'entrypoint':'canonical.'+kind,'resources':{},'length_unit':'unknown'}
    doc['buffers'][0]['uri']='file:///not-allowed.bin'
    return payload(raw,'glb'),payload(json.dumps(doc).encode(),'gltf')

