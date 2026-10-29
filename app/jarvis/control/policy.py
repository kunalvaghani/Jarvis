"""URL, path, app and risk policy plus the per-action approval gate (prompt section 6, doc section 13)."""
from __future__ import annotations

from dataclasses import dataclass, field
import ipaddress
import os
from pathlib import Path, PureWindowsPath
import re
import socket
from typing import Callable, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Tuple, Union
from urllib.parse import urlsplit, urlunsplit

from .types import Action, ControlError, ErrorCategory, Risk

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
Resolver = Callable[[str], Sequence[str]]
METADATA_HOSTS = frozenset({'169.254.169.254', 'fd00:ec2::254', 'metadata.google.internal', 'metadata'})
NUMERIC_HOST = re.compile(r'^(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+)){0,3}$', re.I)
LABEL = re.compile(r'^[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?$')  # Browsers accept '_' in hosts.
DEVICE_NAMES =re.compile(r'^(?:con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\..*)?$', re.I)
CONSEQUENTIAL = re.compile(
    r'\b(send|submit|post|publish|purchase|buy|pay|checkout|order|delete|remove|erase|uninstall|install|'
    r'upload|transfer|accept|agree|sign up|subscribe|unsubscribe|confirm|approve|grant|'
    r'change password|security|permission|share)\b', re.I)
APPROVAL_CLAIMS = frozenset({'approved', 'approval', 'preapproved', 'user_approved', 'authorized', 'authorization',
                             'skip_approval', 'bypass_approval', 'requires_approval', 'permission', 'permissions'})


class PolicyError(ControlError):
    def __init__(self, message: str) -> None:
        super().__init__(message, ErrorCategory.POLICY_DENIED)


def system_resolver(host: str) -> Sequence[str]:
    try:
        return tuple({str(row[4][0]) for row in socket.getaddrinfo(host, None)})
    except OSError:
        return ()


def _as_ip(host: str) -> Optional[IPAddress]:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        pass
    if NUMERIC_HOST.match(host):
        # Browsers accept 127.1, 0x7f.1 and 2130706433 as IPv4 addresses.
        try:
            return ipaddress.IPv4Address(socket.inet_aton(host))
        except OSError:
            return None
    return None


def _valid_hostname(host: str) -> bool:
    if len(host) > 253 or not all(LABEL.match(label) for label in host.split('.')):
        return False
    try:
        for label in host.split('.'):
            if label.startswith('xn--'):
                label.encode('ascii').decode('idna')  # Must be decodable punycode.
    except UnicodeError:
        return False
    return True


def _private(address: IPAddress) -> bool:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved
            or address.is_multicast or address.is_unspecified or str(address) in METADATA_HOSTS)


