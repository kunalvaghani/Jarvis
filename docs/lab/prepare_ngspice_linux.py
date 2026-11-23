"""Explicitly approved, fixed Debian archive acquisition; never execute packages.

Run manually from repo root only after the approval in NGSPICE_RUNTIME_PLAN.md.
No package manager, installation scripts, link extraction or host library load.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'app/.jarvis-runtime/discovery/tools/ngspice-linux-44.2'
PACKAGES = (
    ('libngspice0', '44.2+ds-1', 'n/ngspice', 2503956,
     'd1b9dec8b93f8785c6e8bf6ecea05fc94d6b4c7e60ee8e7df0589e3a2a62822a'),
    ('libgomp1', '14.2.0-19', 'g/gcc-14', 137148,
     '72b7a1a33c48f3195efeb044111b34ae684b1e640bb6495c832443b798601cd5'),
)


def ar_members(raw):
    if not raw.startswith(b'!<arch>\n'):
        raise ValueError('invalid Debian ar header')
    offset = 8
    result = {}
    while offset < len(raw):
        header = raw[offset:offset+60]
        if len(header) != 60 or header[-2:] != b'`\n':
            raise ValueError('invalid ar member header')
        name = header[:16].decode('ascii').strip().rstrip('/')
        size = int(header[48:58])
        if name not in ('debian-binary', 'control.tar.xz', 'control.tar.gz', 'data.tar.xz', 'data.tar.gz'):
            raise ValueError('unreviewed package archive member')
        if name in result or size < 0 or offset+60+size > len(raw):
            raise ValueError('invalid ar size/duplicate member')
        result[name] = raw[offset+60:offset+60+size]
        offset += 60+size+(size % 2)
    if result.get('debian-binary') != b'2.0\n':
        raise ValueError('unsupported Debian package format')
    return result


def extract_data(raw, destination, remaining):
    files, skipped_links = [], []
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r|*') as archive:
        for member in archive:
            name = member.name.removeprefix('./')
            if not name or name == '.':
                continue
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
                raise ValueError('unsafe archive path')
            if member.isdir():
                continue
            if member.issym() or member.islnk():
                skipped_links.append(name)  # Never materialize a package link on the host.
                continue
            if not member.isfile() or member.size < 0 or member.size > remaining:
                raise ValueError('unsupported member or extracted-size cap exceeded')
            remaining -= member.size
            source = archive.extractfile(member)
            data = source.read(member.size+1)
            if len(data) != member.size:
                raise ValueError('archive member length differs')
            target = destination.joinpath(*path.parts)
            if target.exists() or any(p.is_symlink() for p in (target, *target.parents)):
                raise ValueError('refuse overwrite or linked destination')
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as out:
                out.write(data)
            files.append({'path': str(target.relative_to(DEST)).replace('\\', '/'), 'bytes': len(data),
                          'sha256': hashlib.sha256(data).hexdigest()})
    return files, skipped_links, remaining


def main():
    if DEST.exists() and any(DEST.iterdir()):
        raise ValueError('runtime destination already exists; inspect it, never replay automatically')
    if any(p.is_symlink() for p in (DEST, *DEST.parents)):
        raise ValueError('linked runtime destination')
    DEST.mkdir(parents=True, exist_ok=True)
    rows, remaining, downloaded = [], 32_000_000, 0
    for name, version, pool, size, expected in PACKAGES:
        filename = f'{name}_{version}_amd64.deb'
        url = f'https://deb.debian.org/debian/pool/main/{pool}/{filename}'
        with urlopen(url, timeout=30) as response:
            final = urlparse(response.geturl())
            if final.scheme != 'https' or final.hostname != 'deb.debian.org':
                raise ValueError('unexpected download destination')
            raw = response.read(min(size+1, 10_000_000-downloaded+1))
        downloaded += len(raw)
        if len(raw) != size or downloaded > 10_000_000 or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError('official archive size/hash mismatch or cap exceeded')
        (DEST / filename).write_bytes(raw)
        members = ar_members(raw)
        data = next(value for key, value in members.items() if key.startswith('data.tar.'))
        files, skipped, remaining = extract_data(data, DEST / name, remaining)
        # Control archive stays inert; retained for human inspection, not executed.
        for key, value in members.items():
            if key.startswith('control.tar.'):
                (DEST / f'{name}-{key}').write_bytes(value)
        rows.append({'package': name, 'version': version, 'url': url, 'bytes': len(raw), 'sha256': expected,
                     'files': files, 'links_not_extracted': skipped})
    receipt = {'date_local': '2026-11-04 Asia/Calcutta', 'authorization': 'user approved Linux preparation and up to 20 sandbox tests',
               'packages': rows, 'downloaded_bytes': downloaded, 'extracted_bytes': 32_000_000-remaining,
               'host_install': False, 'maintainer_scripts_executed': False, 'solver_executed': False}
    (DEST / 'preparation.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'packages'}))


if __name__ == '__main__':
    main()
