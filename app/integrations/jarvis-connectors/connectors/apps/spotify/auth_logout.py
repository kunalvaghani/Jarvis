"""Locally remove cached Spotify tokens. Revocation via Spotify account settings is separate."""
from spotify_connector.auth import PKCETokenManager
from spotify_connector.base import ConnectorError
if __name__=='__main__':
    tokens=PKCETokenManager()
    if not tokens.store:raise ConnectorError('Set SPOTIFY_CLIENT_ID')
    tokens.store.delete()
    print('Local Spotify credentials cleared. Revoke app access in Spotify account settings if desired.')
