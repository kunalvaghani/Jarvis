"""Blender automation child connector for Jarvis. Pure Python client + bpy-only bridge."""
from .base import BaseConnector,ConnectorError,ConnectorInfo
from .connector import BlenderConnector
__all__=['BaseConnector','ConnectorError','ConnectorInfo','BlenderConnector']
__version__='1.0.0'
