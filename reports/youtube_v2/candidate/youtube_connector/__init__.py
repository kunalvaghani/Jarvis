"""YouTube connector v2 export; original v1 is preserved for regression."""
from .base import ConnectorError, ConnectorInfo, UnsupportedAction
from .youtube import YouTubeConnector as LegacyYouTubeConnector
from .youtube_v2 import YouTubeConnector
__all__ = ['ConnectorError','ConnectorInfo','UnsupportedAction',
           'YouTubeConnector','LegacyYouTubeConnector']
