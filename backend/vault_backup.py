"""Backups of the client vault, built to survive the ways backups usually fail.

The vault is one folder on one machine and FAIS wants records kept five years.
A dead laptop currently costs the practice everything. This is the unglamorous
part that protects all the rest.

Four decisions, each aimed at a specific way this goes wrong:

**Snapshots, not a mirror.** A mirror faithfully propagates a deletion or a
corruption — delete a client file by accident and the next sync destroys the
only other copy. Snapshots are immutable once written, so an older one still
has the file.

**Content-addressed.** Every unique file is stored once under the hash of its
own contents. Repeat backups copy only what changed, which is what makes this
cheap enough to actually run; and because an object's name IS its checksum,
silent corruption is detectable rather than assumed away.

**The database is copied through SQLite, not off the disk.** Copying a live
.db file mid-write gives you a plausible-looking file that will not open. The
sqlite backup API takes a consistent snapshot of an in-use database.

**Verify is a first-class operation.** A backup nobody has restored is a
hypothesis. `verify` re-hashes every object a snapshot references, and
`restore` writes to a new directory so it can be tested without risking the
live vault.

Deliberately NOT encrypted. Key management done badly loses the archive more
reliably than no backup at all, and the correct answer here is a destination
the operating system already encrypts (BitLocker, FileVault, LUKS). The
backup contains client data in the clear: treat the destination exactly as you
treat the vault.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

CHUNK = 1 << 20
LAYOUT = "objects"
SNAPSHOTS = "snapshots"

# Files that are caches or locks, not records. Backing up a journal alongside
# an already-consistent database copy would restore an inconsistent pair.
SKIP_NAMES = {".DS_Store", "Thumbs.db"}
SKIP_SUFFIXES = {".tmp", ".part", ".crdownload", "-journal", "-wal", "-shm"}


class BackupError(RuntimeError):
    pass


@dataclass
class Entry:
    path: str            # relative to the vault root, POSIX separators
    digest: str
    size: int


@dataclass
class Snapshot:
    id: str
    created_at: str
    source: str
    entries: List[Entry] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def bytes_total(self) -> int:
        return sum(e.size for e in self.entries)


def _hash_file(path: Path) -> Tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            block = handle.read(CHUNK)
            if not block:
                break
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _object_path(root: Path, digest: str) -> Path:
    return root / LAYOUT / digest[:2] / digest


def _skip(path: Path) -> bool:
    if path.name in SKIP_NAMES:
        return True
    return any(path.name.endswith(suffix) for suffix in SKIP_SUFFIXES)


def _consistent_db_copy(db_path: Path, into: Path) -> Optional[Path]:
    """A snapshot of a live SQLite file, taken through SQLite itself.

    Copying the bytes of an open database can catch it mid-transaction and
    produce a file that opens to an error months later, when it is the only
    copy left.
    """
    if not db_path.exists():
        return None
    target = into / db_path.name
    source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        dest = sqlite3.connect(target)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()
    return target


def _walk(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and not _skip(path):
            yield path


def back_up(source: Path, dest: Path, *, note: str = "") -> Snapshot:
    """Take a snapshot of `source` into the archive at `dest`."""
    source, dest = Path(source), Path(dest)
    if not source.exists():
        raise BackupError(f"Nothing to back up: {source} does not exist.")
    if dest.resolve() == source.resolve() or dest.resolve().is_relative_to(source.resolve()):
        # An archive inside the vault dies with the vault, and each backup
        # would then back up the previous one.
        raise BackupError(
            "The backup destination must be outside the vault, on a different "
            "drive or machine. An archive inside the vault is not a backup."
        )

    (dest / LAYOUT).mkdir(parents=True, exist_ok=True)
    (dest / SNAPSHOTS).mkdir(parents=True, exist_ok=True)

    entries: List[Entry] = []
    notes: List[str] = [note] if note else []
    stored = 0

    staged = dest / ".staging"
    if staged.exists():
        shutil.rmtree(staged)
    staged.mkdir(parents=True)
    try:
        for db in sorted(source.glob("*.db")):
            copy = _consistent_db_copy(db, staged)
            if copy:
                digest, size = _hash_file(copy)
                stored += _store(dest, copy, digest)
                entries.append(Entry(db.name, digest, size))
                notes.append(f"{db.name} copied through SQLite for consistency")

        for path in _walk(source):
            if path.suffix == ".db" and path.parent == source:
                continue                      # already taken, consistently
            digest, size = _hash_file(path)
            stored += _store(dest, path, digest)
            entries.append(Entry(path.relative_to(source).as_posix(), digest, size))
    finally:
        shutil.rmtree(staged, ignore_errors=True)

    snap = Snapshot(
        id=_next_id(dest),
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source=str(source),
        entries=sorted(entries, key=lambda e: e.path),
        notes=notes + [f"{len(entries)} files, {stored} newly stored"],
    )
    _write_snapshot(dest, snap)
    _write_readme(dest)
    return snap


def _next_id(dest: Path) -> str:
    """A snapshot id that is not already taken.

    Ids are timestamps to the second, and two backups inside the same second
    used to write the same filename — the second silently replaced the first.
    Snapshots being immutable is the property that lets an older one still hold
    a file deleted from the vault, so a collision quietly destroys the point of
    the whole design.
    """
    base = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = Path(dest) / SNAPSHOTS
    if not (folder / f"{base}.json").exists():
        return base
    for suffix in range(2, 1000):
        candidate = f"{base}-{suffix}"
        if not (folder / f"{candidate}.json").exists():
            return candidate
    raise BackupError(f"Too many snapshots in the same second as {base}.")


def _store(dest: Path, path: Path, digest: str) -> int:
    """Put a file in the object store. Returns 1 if it was new."""
    target = _object_path(dest, digest)
    if target.exists():
        return 0                              # identical content already held
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".incoming")
    shutil.copyfile(path, tmp)
    # Rename last, so an interrupted copy never becomes a valid-looking object.
    tmp.replace(target)
    return 1


def _write_snapshot(dest: Path, snap: Snapshot) -> Path:
    path = dest / SNAPSHOTS / f"{snap.id}.json"
    payload = {
        "id": snap.id,
        "created_at": snap.created_at,
        "source": snap.source,
        "notes": snap.notes,
        "entries": [{"path": e.path, "sha256": e.digest, "size": e.size}
                    for e in snap.entries],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_snapshot(dest: Path, snapshot_id: str = "") -> Snapshot:
    """A snapshot by id, or the most recent one."""
    found = snapshots(dest)
    if not found:
        raise BackupError(f"No snapshots in {dest}.")
    if not snapshot_id:
        return found[-1]
    for snap in found:
        if snap.id == snapshot_id:
            return snap
    raise BackupError(f"No snapshot {snapshot_id!r} in {dest}.")


def _order_key(snapshot_id: str) -> Tuple[str, int]:
    """Sort key for a snapshot id.

    Ids look like 20260902T071507Z, and a second one taken in the same second
    is 20260902T071507Z-2. Sorted as plain strings, "Z-2" lands BEFORE "Z", so
    "the newest snapshot" would resolve to the oldest — and a restore with no
    id given would quietly rebuild the wrong day.
    """
    base, _, suffix = snapshot_id.partition("-")
    return base, int(suffix) if suffix.isdigit() else 1


def snapshots(dest: Path) -> List[Snapshot]:
    """Every snapshot, genuinely oldest first."""
    folder = Path(dest) / SNAPSHOTS
    out: List[Snapshot] = []
    for path in sorted(folder.glob("*.json"), key=lambda p: _order_key(p.stem)) if folder.exists() else []:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out.append(Snapshot(
            id=str(raw.get("id") or path.stem),
            created_at=str(raw.get("created_at") or ""),
            source=str(raw.get("source") or ""),
            entries=[Entry(e["path"], e["sha256"], int(e.get("size") or 0))
                     for e in raw.get("entries") or []],
            notes=[str(n) for n in raw.get("notes") or []],
        ))
    return out


@dataclass
class Verdict:
    ok: bool
    checked: int = 0
    missing: List[str] = field(default_factory=list)
    corrupt: List[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.ok:
            return f"{self.checked} files verified, all intact."
        parts = []
        if self.missing:
            parts.append(f"{len(self.missing)} missing")
        if self.corrupt:
            parts.append(f"{len(self.corrupt)} corrupt")
        return f"{self.checked} files checked: " + ", ".join(parts) + "."


def verify(dest: Path, snapshot_id: str = "", *, deep: bool = True) -> Verdict:
    """Check a snapshot is actually restorable.

    An object's filename is the hash of its contents, so re-hashing detects
    the bit rot and truncated copies that a size-and-date check misses. `deep`
    is on by default: the cheap check is the one that tells you everything is
    fine right up until the day it matters.
    """
    dest = Path(dest)
    snap = load_snapshot(dest, snapshot_id)
    verdict = Verdict(ok=True)
    for entry in snap.entries:
        verdict.checked += 1
        obj = _object_path(dest, entry.digest)
        if not obj.exists():
            verdict.missing.append(entry.path)
            continue
        if deep:
            digest, size = _hash_file(obj)
            if digest != entry.digest or size != entry.size:
                verdict.corrupt.append(entry.path)
    verdict.ok = not verdict.missing and not verdict.corrupt
    return verdict


def verify_archive(dest: Path, *, deep: bool = True) -> Verdict:
    """Check every object any snapshot references, not just the newest.

    Verifying one snapshot is not verifying the archive. An object kept only
    by an older snapshot — the copy of a file since deleted from the vault,
    which is exactly what snapshots are for — can rot without the newest
    snapshot noticing. This is what `--verify` runs, because "verify my
    backup" does not mean "verify the most recent third of it".
    """
    dest = Path(dest)
    found = snapshots(dest)
    if not found:
        raise BackupError(f"No snapshots in {dest}.")
    verdict = Verdict(ok=True)
    seen: Dict[str, str] = {}          # digest -> a path that references it
    for snap in found:
        for entry in snap.entries:
            seen.setdefault(entry.digest, f"{snap.id}:{entry.path}")
    for digest, where in sorted(seen.items()):
        verdict.checked += 1
        obj = _object_path(dest, digest)
        if not obj.exists():
            verdict.missing.append(where)
            continue
        if deep and _hash_file(obj)[0] != digest:
            verdict.corrupt.append(where)
    verdict.ok = not verdict.missing and not verdict.corrupt
    return verdict


def restore(dest: Path, into: Path, snapshot_id: str = "",
            *, overwrite: bool = False) -> List[str]:
    """Rebuild a snapshot into `into`. Returns the paths written.

    Restores to a NEW directory by default and refuses a non-empty one. The
    moment a restore can write over the live vault, a mistyped command during
    an emergency destroys the thing being recovered.

    Every object is re-hashed as it is written, so a restore fails loudly
    rather than producing a subtly wrong vault.
    """
    dest, into = Path(dest), Path(into)
    snap = load_snapshot(dest, snapshot_id)
    if into.exists() and any(into.iterdir()) and not overwrite:
        raise BackupError(
            f"{into} is not empty. Restore into a new directory and compare it "
            "with the live vault before replacing anything."
        )
    written: List[str] = []
    for entry in snap.entries:
        obj = _object_path(dest, entry.digest)
        if not obj.exists():
            raise BackupError(
                f"Snapshot {snap.id} references a missing object for "
                f"{entry.path}. Run verify — this archive is incomplete."
            )
        digest, _size = _hash_file(obj)
        if digest != entry.digest:
            raise BackupError(
                f"{entry.path} is corrupt in the archive (hash mismatch). "
                "Restore an earlier snapshot."
            )
        target = into / entry.path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(obj, target)
        written.append(entry.path)
    return written


def prune(dest: Path, keep: int = 12) -> List[str]:
    """Drop old snapshots and any object nothing references any more.

    Kept deliberately conservative: snapshots are small, objects are shared,
    and the whole point of snapshots is being able to go back. `keep` counts
    snapshots, not days, so an archive that has not run in months still holds
    its history.
    """
    dest = Path(dest)
    found = snapshots(dest)
    if keep < 1 or len(found) <= keep:
        return []
    doomed = found[: len(found) - keep]
    for snap in doomed:
        (dest / SNAPSHOTS / f"{snap.id}.json").unlink(missing_ok=True)

    live = {e.digest for snap in snapshots(dest) for e in snap.entries}
    removed: List[str] = []
    objects = dest / LAYOUT
    for obj in sorted(objects.rglob("*")) if objects.exists() else []:
        if obj.is_file() and obj.name not in live:
            obj.unlink(missing_ok=True)
            removed.append(obj.name)
    return [s.id for s in doomed] + removed


README = """# Fortitudo vault backup

