"""
HDF5 read/write for tracking v2 groups (``tracking/anatomical``, ``tracking/blob``).

See ``docs/h5_tracking_contract.md``.

**Batch I/O (T0)** — :func:`write_anatomical_tracking`, :func:`read_anatomical_tracking`,
:func:`write_blob_tracking`, :func:`read_blob_tracking`.

**Acquisition buffer (T1a)** — :class:`AnatomicalTrackingBuffer` accumulates per-camera-tick
pose rows during a trial; :meth:`~AnatomicalTrackingBuffer.append_frame` stores
``frame_index``, per-node ``x`` / ``y`` / ``score`` / ``valid``; :meth:`~AnatomicalTrackingBuffer.flush`
writes ``tracking/anatomical`` via :func:`write_anatomical_tracking` and bumps schema to v2.
:class:`BlobTrackingBuffer` mirrors this for ``tracking/blob`` (T1d).
Module-level :func:`append_anatomical_frame` and :func:`flush_anatomical_tracking_buffer`
are thin wrappers for callers that prefer a functional style.

Empty buffers skip HDF5 writes on flush (no partial ``tracking/`` group).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

import h5py
import numpy as np

from maze.core.anatomy import BLOB_NODE_NAMES, BLOB_VERTEX_COUNT
from maze.core.h5_layout import ensure_group, write_json_attr
from maze.core.schema import (
    CONTROLLER_SCHEMA_VERSION_V2,
    TRACKING_ANATOMICAL_GROUP,
    TRACKING_BLOB_GROUP,
    TRACKING_BLOB_HEADING_DATASET,
    TRACKING_BLOB_XY_DATASET,
    TRACKING_FRAME_INDEX_DATASET,
    TRACKING_GROUP,
    TRACKING_SCORE_DATASET,
    TRACKING_VALID_DATASET,
    TRACKING_X_DATASET,
    TRACKING_Y_DATASET,
)

PoseSource = Literal["sleap_live", "sleap_import", "dlc_import"]
BlobSource = Literal["backup_live", "offline_retrack"]


def _decode_attr(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def _load_json_attr(group: h5py.Group, attr_name: str) -> Any:
    raw = group.attrs.get(attr_name)
    if raw is None:
        return None
    raw = _decode_attr(raw)
    return json.loads(str(raw))


def _write_dataset(group: h5py.Group, name: str, data: np.ndarray) -> h5py.Dataset:
    if name in group:
        del group[name]
    return group.create_dataset(name, data=data, compression="gzip")


def ensure_controller_schema_v2(h5: h5py.File) -> None:
    """Set ``metadata/controller_schema_version`` to v2 when tracking groups are written."""
    meta = ensure_group(h5, "metadata")
    meta.attrs["controller_schema_version"] = CONTROLLER_SCHEMA_VERSION_V2


def has_tracking_group(g_trial: h5py.Group) -> bool:
    """Return True when the trial group contains a ``tracking/`` child."""
    return TRACKING_GROUP in g_trial


def has_anatomical_tracking(g_trial: h5py.Group) -> bool:
    """Return True when ``tracking/anatomical`` exists with required datasets."""
    g_tracking = g_trial.get(TRACKING_GROUP)
    if g_tracking is None or TRACKING_ANATOMICAL_GROUP not in g_tracking:
        return False
    g_anat = g_tracking[TRACKING_ANATOMICAL_GROUP]
    return (
        TRACKING_FRAME_INDEX_DATASET in g_anat
        and TRACKING_X_DATASET in g_anat
        and TRACKING_Y_DATASET in g_anat
        and TRACKING_SCORE_DATASET in g_anat
    )


@dataclass(frozen=True)
class AnatomicalTrackingData:
    """Dense per-frame anatomical pose from ``tracking/anatomical``."""

    frame_index: np.ndarray
    x: np.ndarray
    y: np.ndarray
    score: np.ndarray
    node_names: tuple[str, ...]
    pose_source: str
    fps: float
    valid: np.ndarray | None = None
    pose_model_path: str = ""


@dataclass(frozen=True)
class BlobTrackingData:
    """Backup blob polygon from ``tracking/blob``."""

    frame_index: np.ndarray
    xy: np.ndarray
    valid: np.ndarray
    heading_rad: np.ndarray
    score: np.ndarray
    node_names: tuple[str, ...]
    blob_source: str
    n_vertices: int
    backup_params_json: dict[str, Any] | None = None


@dataclass
class AnatomicalTrackingBuffer:
    """
    In-memory accumulator for live anatomical pose during acquisition.

    Append one row per camera tick, then :meth:`flush` to ``tracking/anatomical`` at trial
    ``stop()``. Metadata (``node_names``, ``pose_source``, ``fps``) is fixed at construction.
    """

    node_names: tuple[str, ...] | list[str]
    pose_source: PoseSource
    fps: float
    pose_model_path: str = ""
    _frame_indices: list[int] = field(default_factory=list, init=False, repr=False)
    _x_rows: list[np.ndarray] = field(default_factory=list, init=False, repr=False)
    _y_rows: list[np.ndarray] = field(default_factory=list, init=False, repr=False)
    _score_rows: list[np.ndarray] = field(default_factory=list, init=False, repr=False)
    _valid_rows: list[np.ndarray] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self.node_names = tuple(str(n) for n in self.node_names)
        if not self.node_names:
            raise ValueError("node_names must be non-empty")

    @property
    def frame_count(self) -> int:
        return len(self._frame_indices)

    def append_frame(
        self,
        frame_index: int,
        x: np.ndarray,
        y: np.ndarray,
        score: np.ndarray,
        valid: np.ndarray | None = None,
    ) -> None:
        """Append one anatomical pose row aligned to ``frame_index``."""
        k = len(self.node_names)
        x_arr = np.asarray(x, dtype=np.float32).reshape(-1)
        y_arr = np.asarray(y, dtype=np.float32).reshape(-1)
        score_arr = np.asarray(score, dtype=np.float32).reshape(-1)
        if x_arr.shape != (k,) or y_arr.shape != (k,) or score_arr.shape != (k,):
            raise ValueError(
                f"x/y/score must each be shape ({k},); got {x_arr.shape}, {y_arr.shape}, {score_arr.shape}"
            )

        self._frame_indices.append(int(frame_index))
        self._x_rows.append(x_arr)
        self._y_rows.append(y_arr)
        self._score_rows.append(score_arr)
        if valid is not None:
            valid_arr = np.asarray(valid, dtype=np.uint8).reshape(-1)
            if valid_arr.shape != (k,):
                raise ValueError(f"valid shape {valid_arr.shape} != ({k},)")
            self._valid_rows.append(valid_arr)

    def clear(self) -> None:
        """Discard buffered frames without writing HDF5."""
        self._frame_indices.clear()
        self._x_rows.clear()
        self._y_rows.clear()
        self._score_rows.clear()
        self._valid_rows.clear()

    def flush(
        self,
        g_trial: h5py.Group,
        *,
        h5: h5py.File | None = None,
    ) -> h5py.Group | None:
        """
        Write buffered frames to ``tracking/anatomical``.

        Returns the anatomical group, or ``None`` when the buffer is empty (no HDF5 write).
        """
        if not self._frame_indices:
            return None

        valid = None
        if self._valid_rows:
            if len(self._valid_rows) != len(self._frame_indices):
                raise RuntimeError("valid row count mismatch")
            valid = np.stack(self._valid_rows, axis=0)

        return write_anatomical_tracking(
            g_trial,
            frame_index=np.asarray(self._frame_indices, dtype=np.uint32),
            x=np.stack(self._x_rows, axis=0),
            y=np.stack(self._y_rows, axis=0),
            score=np.stack(self._score_rows, axis=0),
            valid=valid,
            node_names=self.node_names,
            pose_source=self.pose_source,
            fps=self.fps,
            pose_model_path=self.pose_model_path,
            h5=h5,
        )


def append_anatomical_frame(
    buffer: AnatomicalTrackingBuffer,
    frame_index: int,
    x: np.ndarray,
    y: np.ndarray,
    score: np.ndarray,
    valid: np.ndarray | None = None,
) -> None:
    """Append one frame to an :class:`AnatomicalTrackingBuffer`."""
    buffer.append_frame(frame_index, x, y, score, valid)


def flush_anatomical_tracking_buffer(
    buffer: AnatomicalTrackingBuffer,
    g_trial: h5py.Group,
    *,
    h5: h5py.File | None = None,
) -> h5py.Group | None:
    """Flush an :class:`AnatomicalTrackingBuffer` to ``tracking/anatomical``."""
    return buffer.flush(g_trial, h5=h5)


@dataclass
class BlobTrackingBuffer:
    """
    In-memory accumulator for live backup-tracker blob polygons during acquisition.

    Append one row per camera tick, then :meth:`flush` to ``tracking/blob`` at trial
    ``stop()``. ``backup_params_json`` is frozen at construction for offline re-track.
    """

    backup_params_json: dict[str, Any]
    blob_source: BlobSource = "backup_live"
    _frame_indices: list[int] = field(default_factory=list, init=False, repr=False)
    _xy_rows: list[np.ndarray] = field(default_factory=list, init=False, repr=False)
    _valid_rows: list[int] = field(default_factory=list, init=False, repr=False)
    _heading_rows: list[float] = field(default_factory=list, init=False, repr=False)
    _score_rows: list[float] = field(default_factory=list, init=False, repr=False)

    @property
    def frame_count(self) -> int:
        return len(self._frame_indices)

    def append_frame(
        self,
        frame_index: int,
        xy: np.ndarray,
        *,
        valid: bool,
        heading_rad: float,
        score: float,
    ) -> None:
        """Append one oriented blob polygon row aligned to ``frame_index``."""
        xy_arr = np.asarray(xy, dtype=np.float32)
        if xy_arr.shape != (BLOB_VERTEX_COUNT, 2):
            raise ValueError(f"xy shape {xy_arr.shape} != ({BLOB_VERTEX_COUNT}, 2)")

        self._frame_indices.append(int(frame_index))
        self._xy_rows.append(xy_arr)
        self._valid_rows.append(1 if valid else 0)
        self._heading_rows.append(float(heading_rad))
        self._score_rows.append(float(score))

    def clear(self) -> None:
        """Discard buffered frames without writing HDF5."""
        self._frame_indices.clear()
        self._xy_rows.clear()
        self._valid_rows.clear()
        self._heading_rows.clear()
        self._score_rows.clear()

    def flush(
        self,
        g_trial: h5py.Group,
        *,
        h5: h5py.File | None = None,
    ) -> h5py.Group | None:
        """Write buffered frames to ``tracking/blob``; return ``None`` when empty."""
        if not self._frame_indices:
            return None

        return write_blob_tracking(
            g_trial,
            frame_index=np.asarray(self._frame_indices, dtype=np.uint32),
            xy=np.stack(self._xy_rows, axis=0),
            valid=np.asarray(self._valid_rows, dtype=np.uint8),
            heading_rad=np.asarray(self._heading_rows, dtype=np.float32),
            score=np.asarray(self._score_rows, dtype=np.float32),
            blob_source=self.blob_source,
            backup_params_json=self.backup_params_json,
            h5=h5,
        )


def write_anatomical_tracking(
    g_trial: h5py.Group,
    *,
    frame_index: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    score: np.ndarray,
    node_names: tuple[str, ...] | list[str],
    pose_source: PoseSource,
    fps: float,
    pose_model_path: str = "",
    valid: np.ndarray | None = None,
    h5: h5py.File | None = None,
) -> h5py.Group:
    """
    Write or replace ``tracking/anatomical`` under a trial group.

    When ``h5`` is provided, bumps ``metadata/controller_schema_version`` to v2.
    """
    frame_index_arr = np.asarray(frame_index, dtype=np.uint32)
    x_arr = np.asarray(x, dtype=np.float32)
    y_arr = np.asarray(y, dtype=np.float32)
    score_arr = np.asarray(score, dtype=np.float32)

    t = frame_index_arr.shape[0]
    if x_arr.shape != (t, len(node_names)):
        raise ValueError(f"x shape {x_arr.shape} != ({t}, {len(node_names)})")
    if y_arr.shape != x_arr.shape:
        raise ValueError(f"y shape {y_arr.shape} != x shape {x_arr.shape}")
    if score_arr.shape != x_arr.shape:
        raise ValueError(f"score shape {score_arr.shape} != x shape {x_arr.shape}")

    g_tracking = g_trial.require_group(TRACKING_GROUP)
    g_anat = g_tracking.require_group(TRACKING_ANATOMICAL_GROUP)

    _write_dataset(g_anat, TRACKING_FRAME_INDEX_DATASET, frame_index_arr)
    _write_dataset(g_anat, TRACKING_X_DATASET, x_arr)
    _write_dataset(g_anat, TRACKING_Y_DATASET, y_arr)
    _write_dataset(g_anat, TRACKING_SCORE_DATASET, score_arr)
    if valid is not None:
        valid_arr = np.asarray(valid, dtype=np.uint8)
        if valid_arr.shape != x_arr.shape:
            raise ValueError(f"valid shape {valid_arr.shape} != x shape {x_arr.shape}")
        _write_dataset(g_anat, TRACKING_VALID_DATASET, valid_arr)
    elif TRACKING_VALID_DATASET in g_anat:
        del g_anat[TRACKING_VALID_DATASET]

    write_json_attr(g_anat, "node_names", list(node_names))
    g_anat.attrs["pose_source"] = pose_source
    g_anat.attrs["fps"] = float(fps)
    if pose_model_path:
        g_anat.attrs["pose_model_path"] = pose_model_path
    elif "pose_model_path" in g_anat.attrs:
        del g_anat.attrs["pose_model_path"]

    if h5 is not None:
        ensure_controller_schema_v2(h5)

    return g_anat


def read_anatomical_tracking(g_trial: h5py.Group) -> AnatomicalTrackingData | None:
    """Read ``tracking/anatomical``; return None when absent or incomplete."""
    if not has_anatomical_tracking(g_trial):
        return None

    g_anat = g_trial[TRACKING_GROUP][TRACKING_ANATOMICAL_GROUP]
    node_names_raw = _load_json_attr(g_anat, "node_names")
    if not isinstance(node_names_raw, list):
        return None

    valid = None
    if TRACKING_VALID_DATASET in g_anat:
        valid = g_anat[TRACKING_VALID_DATASET][:].astype(np.uint8, copy=False)

    return AnatomicalTrackingData(
        frame_index=g_anat[TRACKING_FRAME_INDEX_DATASET][:].astype(np.uint32, copy=False),
        x=g_anat[TRACKING_X_DATASET][:].astype(np.float32, copy=False),
        y=g_anat[TRACKING_Y_DATASET][:].astype(np.float32, copy=False),
        score=g_anat[TRACKING_SCORE_DATASET][:].astype(np.float32, copy=False),
        valid=valid,
        node_names=tuple(str(n) for n in node_names_raw),
        pose_source=str(_decode_attr(g_anat.attrs.get("pose_source", ""))),
        pose_model_path=str(_decode_attr(g_anat.attrs.get("pose_model_path", ""))),
        fps=float(g_anat.attrs.get("fps", 0.0)),
    )


def write_blob_tracking(
    g_trial: h5py.Group,
    *,
    frame_index: np.ndarray,
    xy: np.ndarray,
    valid: np.ndarray,
    heading_rad: np.ndarray,
    score: np.ndarray,
    blob_source: BlobSource,
    backup_params_json: dict[str, Any] | None = None,
    h5: h5py.File | None = None,
) -> h5py.Group:
    """
    Write or replace ``tracking/blob`` under a trial group.

    Vertex count is fixed at ``BLOB_VERTEX_COUNT`` (8). When ``h5`` is provided,
    bumps ``metadata/controller_schema_version`` to v2.
    """
    frame_index_arr = np.asarray(frame_index, dtype=np.uint32)
    xy_arr = np.asarray(xy, dtype=np.float32)
    valid_arr = np.asarray(valid, dtype=np.uint8)
    heading_arr = np.asarray(heading_rad, dtype=np.float32)
    score_arr = np.asarray(score, dtype=np.float32)

    t = frame_index_arr.shape[0]
    if xy_arr.shape != (t, BLOB_VERTEX_COUNT, 2):
        raise ValueError(f"xy shape {xy_arr.shape} != ({t}, {BLOB_VERTEX_COUNT}, 2)")
    for name, arr in (
        ("valid", valid_arr),
        ("heading_rad", heading_arr),
        ("score", score_arr),
    ):
        if arr.shape != (t,):
            raise ValueError(f"{name} shape {arr.shape} != ({t},)")

    g_tracking = g_trial.require_group(TRACKING_GROUP)
    g_blob = g_tracking.require_group(TRACKING_BLOB_GROUP)

    _write_dataset(g_blob, TRACKING_FRAME_INDEX_DATASET, frame_index_arr)
    _write_dataset(g_blob, TRACKING_BLOB_XY_DATASET, xy_arr)
    _write_dataset(g_blob, TRACKING_VALID_DATASET, valid_arr)
    _write_dataset(g_blob, TRACKING_BLOB_HEADING_DATASET, heading_arr)
    _write_dataset(g_blob, TRACKING_SCORE_DATASET, score_arr)

    g_blob.attrs["n_vertices"] = BLOB_VERTEX_COUNT
    g_blob.attrs["blob_source"] = blob_source
    write_json_attr(g_blob, "node_names", list(BLOB_NODE_NAMES))
    if backup_params_json is not None:
        write_json_attr(g_blob, "backup_params_json", backup_params_json)
    elif "backup_params_json" in g_blob.attrs:
        del g_blob.attrs["backup_params_json"]

    if h5 is not None:
        ensure_controller_schema_v2(h5)

    return g_blob


def read_blob_tracking(g_trial: h5py.Group) -> BlobTrackingData | None:
    """Read ``tracking/blob``; return None when absent or incomplete."""
    g_tracking = g_trial.get(TRACKING_GROUP)
    if g_tracking is None or TRACKING_BLOB_GROUP not in g_tracking:
        return None

    g_blob = g_tracking[TRACKING_BLOB_GROUP]
    required = (
        TRACKING_FRAME_INDEX_DATASET,
        TRACKING_BLOB_XY_DATASET,
        TRACKING_VALID_DATASET,
        TRACKING_BLOB_HEADING_DATASET,
        TRACKING_SCORE_DATASET,
    )
    if not all(name in g_blob for name in required):
        return None

    node_names_raw = _load_json_attr(g_blob, "node_names")
    if not isinstance(node_names_raw, list):
        return None

    backup_params = _load_json_attr(g_blob, "backup_params_json")
    if backup_params is not None and not isinstance(backup_params, dict):
        backup_params = None

    return BlobTrackingData(
        frame_index=g_blob[TRACKING_FRAME_INDEX_DATASET][:].astype(np.uint32, copy=False),
        xy=g_blob[TRACKING_BLOB_XY_DATASET][:].astype(np.float32, copy=False),
        valid=g_blob[TRACKING_VALID_DATASET][:].astype(np.uint8, copy=False),
        heading_rad=g_blob[TRACKING_BLOB_HEADING_DATASET][:].astype(np.float32, copy=False),
        score=g_blob[TRACKING_SCORE_DATASET][:].astype(np.float32, copy=False),
        node_names=tuple(str(n) for n in node_names_raw),
        blob_source=str(_decode_attr(g_blob.attrs.get("blob_source", ""))),
        n_vertices=int(g_blob.attrs.get("n_vertices", BLOB_VERTEX_COUNT)),
        backup_params_json=backup_params,
    )
