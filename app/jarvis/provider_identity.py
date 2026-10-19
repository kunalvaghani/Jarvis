"""Provider account identity for approved external writes (Prompt 33, P33-004).

An approval names the provider, the account/workspace identity and the target; it never contains a credential.
The identity and an HMAC fingerprint of each credential are captured *before* the approval card is shown; the
same context is re-checked immediately before dispatch and the request is sent with the approved context's
environment, never with whatever the process environment holds at that moment.

* Identity keys (non-secret: account label, user name, host/workspace URL) define *who*. If any are missing the
  context is ``unverified`` and every credential change is refused.
* A credential change with an unchanged, verified identity is token **rotation**: allowed, using the current
  credential of that same identity, and reported. A changed identity is an **account switch** and is refused.
Fingerprints use a per-process random key, so they cannot be compared across runs or reversed into tokens.
"""
import hashlib
import hmac
import os
import secrets

# provider (toolkit name) -> (identity keys, credential keys)
PROVIDERS = {
    'calendar': (('JARVIS_GOOGLE_ACCOUNT',), ('JARVIS_GOOGLE_ACCESS_TOKEN',)),
    'github': (('JARVIS_GITHUB_ACCOUNT',), ('JARVIS_GITHUB_TOKEN',)),
    'slack': (('JARVIS_SLACK_WORKSPACE',), ('JARVIS_SLACK_TOKEN',)),
    'twitter': (('JARVIS_TWITTER_ACCOUNT',), ('JARVIS_TWITTER_TOKEN',)),
    'jira': (('JARVIS_JIRA_URL', 'JARVIS_JIRA_USER'), ('JARVIS_JIRA_TOKEN',)),
    'email': (('JARVIS_SMTP_HOST', 'JARVIS_EMAIL_USER'), ('JARVIS_EMAIL_PASSWORD',)),
}
_KEY = secrets.token_bytes(32)


class AccountDrift(ValueError):
    """The account or credential behind an approved write changed before dispatch; nothing was sent."""


def _fingerprint(value):
    return hmac.new(_KEY, value.encode('utf-8', 'replace'), hashlib.sha256).hexdigest()[:16]


class ProviderContext:
    def __init__(self, provider, environment=None):
        self.provider = provider
        environment = dict(os.environ if environment is None else environment)
        identity_keys, credential_keys = PROVIDERS.get(provider, ((), ()))
        self.identity = tuple((key, environment.get(key, '')) for key in identity_keys)
        self.verified = bool(identity_keys) and all(value for _, value in self.identity)
        self.fingerprints = {key: _fingerprint(environment[key]) for key in credential_keys if environment.get(key)}
        # Only JARVIS_* settings are carried to dispatch; this snapshot never leaves the process.
        self.environment = {key: value for key, value in environment.items() if key.startswith('JARVIS_')}
        self.rotated = False

    @property
    def account(self):
        if self.verified:
            return ' / '.join(value for _, value in self.identity)[:200]
        anchor = next(iter(self.fingerprints.values()), 'none')
        return 'unverified account (credential fingerprint ' + anchor[:8] + ')'

    def approval_fields(self, target):
        return {'provider': self.provider, 'account': self.account, 'identity_verified': self.verified,
                'target': str(target)[:300]}

    def recheck(self, environment=None):
        """Return the context to dispatch with, or raise AccountDrift before anything is sent."""
        current = ProviderContext(self.provider, environment)
        if current.identity != self.identity:
            raise AccountDrift('The ' + self.provider + ' account changed while approval was pending; nothing was sent.')
        if current.fingerprints == self.fingerprints:
            return self
        if not self.verified:
            raise AccountDrift('The ' + self.provider + ' credential changed while approval was pending and the account '
                               'identity is not configured, so the account cannot be confirmed; nothing was sent.')
        if set(current.fingerprints) != set(self.fingerprints):
            raise AccountDrift('The ' + self.provider + ' credential set changed while approval was pending; nothing was sent.')
        current.rotated = True  # same verified identity, new token: rotation, not an account switch
        return current
