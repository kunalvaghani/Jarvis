"""Inert asset acquisition contracts; metadata is never proof of physical identity."""
from typing import Literal
from pydantic import Field,model_validator
from ..contracts import StrictModel

FORMAT=Literal['glb','gltf','obj','stl','ply','step','stp','zip']


class Acquisition(StrictModel):
    version: Literal[1]=1
    candidate_id: str=Field(min_length=1,max_length=200)
    provider: Literal['github','sketchfab','polyhaven']
    source_url: str=Field(min_length=10,max_length=2048)
    creator: str=Field(min_length=1,max_length=200)
    license_spdx: str=Field(min_length=1,max_length=50)
    license_url: str=Field(min_length=10,max_length=2048)
    attribution: str=Field(min_length=1,max_length=1000)
    evidence_ref: str=Field(pattern=r'^artifact://sha256/[a-f0-9]{64}$')
    file_format: FORMAT
    maximum_bytes: int=Field(ge=4,le=100_000_000)
    expected_sha256: str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')
    identity_status: Literal['author_declared_replica','author_declared_concept','engineering_source','unknown']
    year: int|None=Field(default=None,ge=1800,le=2200)

    @model_validator(mode='after')
    def rights(self):
        from ..adapters.assets import PERMITTED
        from urllib.parse import urlsplit
        if self.license_spdx not in PERMITTED:raise ValueError('license is outside existing permitted asset policy')
        for value in (self.source_url,self.license_url):
            p=urlsplit(value)
            if p.scheme!='https' or not p.hostname or p.username or p.password or p.fragment or p.query or p.port not in (None,443):
                raise ValueError('public HTTPS provenance without embedded credentials required')
        if not self.creator.strip() or not self.attribution.strip():raise ValueError('nonempty author and attribution required')
        return self


class DownloadResult(StrictModel):
    version: Literal[1]=1
    candidate_id: str
    acquisition_ref: str=Field(pattern=r'^artifact://sha256/[a-f0-9]{64}$')
    relative_file: str=Field(min_length=1,max_length=1000)
    sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    bytes: int=Field(ge=4,le=100_000_000)
    file_format: FORMAT
    completed: Literal[True]=True
    code_executed: Literal[False]=False
    physical_identity_verified: Literal[False]=False
    source_revision: str=Field(min_length=1,max_length=200)
