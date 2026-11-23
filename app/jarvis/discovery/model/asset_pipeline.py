"""Typed asset-subtask state; completion never means physical validation."""
from enum import Enum
import json
from typing import Literal
import uuid
from pydantic import Field,JsonValue,model_serializer
from ..contracts import StrictModel


class Stage(str,Enum):
    research='research'
    select='select'
    acquire='acquire'
    inspect='inspect'
    completed='completed'


class Request(StrictModel):
    query:str=Field(min_length=4,max_length=240)
    target_year:int|None=Field(default=None,ge=1900,le=2100)


class Target(Request):
    resource_grant_sha256:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')
    inspector_sha256:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')

    @model_serializer(mode='wrap')
    def canonical(self,handler):
        result=handler(self)
        if self.resource_grant_sha256 is None:result.pop('resource_grant_sha256',None)
        if self.inspector_sha256 is None:result.pop('inspector_sha256',None)
        return result


class Response(StrictModel):
    stage:Stage
    facts:dict[str,JsonValue]
    files:dict[str,str]


class State(StrictModel):
    version:Literal[1]=1
    run_id:str=Field(pattern=r'^asset-[a-f0-9]{32}$')
    original_goal:str
    stage:Stage=Stage.research
    stage_status:Literal['pending','running','verified','blocked','uncertain','completed']='pending'
    attempts:dict[str,int]=Field(default_factory=dict)
    state_revision:int=Field(default=0,ge=0)
    verified_stages:tuple[str,...]=()
    stage_artifacts:dict[str,str]=Field(default_factory=dict)
    failures:tuple[str,...]=()
    research_ref:str|None=None
    acquisition_ref:str|None=None
    download_ref:str|None=None
    inspection_ref:str|None=None


class Workflow:
    namespace='asset-to-geometry-v1'
    state_type=State
    response_type=Response
    stage_type=Stage
    stages=tuple(s.value for s in Stage)
    projection_fields=('research_ref','acquisition_ref','download_ref','inspection_ref')

    @staticmethod
    def resolve(value):return Target.model_validate_json(value)

    @staticmethod
    def new_state(target):
        return State(run_id='asset-'+uuid.uuid4().hex,original_goal=json.dumps(target.model_dump(mode='json'),sort_keys=True))
