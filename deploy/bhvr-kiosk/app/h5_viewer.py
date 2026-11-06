"""In-kiosk H5 viewer helpers (grill H5_VIEWER_GRILL — MVP).

Sandbox paths under data_root; tree/attrs/preview; pack-now planning.
HTTP routes live in ``main.py``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app import h5_archive

_TEXT_PREVIEW_CAP = 256 * 1024
_PTS_PREVIEW_N = 64
_TS_STEM_RE = re.compile(r"^(?P<head>.+)__p(?P<part>\d{3})$")


def realpath_under(root: Path, path: Path) -> Path:
    """Resolve ``path``; raise ValueError if outside ``root`` (symlink-safe)."""
    root_r = root.resolve()
    path_r = path.resolve()
    try:
        path_r.relative_to(root_r)
    except ValueError as exc:
        raise ValueError(f"path escapes data_root: {path}") from exc
    return path_r


def session_catalog(data_root: Path) -> dict[str, Path]:
    from app.kiosk_settings import list_session_folders

    return {r["name"]: Path(r["path"]) for r in list_session_folders(data_root)}


def resolve_session_dir(data_root: Path, session: str) -> Path:
    """``session`` is the display name from ``list_session_folders`` (may include subdir/)."""
    name = (session or "").strip().replace("\\", "/")
    if not name or name.startswith("/") or ".." in name.split("/"):
        raise ValueError("invalid session id")
    catalog = session_catalog(data_root)
    if name not in catalog:
        raise FileNotFoundError(f"unknown session: {name}")
    return realpath_under(data_root, catalog[name])


def resolve_h5_file(data_root: Path, session: str, file: str) -> Path:
    folder = resolve_session_dir(data_root, session)
    base = Path(file).name
    if base != file or not base.endswith(".h5") or not base:
        raise ValueError("file must be a .h5 basename")
    path = folder / base
    if not path.is_file():
        raise FileNotFoundError(f"missing h5: {base}")
    return realpath_under(data_root, path)


def active_folder_path(active_json: Path) -> Path | None:
    if not active_json.is_file():
        return None
    try:
        data = json.loads(active_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    folder = str(data.get("folder") or "").strip()
    if not folder:
        return None
    try:
        return Path(folder).resolve()
    except OSError:
        return None


def is_active_session_dir(folder: Path, active_json: Path) -> bool:
    active = active_folder_path(active_json)
    if active is None:
        return False
    try:
        return folder.resolve() == active
    except OSError:
        return False


def parse_loose_ts_stem(stem: str) -> dict[str, Any] | None:
    """Parse ``{subject}__{tag}__{cam}__pNNN`` (or legacy ``{subject}__{cam}__pNNN``)."""
    m = _TS_STEM_RE.match(stem)
    if not m:
        return None
    head = m.group("head")
    part = int(m.group("part"))
    bits = head.split("__")
    if len(bits) >= 3:
        subject_id, recording_tag, cam_id = bits[0], bits[1], bits[2]
    elif len(bits) == 2:
        subject_id, cam_id = bits[0], bits[1]
        recording_tag = "ses"
    else:
        return None
    if not subject_id or not cam_id:
        return None
    return {
        "subject_id": subject_id,
        "recording_tag": recording_tag or "ses",
        "cam_id": cam_id,
        "part": part,
        "stem": stem,
    }


def list_session_h5_files(folder: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in sorted(folder.glob("*.h5")):
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        rows.append({"name": p.name, "bytes": size})
    return rows


def list_loose_ts(folder: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in sorted(folder.glob("*.ts")):
        parsed = parse_loose_ts_stem(p.stem)
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        rows.append(
            {
                "name": p.name,
                "bytes": size,
                "parsed": parsed,
            }
        )
    return rows


def _attr_dict(obj: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in obj.attrs:
        v = obj.attrs[k]
        if hasattr(v, "tolist"):
            try:
                v = v.tolist()
            except Exception:  # noqa: BLE001
                v = str(v)
        elif isinstance(v, bytes):
            v = v.decode("utf-8", errors="replace")
        elif hasattr(v, "item") and getattr(v, "shape", ()) == ():
            v = v.item()
        out[str(k)] = v
    return out


def build_tree(h5_path: Path) -> dict[str, Any]:
    h5_archive.require_h5py()
    import h5py

    def walk(group: Any, prefix: str) -> list[dict[str, Any]]:
        kids: list[dict[str, Any]] = []
        for name in group:
            obj = group[name]
            path = f"{prefix}/{name}" if prefix else name
            if isinstance(obj, h5py.Dataset):
                kids.append(
                    {
                        "name": name,
                        "path": path,
                        "type": "dataset",
                        "shape": list(obj.shape),
                        "dtype": str(obj.dtype),
                        "bytes": int(obj.size * obj.dtype.itemsize)
                        if obj.size
                        else 0,
                        "description": str(obj.attrs.get("description") or ""),
                    }
                )
            else:
                kids.append(
                    {
                        "name": name,
                        "path": path,
                        "type": "group",
                        "description": str(obj.attrs.get("description") or ""),
                        "children": walk(obj, path),
                    }
                )
        return kids

    with h5py.File(h5_path, "r") as f:
        return {
            "file": h5_path.name,
            "attrs": _attr_dict(f),
            "description": str(f.attrs.get("description") or ""),
            "children": walk(f, ""),
        }


def mpegts_parts(h5_path: Path) -> list[dict[str, Any]]:
    h5_archive.require_h5py()
    import h5py

    parts: list[dict[str, Any]] = []
    with h5py.File(h5_path, "r") as f:
        if "video" not in f:
            return parts
        video = f["video"]
        for name in sorted(video.keys()):
            if not name.startswith("mpegts_"):
                continue
            ds = video[name]
            try:
                part = int(name.split("_", 1)[1])
            except ValueError:
                part = -1
            parts.append(
                {
                    "name": name,
                    "path": f"video/{name}",
                    "part": part,
                    "bytes": int(ds.shape[0]) if ds.shape else 0,
                }
            )
    return parts


def dataset_exists(h5_path: Path, dataset_path: str) -> bool:
    h5_archive.require_h5py()
    import h5py

    with h5py.File(h5_path, "r") as f:
        return dataset_path in f


def normalize_dataset_path(path: str) -> str:
    p = (path or "").strip().strip("/")
    if not p or ".." in p.split("/") or p.startswith("/"):
        raise ValueError("invalid dataset path")
    return p


def node_detail(h5_path: Path, dataset_path: str) -> dict[str, Any]:
    h5_archive.require_h5py()
    import h5py
    import numpy as np

    dpath = normalize_dataset_path(dataset_path)
    with h5py.File(h5_path, "r") as f:
        if dpath not in f:
            raise FileNotFoundError(dpath)
        obj = f[dpath]
        if isinstance(obj, h5py.Group):
            return {
                "path": dpath,
                "type": "group",
                "attrs": _attr_dict(obj),
                "preview": None,
            }
        info: dict[str, Any] = {
            "path": dpath,
            "type": "dataset",
            "shape": list(obj.shape),
            "dtype": str(obj.dtype),
            "attrs": _attr_dict(obj),
            "preview": None,
        }
        # mpegts: no text preview (play via raw)
        if dpath.startswith("video/mpegts_"):
            info["preview"] = {"kind": "mpegts", "bytes": int(obj.shape[0])}
            return info
        # float pts table
        if "float" in str(obj.dtype) or "int" in str(obj.dtype):
            n = int(obj.shape[0]) if obj.ndim >= 1 else 0
            if n == 0:
                info["preview"] = {"kind": "empty"}
                return info
            head_n = min(_PTS_PREVIEW_N, n)
            head = [float(x) for x in obj[:head_n]]
            tail: list[float] = []
            if n > head_n:
                tail = [float(x) for x in obj[-min(16, n - head_n) :]]
            info["preview"] = {
                "kind": "numeric",
                "n": n,
                "head": head,
                "tail": tail,
            }
            return info
        # uint8 / bytes → text (capped)
        if obj.dtype == np.uint8 or (obj.dtype.kind in ("S", "O") and obj.ndim <= 1):
            n = int(obj.shape[0]) if obj.ndim >= 1 else 0
            if n <= 0:
                info["preview"] = {"kind": "empty"}
                return info
            cap = min(n, _TEXT_PREVIEW_CAP)
            raw = bytes(obj[:cap])
            truncated = n > cap
            text = raw.decode("utf-8", errors="replace")
            info["preview"] = {
                "kind": "text",
                "text": text,
                "truncated": truncated,
                "bytes": len(raw),
            }
            return info
        info["preview"] = {"kind": "unsupported", "dtype": str(obj.dtype)}
        return info


def plan_pack_now(folder: Path, *, force: bool = False) -> list[dict[str, Any]]:
    """Plan per-cam pack jobs for every loose ``*.ts`` (skip existing unless force)."""
    h5_archive.require_h5py()
    import h5py

    items: list[dict[str, Any]] = []
    by_cam: dict[str, list[dict[str, Any]]] = {}
    for ts in sorted(folder.glob("*.ts")):
        parsed = parse_loose_ts_stem(ts.stem)
        if not parsed or ts.stat().st_size <= 0:
            continue
        cam = str(parsed["cam_id"])
        by_cam.setdefault(cam, []).append({"ts": ts, **parsed})

    for cam, parts in by_cam.items():
        parts.sort(key=lambda r: int(r["part"]))
        max_part = max(int(r["part"]) for r in parts)
        # Prefer existing H5 for this cam; else create path from first part meta.
        existing = sorted(folder.glob(f"*__{cam}.h5"))
        preferred = [p for p in existing if not p.name.startswith("unknown__")]
        if preferred:
            h5_path = preferred[-1]
        else:
            sample = parts[0]
            h5_path = h5_archive.cam_h5_path(
                folder,
                str(sample["subject_id"]),
                cam,
                recording_tag=str(sample["recording_tag"]),
            )
        for row in parts:
            part = int(row["part"])
            name = f"mpegts_{part:03d}"
            exists = False
            if h5_path.is_file():
                with h5py.File(h5_path, "r") as f:
                    exists = "video" in f and name in f["video"]
            if exists and not force:
                items.append(
                    {
                        "action": "skip",
                        "cam_id": cam,
                        "part": part,
                        "ts_path": row["ts"],
                        "h5_path": h5_path,
                        "subject_id": row["subject_id"],
                        "recording_tag": row["recording_tag"],
                    }
                )
                continue
            items.append(
                {
                    "action": "pack",
                    "cam_id": cam,
                    "part": part,
                    "ts_path": row["ts"],
                    "pts_path": row["ts"].with_suffix(".pts"),
                    "h5_path": h5_path,
                    "subject_id": row["subject_id"],
                    "recording_tag": row["recording_tag"],
                    "pack_session_sidecars": part == max_part,
                    "skip_if_exists": False if force else True,
                    "create_shell": not h5_path.is_file(),
                }
            )
    return items