This directory is a backup of a FAIS client vault. **It contains client
personal information in the clear.** Treat it exactly as you treat the vault:
keep it on an encrypted volume (BitLocker, FileVault, LUKS), and do not put it
anywhere the vault itself would not be allowed to go.

## What is here

- `objects/` — every unique file, stored once under the SHA-256 of its own
  contents. A file's name IS its checksum, so corruption is detectable.
- `snapshots/` — one manifest per backup run, listing every path and its hash.
  Snapshots are immutable, so deleting a file from the vault does not delete
  it from here.

## Restoring

    python vault_backup.py --restore <this directory> --into <new empty dir>

It restores to a NEW directory on purpose. Compare it with the live vault
before replacing anything.

## Checking it still works

    python vault_backup.py --verify <this directory>

Run this occasionally. A backup nobody has restored is a hypothesis.
"""


def _write_readme(dest: Path) -> None:
    (Path(dest) / "README.md").write_text(README, encoding="utf-8")


def main() -> int:
    import argparse
    from config import DATA_ROOT

    ap = argparse.ArgumentParser(description="Back up, verify or restore the client vault.")
    ap.add_argument("--to", help="archive directory to back up into")
    ap.add_argument("--source", default=str(DATA_ROOT), help="vault to back up")
    ap.add_argument("--verify", metavar="ARCHIVE",
                    help="check every object in an archive (or one --snapshot)")
    ap.add_argument("--restore", metavar="ARCHIVE", help="archive to restore from")
    ap.add_argument("--into", help="empty directory to restore into")
    ap.add_argument("--snapshot", default="", help="snapshot id (default: newest)")
    ap.add_argument("--list", metavar="ARCHIVE", help="list snapshots")
    ap.add_argument("--prune", metavar="ARCHIVE", help="drop old snapshots")
    ap.add_argument("--keep", type=int, default=12)
    ap.add_argument("--note", default="")
    args = ap.parse_args()

    if args.list:
        for snap in snapshots(Path(args.list)):
            print(f"{snap.id}  {snap.created_at}  {len(snap.entries):5d} files  "
                  f"{snap.bytes_total / 1e6:8.1f} MB")
        return 0

    if args.verify:
        verdict = (verify(Path(args.verify), args.snapshot) if args.snapshot
                   else verify_archive(Path(args.verify)))
        print(verdict.summary())
        for path in verdict.missing:
            print(f"  MISSING  {path}")
        for path in verdict.corrupt:
            print(f"  CORRUPT  {path}")
        return 0 if verdict.ok else 1

    if args.restore:
        if not args.into:
            print("--restore needs --into <new empty directory>")
            return 2
        written = restore(Path(args.restore), Path(args.into), args.snapshot)
        print(f"Restored {len(written)} files into {args.into}")
        print("Compare it with the live vault before replacing anything.")
        return 0

    if args.prune:
        dropped = prune(Path(args.prune), args.keep)
        print(f"Pruned {len(dropped)} snapshots/objects, kept the newest {args.keep}.")
        return 0

    if not args.to:
        ap.print_help()
        return 2

    snap = back_up(Path(args.source), Path(args.to), note=args.note)
    print(f"Snapshot {snap.id}: {len(snap.entries)} files, "
          f"{snap.bytes_total / 1e6:.1f} MB")
    verdict = verify_archive(Path(args.to))
    print(verdict.summary())
    return 0 if verdict.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
