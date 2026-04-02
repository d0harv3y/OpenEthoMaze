from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import h5py
import numpy as np

from ..defaults import QC_IMAGE_PREVIEW_MAX_DIM, QC_IMAGE_STORE_FORMAT
from ._shared import ensure_group, open_db, safe_str
from .trial_key import TrialKey


def write_qc_image(
    db_path: Optional[Path],
    key: TrialKey,
    name: str,
    image: np.ndarray,
    attrs: Optional[dict[str, Any]] = None,
) -> None:
    """Write a QC image to the database."""
    with open_db(db_path, "a") as h5:
        g_qc = ensure_group(h5[key.path()], "qc_images")
        if name in g_qc:
            del g_qc[name]

        arr = np.asarray(image, dtype=np.uint8)
        max_dim = int(QC_IMAGE_PREVIEW_MAX_DIM) if QC_IMAGE_PREVIEW_MAX_DIM else 0
        if max_dim > 0:
            h = int(arr.shape[0]) if arr.ndim >= 2 else 0
            w = int(arr.shape[1]) if arr.ndim >= 2 else 0
            cur_max = max(h, w)
            if cur_max > max_dim and h > 0 and w > 0:
                scale = float(max_dim) / float(cur_max)
                new_w = max(1, int(round(w * scale)))
                new_h = max(1, int(round(h * scale)))
                try:
                    import cv2

                    arr = cv2.resize(arr, (new_w, new_h), interpolation=cv2.INTER_AREA)
                except Exception:
                    step = max(1, int(np.ceil(cur_max / max_dim)))
                    arr = arr[::step, ::step, :] if arr.ndim == 3 else arr[::step, ::step]

        store_format = (QC_IMAGE_STORE_FORMAT or "png_bytes").strip().lower()
        ds: h5py.Dataset
        if store_format == "png_bytes":
            try:
                import cv2

                ok, enc = cv2.imencode(".png", arr)
                if ok and enc is not None:
                    payload = np.asarray(enc, dtype=np.uint8)
                    ds = g_qc.create_dataset(name, data=payload, compression="gzip")
                    ds.attrs["CLASS"] = "IMAGE"
                    ds.attrs["ENCODING"] = "png"
                else:
                    ds = g_qc.create_dataset(name, data=arr, compression="gzip")
                    ds.attrs["CLASS"] = "IMAGE"
                    ds.attrs["ENCODING"] = "raw"
            except Exception:
                ds = g_qc.create_dataset(name, data=arr, compression="gzip")
                ds.attrs["CLASS"] = "IMAGE"
                ds.attrs["ENCODING"] = "raw"
        else:
            ds = g_qc.create_dataset(name, data=arr, compression="gzip")
            ds.attrs["CLASS"] = "IMAGE"
            ds.attrs["ENCODING"] = "raw"

        if attrs:
            for k, v in attrs.items():
                try:
                    ds.attrs[k] = v
                except Exception:
                    ds.attrs[k] = safe_str(v)


def read_qc_image(
    db_path: Optional[Path],
    key: TrialKey,
    name: str,
) -> Optional[np.ndarray]:
    """Read a QC image from the database."""
    try:
        with open_db(db_path, "r") as h5:
            ds = h5[key.path()]["qc_images"][name]
            enc = safe_str(ds.attrs.get("ENCODING", "raw")).lower()
            data = ds[:]
            if enc == "png":
                try:
                    import cv2

                    decoded = cv2.imdecode(np.asarray(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
                    if decoded is not None:
                        return decoded
                except Exception:
                    pass
            return data
    except (KeyError, ValueError):
        return None
