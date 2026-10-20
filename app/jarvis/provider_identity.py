"""Provider account binding for approved external writes (Prompt 33, P33-004).

An approval names the provider, the configured account label and the target; it never contains a credential.
Before the card is shown, ``ProviderContext`` captures the configured labels, a per-process HMAC fingerprint of
each credential and the ``JARVIS_*`` settings. Immediately before dispatch ``recheck`` compares them again, and the
request is sent with the approved snapshot, never with whatever the process environment holds at that moment.

Configured labels (``JARVIS_GOOGLE_ACCOUNT``, Jira URL/user, …) are **display and drift-detection only**: they are not
evidence of who a credential belongs to, so ``identity_verified`` is never derived from them.

* Labels changed while approval was pending: account switch, refused.
* Credential changed while approval was pending: refused before dispatch, and the user must approve again, unless an
  **independent principal verifier** registered for that provider (a read-only "who am I" check, never a write)
  confirms the replacement credential has the same principal and workspace as the approved credential, with at
  least the approved scopes. Only then is it treated as rotation. No verifier is registered by default, so missing
  verification fails closed.
Fingerprints use a per-process random key, so they cannot be compared across runs or reversed into tokens.
"""
import hashlib
import hmac
import os
import secrets

# provider (toolkit name) -> (configured label keys, credential keys)
PROVIDERS = {
    'calendar': (('JARVIS_GOOGLE_ACCOUNT',), ('JARVIS_GOOGLE_ACCESS_TOKEN',)),
    'github': (('JARVIS_GITHUB_ACCOUNT',), ('JARVIS_GITHUB_TOKEN',)),
    'slack': (('JARVIS_SLACK_WORKSPACE',), ('JARVIS_SLACK_TOKEN',)),
    'twitter': (('JARVIS_TWITTER_ACCOUNT',), ('JARVIS_TWITTER_TOKEN',)),
    'jira': (('JARVIS_JIRA_URL', 'JARVIS_JIRA_USER'), ('JARVIS_JIRA_TOKEN',)),
    'email': (('JARVIS_SMTP_HOST', 'JARVIS_EMAIL_USER'), ('JARVIS_EMAIL_PASSWORD',)),
}
# provider -> callable(environment) -> {'principal': str, 'workspace': str, 'scopes': iterable} (read-only lookup)
PRINCIPAL_VERIFIERS = {}
_KEY = secrets.token_bytes(32)


class AccountDrift(ValueError):
    """The account or credential behind an approved write changed before dispatch; nothing was sent."""


def register_principal_verifier(provider, verifier):
    """Install an independent, read-only principal check for a provider (None removes it)."""
    if verifier is None:
        PRINCIPAL_VERIFIERS.pop(provider, None)
    else:
        PRINCIPAL_VERIFIERS[provider] = verifier


def _fingerprint(value):
    return hmac.new(_KEY, value.encode('utf-8', 'replace'), hashlib.sha256).hexdigest()[:16]


def _principal(provider, environment):
    """Independently established principal for a credential, or None when it cannot be established."""
    verifier = PRINCIPAL_VERIFIERS.get(provider)
    if verifier is None:
        return None
    try:
        evidence = verifier(dict(environment))
    except Exception:
        return None  # a failed check is not evidence; callers fail closed
    if not isinstance(evidence, dict) or not evidence.get('principal') or not evidence.get('workspace'):
        return None
    return {'principal': str(evidence['principal']), 'workspace': str(evidence['workspace']),
            'scopes': frozenset(str(scope) for scope in evidence.get('scopes', ()))}


class ProviderContext:
    def __init__(self, provider, environment=None, establish=True):
        self.provider = provider
        environment = dict(os.environ if environment is None else environment)
        label_keys, credential_keys = PROVIDERS.get(provider, ((), ()))
        self.labels = tuple((key, environment.get(key, '')) for key in label_keys)
        self.fingerprints = {key: _fingerprint(environment[key]) for key in credential_keys if environment.get(key)}
        # Only JARVIS_* settings are carried to dispatch; this snapshot never leaves the process.
        self.environment = {key: value for key, value in environment.items() if key.startswith('JARVIS_')}
        self.principal = _principal(provider, self.environment) if establish else None
        self.rotated = False

    @property
    def verified(self):
        return self.principal is not None

    @property
    def account(self):
        if self.principal is not None:
            return (self.principal['principal'] + ' @ ' + self.principal['workspace'])[:200]
        configured = ' / '.join(value for _, value in self.labels if value)
        anchor = next(iter(self.fingerprints.values()), 'none')[:8]
        return ((configured + ' (configured label, not verified)') if configured else 'unverified account') + \
            ' · credential fingerprint ' + anchor

    def approval_fields(self, target):
        return {'provider': self.provider, 'account': self.account, 'identity_verified': self.verified,
                'target': str(target)[:300]}

    def recheck(self, environment=None):
        """Return the context to dispatch with, or raise AccountDrift before anything is sent."""
        current = ProviderContext(self.provider, environment, establish=False)
        if current.labels != self.labels:
            raise AccountDrift('The ' + self.provider + ' account changed while approval was pending; nothing was sent.')
        if current.fingerprints == self.fingerprints:
            return self  # the approved credential itself; dispatch uses the approved snapshot
        refusal = ('The ' + self.provider + ' credential changed while approval was pending and its account could not '
                   'be independently confirmed; nothing was sent. Ask again to approve with the current credential.')
        if self.principal is None or set(current.fingerprints) != set(self.fingerprints):
            raise AccountDrift(refusal)
        replacement = _principal(self.provider, current.environment)
        if (replacement is None or replacement['principal'] != self.principal['principal']
                or replacement['workspace'] != self.principal['workspace']
                or not self.principal['scopes'] <= replacement['scopes']):
            raise AccountDrift(refusal)
        current.principal = replacement
        current.rotated = True  # independently verified same principal and workspace: rotation
        return current