@dataclass(frozen=True)
class Policy:
    allowed_roots: Tuple[Path, ...] = ()
    loopback_allow: FrozenSet[Tuple[str, int]] = frozenset()  # Exact (host, port) pairs, e.g. God's Eye.
    blocked_domains: FrozenSet[str] = frozenset()
    allowed_domains: FrozenSet[str] = frozenset()  # Empty = any public domain.
    allowed_apps: FrozenSet[str] = frozenset()     # Lower-case executable names; empty = any non-elevated app.
    resolver: Resolver = field(default=system_resolver, compare=False)

    # URLs ---------------------------------------------------------------
    def check_url(self, url: str) -> str:
        if not isinstance(url, str) or not url.strip() or len(url) > 8000 or any(ord(c) < 32 for c in url):
            raise PolicyError('Blocked: the URL is empty, too long or contains control characters.')
        text = url.strip().replace('\\', '/')
        if '://' not in text and not re.match(r'^[a-z][a-z0-9+.-]*:', text, re.I):
            text = 'https://' + text
        parts = urlsplit(text)
        scheme = parts.scheme.lower()
        if scheme not in ('http', 'https'):
            raise PolicyError(f'Blocked: {scheme or "missing"} URLs are not allowed; only http and https.')
        host = (parts.hostname or '').rstrip('.').lower()
        if not host:
            raise PolicyError('Blocked: the URL has no host.')
        try:
            host = host.encode('idna').decode('ascii')
            port = parts.port or (443 if scheme == 'https' else 80)
        except (UnicodeError, ValueError):
            raise PolicyError('Blocked: the URL host or port is malformed.') from None
        if (host, port) in self.loopback_allow:
            return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))
        if host in METADATA_HOSTS or host == 'localhost' or host.endswith('.localhost'):
            raise PolicyError(f'Blocked: {host} is a local or metadata address.')
        address = _as_ip(host)
        if address is not None:
            if _private(address):
                raise PolicyError(f'Blocked: {host} is a loopback, private, link-local or reserved address.')
            if self.allowed_domains:
                raise PolicyError(f'Blocked: raw IP address {host} is not on the allowed-domain list.')
        elif NUMERIC_HOST.match(host):
            raise PolicyError(f'Blocked: {host} looks like an IP address but is malformed.')
        else:
            if not _valid_hostname(host):
                raise PolicyError(f'Blocked: {host} is not a valid host name.')
            if any(host == d or host.endswith('.' + d) for d in self.blocked_domains):
                raise PolicyError(f'Blocked: {host} is on the blocked-domain list.')
            if self.allowed_domains and not any(host == d or host.endswith('.' + d) for d in self.allowed_domains):
                raise PolicyError(f'Blocked: {host} is not on the allowed-domain list.')
            for resolved in self.resolver(host):
                found = _as_ip(resolved.split('%')[0])
                if found is not None and _private(found):
                    raise PolicyError(f'Blocked: {host} resolves to a private or local address.')
        return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))

    def check_redirects(self, chain: Iterable[str]) -> List[str]:
        """Every hop of a redirect chain must pass on its own."""
        return [self.check_url(url) for url in chain]

    # Paths --------------------------------------------------------------
    def confine(self, path: Union[str, Path], roots: Optional[Sequence[Path]] = None) -> Path:
        allowed = tuple(Path(root).resolve() for root in (roots if roots is not None else self.allowed_roots))
        if not allowed:
            raise PolicyError('Blocked: no approved directory is configured for file operations.')
        text = str(path)
        if not text or '\x00' in text or text.startswith(('\\\\?\\', '\\\\.\\', '//?/', '//./')):
            raise PolicyError('Blocked: device or raw-namespace paths are not allowed.')
        windows = PureWindowsPath(text)
        if ':' in text[2:] or any(DEVICE_NAMES.match(part) for part in windows.parts[1:]):
            raise PolicyError('Blocked: alternate data streams and device names are not allowed.')
        candidate = Path(text)
        if not candidate.is_absolute():
            candidate = allowed[0] / candidate
        resolved = Path(os.path.realpath(candidate))  # Follows every symlink/junction that exists.
        for root in allowed:
            try:
                resolved.relative_to(root)
                return resolved
            except ValueError:
                continue
        raise PolicyError('Blocked: the path is outside the approved directories.')

    # Apps ---------------------------------------------------------------
    def check_app(self, executable: str, elevated: bool = False) -> None:
        if elevated:
            raise ControlError('The target window runs as administrator; Jarvis cannot and will not control it. '
                               'Please handle it yourself.', ErrorCategory.ELEVATED_TARGET)
        name = Path(executable).name.lower()
        if self.allowed_apps and name not in self.allowed_apps:
            raise PolicyError(f'Blocked: {name} is not on the allowed application list.')


def classify(name: str, label: str = '', declared: Risk = Risk.READ) -> Risk:
    """Risk is the maximum of the tool's declared tier and what the target text implies."""
    if CONSEQUENTIAL.search(name.replace('_', ' ')) or CONSEQUENTIAL.search(label or ''):
        return Risk.CONSEQUENTIAL
    return declared


def strip_claims(params: Mapping[str, object]) -> dict[str, object]:
    """A proposal can never carry its own authorization."""
    return {key: value for key, value in params.items() if key.lower() not in APPROVAL_CLAIMS}


Confirm = Callable[[Action], bool]


@dataclass
class ApprovalGate:
    """Ask before every Tier-2 action, one action at a time, also inside batches."""
    confirm: Optional[Confirm] = None
    decisions: List[Tuple[str, bool]] = field(default_factory=list)

    def require(self, action: Action) -> None:
        if action.risk < Risk.CONSEQUENTIAL:
            return
        granted = False
        if self.confirm is not None:
            try:
                granted = self.confirm(action) is True
            except Exception:
                granted = False  # A broken approval UI never grants permission.
        self.decisions.append((action.action_id, granted))
        if not granted:
            raise ControlError('The user did not grant permission for this action; nothing was done.',
                               ErrorCategory.APPROVAL_DENIED)
