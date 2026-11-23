"""C2 native parts expressed through the C1 project/parameter/dependency contract."""
from pathlib import Path
from jarvis.discovery.contracts import Component,Parameter,Quantity,Representations,Scenario,Source
from jarvis.discovery.model.component_graph import Project,ParameterBinding,Computation,Dependency
from jarvis.discovery.model.pendulum import scenario,sha


def world(spec):
    digest=sha(scenario(spec));identity='pendulum-world-'+digest[:32]
    source=Source(id=identity+'-source',locator='urn:jarvis:pendulum-world:'+digest,sha256=digest,
                  justification='Canonical user-declared scenario values, not measurements.')
    fields=(('gravity',spec.gravity_m_s2,'m/s^2'),('initial_angle',spec.initial_angle_rad,'radian'),
            ('duration',spec.duration_s,'s'),('time_step',spec.dt_s,'s'))
    params=tuple(Parameter(id=identity+'.'+name,name=name,quantity=Quantity(value=value,unit=unit,
                  origin='source',source_ref=source.id)) for name,value,unit in fields)
    return source,Scenario(id=identity,name='Fixed pendulum scenario',parameters=params,source_ids=(source.id,),
                           assumptions=('uniform gravity along -Z','initial angular velocity is zero','no contact/air/thermal model'))


def project(spec,run_ref,ids,folder,memory):
    folder=Path(folder);source,scene=world(spec);components=[]
    for name,identity in ids.items():
        old=memory.get(identity);revision=old.revision+1 if old else 1
        mass=Quantity(value=spec.mass_kg,unit='kg',origin='source',source_ref=run_ref) if name=='bob' else Quantity(unit='kg')
        components.append(Component(id=identity,revision=revision,name='Pendulum '+name,reality_class='P1',mass=mass,
            parent_id=ids['anchor'] if name!='anchor' else None,missing=('material/strength not modeled',),
            representations=Representations(native=str(folder/'pendulum.blend'),visual=str(folder/'pendulum.obj'),
                functional=str(folder/'rig.json'),physical=str(folder/'model.json'))))
    bindings=[]
    for name,part,path,value,unit,low,high in (
        ('length','rod','geometry.length',spec.length_m,'m',0.1,5.0),
        ('radius','bob','geometry.radius',spec.radius_m,'m',0.005,0.2),
        ('mass','bob','physical.mass',spec.mass_kg,'kg',0.01,20.0)):
        identity=ids[part]+'.'+name;old=memory.get(identity)
        param=Parameter(id=identity,revision=old.revision+1 if old else 1,name=name,lower=low,upper=high,
                        quantity=Quantity(value=value,unit=unit,origin='source',source_ref=run_ref))
        bindings.append(ParameterBinding(component_id=ids[part],path=path,parameter=param,mutable=True))
    nodes={'rod':ids['rod']+'.geometry','bob':ids['bob']+'.geometry','inertia':ids['bob']+'.inertia',
           'mechanics':ids['anchor']+'.mechanics','display':ids['anchor']+'.display'}
    computations=tuple(Computation(id=nodes[key],component_id=ids[part],kind=kind) for key,part,kind in (
        ('rod','rod','geometry'),('bob','bob','geometry'),('inertia','bob','mass_inertia'),
        ('mechanics','anchor','mechanics'),('display','anchor','visualization')))
    length,radius,mass=(b.parameter.id for b in bindings)
    edges=((length,nodes['rod']),(length,nodes['inertia']),(radius,nodes['bob']),(radius,nodes['inertia']),
           (mass,nodes['inertia']),(nodes['inertia'],nodes['mechanics']),
           (nodes['rod'],nodes['display']),(nodes['bob'],nodes['display']),(nodes['mechanics'],nodes['display']))
    previous=memory.get('project-snapshot:'+spec.project_id)
    value=Project(id=spec.project_id,revision=previous.revision+1 if previous else 1,components=tuple(components),
        parameters=tuple(bindings),computations=computations,dependencies=tuple(Dependency(source=a,target=b) for a,b in edges),scenario=scene)
    return source,value
