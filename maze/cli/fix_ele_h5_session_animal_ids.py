"""
Relabel Squishware ELE HDF5 first-session trials after animal-ID typo.

Moves session groups from wrong top-level animal IDs to the correct ones
(e.g. /3275/S01 -> /3375/S01) and removes empty mislabeled animal groups.

Usage:
    uv run maze-fix-ele-h5-session-animal-ids PATH\\to\\file.hdf5 --dry-run
    uv run maze-fix-ele-h5-session-animal-ids PATH\\to\\file.hdf5 \\
        --map 3275=3375 3276=3376 --sessions S01
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

import h5py


def _copy_group(src: h5py.Group, dest_parent: h5py.Group, name: str) -> h5py.Group:
    """Deep-copy a group (and attrs) under dest_parent/name."""
    if name in dest_parent:
        raise ValueError(f"Destination already exists: {dest_parent.name}/{name}")
    dest = dest_parent.create_group(name)
    for key, val in src.attrs.items():
        dest.attrs[key] = val
    for key, item in src.items():
        src.file.copy(item, dest, key)
    return dest


def apply_remap(
    h5_path: Path,
    mapping: dict[str, str],
    sessions: set[str],
    *,
    dry_run: bool,
) -> None:
    with h5py.File(h5_path, "a") as h5:
        for wrong_id, correct_id in mapping.items():
            if wrong_id not in h5:
                print(f"  skip {wrong_id}: not in file")
                continue
            g_wrong = h5[wrong_id]
            if not isinstance(g_wrong, h5py.Group):
                raise TypeError(f"/{wrong_id} is not a group")
            g_correct = h5[correct_id] if correct_id in h5 else h5.create_group(correct_id)

            for sess in sorted(g_wrong.keys()):
                if sess not in sessions:
                    continue
                src_path = f"/{wrong_id}/{sess}"
                dst_path = f"/{correct_id}/{sess}"
                if sess in g_correct:
                    raise ValueError(f"Destination session exists: {dst_path}")
                print(f"  {'would move' if dry_run else 'move'} {src_path} -> {dst_path}")
                if not dry_run:
                    _copy_group(g_wrong[sess], g_correct, sess)
                    del g_wrong[sess]

            remaining = list(g_wrong.keys())
            if not remaining:
                print(f"  {'would delete' if dry_run else 'delete'} empty /{wrong_id}")
                if not dry_run:
                    del h5[wrong_id]
            else:
                print(f"  keep /{wrong_id} (remaining sessions: {remaining})")


def parse_mapping(pairs: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Expected OLD=NEW, got {pair!r}")
        old, new = pair.split("=", 1)
        old, new = old.strip(), new.strip()
        if not old or not new:
            raise ValueError(f"Invalid mapping {pair!r}")
        out[old] = new
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Fix mislabeled ELE HDF5 animal IDs for selected sessions.")
    ap.add_argument("h5_path", type=Path, help="Squishware ELE .hdf5 / .h5 file")
    ap.add_argument(
        "--map",
        nargs="+",
        default=["3275=3375", "3276=3376"],
        help="OLD=NEW animal ID remaps (default: 3275=3375 3276=3376)",
    )
    ap.add_argument(
        "--sessions",
        nargs="+",
        default=["S01"],
        help="Session IDs to move from wrong animals (default: S01)",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print actions only")
    ap.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip timestamped .bak copy beside the file",
    )
    args = ap.parse_args()

    h5_path = args.h5_path.resolve()
    if not h5_path.is_file():
        raise SystemExit(f"Not found: {h5_path}")

    mapping = parse_mapping(args.map)
    sessions = set(args.sessions)

    print(f"File: {h5_path}")
    print(f"Mapping: {mapping}")
    print(f"Sessions: {sorted(sessions)}")

    if not args.dry_run and not args.no_backup:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = h5_path.with_suffix(h5_path.suffix + f".bak_{ts}")
        print(f"Backup: {backup}")
        shutil.copy2(h5_path, backup)

    apply_remap(h5_path, mapping, sessions, dry_run=args.dry_run)
    print("Done." if not args.dry_run else "Dry run complete.")


if __name__ == "__main__":
    main()
