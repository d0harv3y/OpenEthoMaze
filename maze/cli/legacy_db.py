"""
Legacy VAST database manager: init/sync DB and manifest from file discovery and
treatment_labels.csv; run inference, pipeline, and exports on selected trials.

All outputs go to ``<repo>/outputs/legacy/`` (override with ``--db-path``):
  - vast_results_legacy.h5   (database)
  - trial_manifest_legacy.csv (manifest; columns from maze.pipeline.io.file_discovery.MANIFEST_CSV_FIELDNAMES)
  - exports/                 (CSV exports from run-exports)

Discovery uses ``maze.pipeline.paths`` ``DATA_DIRS`` (or ``--data-dir``); per-machine roots belong in
``paths_local.py``. Cohort labels live beside discovery roots as ``treatment_labels.csv`` (legacy VAST adapter).

Usage:
  uv run maze-legacy-db init
  uv run maze-legacy-db sync [--update-labels] [--no-backup] [--dry-run]
  uv run maze-legacy-db run-inference --model PATH [--animal-id ID ...] [--session S01] [--trial T01]
  uv run maze-legacy-db run-pipeline [--animal-id ID ...] [--session S01] [--trial T01] [--no-qc]
  uv run maze-legacy-db run-exports [--animal-id ID ...] [--session S01] [--trial T01] [--include-mistrials]
  uv run maze-legacy-db build-kpms-h5 [--data-dir PATH] [--db-path PATH] [--profile PATH] [--animal-id ID ...]
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

# -----------------------------------------------------------------------------
# Imports (legacy VAST source adapter + shared pipeline surfaces)
# -----------------------------------------------------------------------------
from maze.pipeline.paths import DATA_DIRS
from maze.pipeline.sources.legacy_vast import (
    TrialManifest,
    apply_treatment_labels,
    check_duplicates,
    discover_trials,
    load_manifest_csv,
    load_treatment_labels,
    save_manifest_csv,
    update_treatment_labels_from_discovery,
)
from maze.pipeline.io.input_h5_loader import load_trial_data, load_trial_settings
from maze.pipeline.db import (
    TrialKey,
    delete_animal_group,
    delete_trial_group,
    ensure_trial_group,
    init_database,
    list_trials,
    read_trial_meta_for_manifest,
    trial_has_settings,
    write_animal_label,
    write_feedback_series,
    write_trial_frame_counts,
    write_trial_settings,
    write_sleap_model_path,
    write_sleap_path,
    write_trial_manifest_rows,
)
from maze.pipeline.run_pipeline import (
    load_manifests_from_db,
    run_pipeline,
    run_single_trial,
)
from maze.pipeline.exports import export_all
from maze.pipeline.build_tracking_h5 import (
    build_tracking_h5,
    default_kpms_tracking_db,
    manifest_path_for_db,
)
from maze.pipeline.offline_tracking import offline_blob_params_from_fallback
from maze.controller.acquisition.profile import load_fallback_tracking_from_profile
from maze.repo_paths import REPO_ROOT

LEGACY_DIR = REPO_ROOT / "outputs" / "legacy"
LEGACY_DB = LEGACY_DIR / "vast_results_legacy.h5"
LEGACY_MANIFEST = LEGACY_DIR / "trial_manifest_legacy.csv"
DEFAULT_KPMS_TRACKING_DB = default_kpms_tracking_db(REPO_ROOT)
LABELS_PATH = REPO_ROOT / "inputs" / "treatment_labels.csv"
INFERRED_ID_MAPPINGS_PATH = REPO_ROOT / "inputs" / "inferred_id_mappings.csv"

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def _set_legacy_paths(db_path: Optional[Path] = None) -> None:
    """Set global legacy output paths, optionally overriding DB location."""
    global LEGACY_DIR, LEGACY_DB, LEGACY_MANIFEST
    if db_path is None:
        return
    LEGACY_DB = Path(db_path).expanduser().resolve()
    LEGACY_DIR = LEGACY_DB.parent
    LEGACY_MANIFEST = LEGACY_DIR / "trial_manifest_legacy.csv"


def _ensure_legacy_dir() -> None:
    LEGACY_DIR.mkdir(parents=True, exist_ok=True)


def _compact_h5_file(path: Path) -> None:
    """Rewrite an HDF5 file into a compact copy and replace in-place."""
    import h5py

    tmp_path = Path(str(path) + ".compact_tmp")
    if tmp_path.exists():
        tmp_path.unlink()
    with h5py.File(path, "r") as src, h5py.File(tmp_path, "w") as dst:
        for k, v in src.attrs.items():
            dst.attrs[k] = v
        for key in src.keys():
            src.copy(key, dst)
    tmp_path.replace(path)


def _get_video_frame_count(video_path: Path) -> Optional[int]:
    if not HAS_CV2:
        return None
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        return frame_count if frame_count > 0 else None
    except Exception:
        return None


def _apply_inferred_ids_from_csv(result) -> int:
    """Apply inferred_id from inputs/inferred_id_mappings.csv if present. Returns count applied."""
    if not INFERRED_ID_MAPPINGS_PATH.exists():
        return 0
    mappings = {}
    with open(INFERRED_ID_MAPPINGS_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["original_id"], row["session"], row["trial"])
            mappings[key] = row["inferred_id"]
    n = 0
    for trial in result.trials:
        key = (trial.animal_id, trial.session, trial.trial)
        if key in mappings:
            trial.inferred_id = mappings[key]
            n += 1
    return n


def _filter_manifests(
    manifests: list[TrialManifest],
    animal_ids: Optional[list[str]],
    sessions: Optional[list[str]],
    trials: Optional[list[str]],
) -> list[TrialManifest]:
    out = list(manifests)
    if animal_ids:
        out = [m for m in out if m.animal_id in animal_ids]
    if sessions:
        out = [m for m in out if m.session in sessions]
    if trials:
        out = [m for m in out if m.trial in trials]
    return out


def _expand_filter_arg(vals: Optional[list[str]]) -> Optional[list[str]]:
    if not vals:
        return None
    out = []
    for v in vals:
        out.extend(x.strip() for x in str(v).replace(",", " ").split() if x.strip())
    return out if out else None


def _resolve_data_dirs(data_dirs: Optional[Sequence[Path]]) -> Optional[list[Path]]:
    if not data_dirs:
        return None
    out = [Path(p) for p in data_dirs if str(p).strip()]
    return out or None


def _normalize_session(s: str) -> str:
    if s and s[0].upper() in ("S", "H"):
        return s
    return f"S{int(s):02d}" if s.isdigit() else s


def _normalize_trial(s: str) -> str:
    if s and s[0].upper() == "T":
        return s
    return f"T{int(s):02d}" if s.isdigit() else s


# -----------------------------------------------------------------------------
# Subcommand: init
# -----------------------------------------------------------------------------
def cmd_init(*, data_dirs: Optional[Sequence[Path]] = None) -> None:
    """Initialize legacy DB and manifest from discovery + treatment_labels.csv."""
    _ensure_legacy_dir()
    print(f"Initializing legacy database: {LEGACY_DB}")
    resolved_data_dirs = _resolve_data_dirs(data_dirs)
    print(f"Data directories: {resolved_data_dirs or DATA_DIRS}")
    print(f"Treatment labels: {LABELS_PATH}")
    print()

    init_database(LEGACY_DB)
    print("Created metadata structure")

    print("\nDiscovering trials...")
    result = discover_trials(resolved_data_dirs)
    print(f"  Input H5: {len(result.input_h5_files)}, Videos: {len(result.video_files)}, SLEAP: {len(result.sleap_files)}")
    print(f"  Total trials: {len(result.trials)}, Matched videos: {result.n_matched_videos}, Matched SLEAP: {result.n_matched_sleap}")

    duplicates = check_duplicates(result)
    if duplicates:
        print(f"\nWARNING: {len(duplicates)} duplicate trial keys (first 5):")
        for key, trials in duplicates[:5]:
            print(f"  {key}: {[t.input_h5_path for t in trials]}")

    print("\nLoading treatment labels...")
    labels = load_treatment_labels(LABELS_PATH)
    apply_treatment_labels(result, labels)
    n_strain = sum(1 for t in result.trials if t.strain)
    n_experiment = sum(1 for t in result.trials if t.experiment)
    print(f"  With strain: {n_strain}, With experiment: {n_experiment}")

    n_inferred = _apply_inferred_ids_from_csv(result)
    if n_inferred:
        print(f"\nApplied {n_inferred} inferred IDs from {INFERRED_ID_MAPPINGS_PATH.name}")

    print("\nCreating trial groups and loading source data...")
    if not HAS_CV2:
        print("  Note: cv2 not available, video frame counts will not be extracted")
    counts = {"timestamps": 0, "h5_frames": 0, "video_frames": 0, "settings_failures": 0}

    for trial in result.trials:
        key = TrialKey.from_manifest(trial)
        ensure_trial_group(
            LEGACY_DB,
            key,
            video_path=str(trial.video_path) if trial.video_path else None,
            sleap_path=str(trial.sleap_path) if trial.sleap_path else None,
            input_h5_path=str(trial.input_h5_path),
        )
        h5_fps = None
        try:
            settings = load_trial_settings(
                trial.input_h5_path,
                trial.animal_id,
                trial.h5_session,
                trial.trial,
            )
            trial.timestamp = settings.timestamp
            if settings.timestamp:
                counts["timestamps"] += 1
            trial_start_frame = None
            h5_data = None
            try:
                h5_data = load_trial_data(
                    trial.input_h5_path,
                    trial.animal_id,
                    trial.h5_session,
                    trial.trial,
                )
                if h5_data.fps > 0:
                    h5_fps = h5_data.fps
                trial.h5_n_frames = h5_data.n_frames
                if h5_data.n_frames > 0:
                    counts["h5_frames"] += 1
                trial_start_frame = h5_data.trial_start_frame
            except Exception:
                pass
            timestamp_str = settings.timestamp.isoformat() if settings.timestamp else None
            write_trial_settings(
                LEGACY_DB,
                key,
                arena_radius_px=settings.arena_radius_px,
                px_per_cm=settings.px_per_cm,
                arena_center_x_px=settings.arena_center_x_px,
                arena_center_y_px=settings.arena_center_y_px,
                timestamp=timestamp_str,
                stage=settings.stage,
                color=settings.color,
                exit_number=settings.exit_number,
                exit_x=settings.exit_x,
                exit_y=settings.exit_y,
                roi_old=settings.roi_old,
                h5_fps=h5_fps,
                trial_start_frame=trial_start_frame,
            )
            if h5_data is not None and h5_data.n_frames > 0:
                start = trial_start_frame if trial_start_frame is not None else 0
                start = min(start, h5_data.n_frames)
                w_analysis = h5_data.w[start:]
                m_analysis = h5_data.m[start:]
                if len(w_analysis) > 0 and len(w_analysis) == len(m_analysis):
                    try:
                        write_feedback_series(LEGACY_DB, key, w_analysis, m_analysis)
                    except Exception:
                        pass
        except Exception as e:
            counts["settings_failures"] += 1
            print(f"  Warning: {key.path()}: {e}")

        if trial.video_path and trial.video_path.exists():
            n_frames = _get_video_frame_count(trial.video_path)
            if n_frames is not None:
                trial.video_n_frames = n_frames
                counts["video_frames"] += 1

        if trial.h5_n_frames is not None and trial.video_n_frames is not None:
            try:
                write_trial_frame_counts(LEGACY_DB, key, trial.h5_n_frames, trial.video_n_frames)
            except Exception:
                pass

    print(f"  Trial groups: {len(result.trials)} (timestamps: {counts['timestamps']}, h5_frames: {counts['h5_frames']}, video_frames: {counts['video_frames']}, settings_failures: {counts['settings_failures']})")

    print("\nWriting animal labels...")
    unique_animals = set()
    for trial in result.trials:
        animal_id = trial.effective_animal_id
        if animal_id in unique_animals:
            continue
        unique_animals.add(animal_id)
        write_animal_label(
            LEGACY_DB,
            animal_id,
            strain=trial.strain,
            experiment=trial.experiment,
            sex=trial.sex,
            tx=trial.tx,
            researcher=trial.researcher,
            drug=trial.drug,
        )
    print(f"  Wrote labels for {len(unique_animals)} animals")

    save_manifest_csv(result, LEGACY_MANIFEST)
    write_trial_manifest_rows(LEGACY_DB, result.trials)
    print(f"\nDatabase: {LEGACY_DB}")
    print(f"Manifest: {LEGACY_MANIFEST}")


# -----------------------------------------------------------------------------
# Subcommand: sync
# -----------------------------------------------------------------------------
def cmd_sync(
    update_labels: bool,
    no_backup: bool,
    dry_run: bool,
    prune_unlabeled: bool,
    *,
    data_dirs: Optional[Sequence[Path]] = None,
) -> None:
    """Sync legacy DB and manifest with discovery; optionally prune and update labels."""
    from tqdm import tqdm

    if dry_run:
        print("Dry run: no backup or DB writes.")
        print()

    had_existing_db = LEGACY_DB.exists() and LEGACY_DB.stat().st_size > 0
    if not dry_run:
        _ensure_legacy_dir()
        if not no_backup and LEGACY_DB.exists():
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = Path(str(LEGACY_DB) + f".backup_{ts}")
            shutil.copy(LEGACY_DB, backup)
            print(f"Backed up to {backup}\n")
        if not LEGACY_DB.exists() or LEGACY_DB.stat().st_size == 0:
            init_database(LEGACY_DB)
            print(f"Initialized {LEGACY_DB}\n")

    resolved_data_dirs = _resolve_data_dirs(data_dirs)
    print(f"Discovering trials in: {resolved_data_dirs or DATA_DIRS}")
    result = discover_trials(resolved_data_dirs)
    print(f"  Trials: {len(result.trials)}\n")

    if update_labels and not dry_run:
        update_treatment_labels_from_discovery(result, LABELS_PATH)
        print()

    print("Loading and applying treatment labels...")
    labels = load_treatment_labels(LABELS_PATH)
    apply_treatment_labels(result, labels)
    labeled_animal_ids = {
        key for key, label in labels.items() if getattr(label, "type", "animal_id") == "animal_id"
    }
    print()

    discovery_key_set = {(t.animal_id, t.phase, t.session, t.trial) for t in result.trials}

    if not dry_run:
        print("Syncing trial groups and paths...")
        for trial in tqdm(result.trials, desc="Syncing", unit="trial"):
            key = TrialKey.from_manifest(trial)
            ensure_trial_group(
                LEGACY_DB,
                key,
                video_path=str(trial.video_path) if trial.video_path else None,
                sleap_path=str(trial.sleap_path) if trial.sleap_path else None,
                input_h5_path=str(trial.input_h5_path),
            )
            if trial_has_settings(LEGACY_DB, key):
                continue
            try:
                settings = load_trial_settings(
                    trial.input_h5_path,
                    trial.animal_id,
                    trial.h5_session,
                    trial.trial,
                )
                trial.timestamp = settings.timestamp
                h5_data = None
                trial_start_frame = None
                try:
                    h5_data = load_trial_data(
                        trial.input_h5_path,
                        trial.animal_id,
                        trial.h5_session,
                        trial.trial,
                    )
                    trial.h5_n_frames = h5_data.n_frames
                    trial_start_frame = h5_data.trial_start_frame
                except Exception:
                    pass
                timestamp_str = settings.timestamp.isoformat() if settings.timestamp else None
                write_trial_settings(
                    LEGACY_DB,
                    key,
                    arena_radius_px=settings.arena_radius_px,
                    px_per_cm=settings.px_per_cm,
                    arena_center_x_px=settings.arena_center_x_px,
                    arena_center_y_px=settings.arena_center_y_px,
                    timestamp=timestamp_str,
                    stage=settings.stage,
                    color=settings.color,
                    exit_number=settings.exit_number,
                    exit_x=settings.exit_x,
                    exit_y=settings.exit_y,
                    roi_old=settings.roi_old,
                    h5_fps=h5_data.fps if h5_data and h5_data.fps > 0 else None,
                    trial_start_frame=trial_start_frame,
                )
                if h5_data and h5_data.n_frames > 0:
                    start = trial_start_frame if trial_start_frame is not None else 0
                    start = min(start, h5_data.n_frames)
                    w_analysis = h5_data.w[start:]
                    m_analysis = h5_data.m[start:]
                    if len(w_analysis) > 0 and len(w_analysis) == len(m_analysis):
                        write_feedback_series(LEGACY_DB, key, w_analysis, m_analysis)
            except Exception:
                pass
            if trial.video_path and trial.video_path.exists():
                n_frames = _get_video_frame_count(trial.video_path)
                if n_frames is not None:
                    trial.video_n_frames = n_frames
        print(f"  Ensured {len(result.trials)} trial groups\n")
        print("Writing animal labels...")
        unique_animals = set()
        for trial in result.trials:
            aid = trial.effective_animal_id
            if aid in unique_animals:
                continue
            unique_animals.add(aid)
            write_animal_label(
                LEGACY_DB,
                aid,
                strain=trial.strain,
                experiment=trial.experiment,
                sex=trial.sex,
                tx=trial.tx,
                researcher=trial.researcher,
                drug=trial.drug,
            )
        print(f"  Wrote labels for {len(unique_animals)} animals\n")

    db_trials = list_trials(LEGACY_DB) if LEGACY_DB.exists() else []
    to_prune = [t for t in db_trials if (t.animal_id, t.phase, t.session, t.trial) not in discovery_key_set]
    animals_to_remove = {
        aid for aid in {t.animal_id for t in to_prune}
        if not any(t.animal_id == aid for t in result.trials)
    }
    if prune_unlabeled and not dry_run:
        unlabeled_animals = {
            aid
            for aid in {t.animal_id for t in db_trials}
            if labeled_animal_ids and aid not in labeled_animal_ids
        }
        if unlabeled_animals:
            print(f"Pruning unlabeled animals (no row in treatment_labels.csv): {len(unlabeled_animals)}")
            animals_to_remove |= unlabeled_animals

    if to_prune or animals_to_remove:
        if dry_run:
            print("Would prune:")
            for t in to_prune:
                print(f"  Trial: {t.path()}")
            for aid in sorted(animals_to_remove):
                print(f"  Animal: {aid}")
        else:
            for t in to_prune:
                delete_trial_group(LEGACY_DB, t)
            for aid in sorted(animals_to_remove):
                delete_animal_group(LEGACY_DB, aid)
            print(f"Pruned {len(to_prune)} trial(s), removed {len(animals_to_remove)} animal group(s).")
    else:
        print("Nothing to prune.")

    if not dry_run:
        def _norm(s):
            return (s or "").strip()
        if LEGACY_MANIFEST.exists():
            existing = load_manifest_csv(LEGACY_MANIFEST)
            by_key = {(_norm(m.animal_id), _norm(m.session), _norm(m.trial)): m for m in existing}
            for t in result.trials:
                k = (_norm(t.animal_id), _norm(t.session), _norm(t.trial))
                if k in by_key:
                    m = by_key[k]
                    t.timestamp = m.timestamp
                    t.h5_n_frames = m.h5_n_frames
                    t.video_n_frames = m.video_n_frames
                    t.inferred_id = m.inferred_id
        if LEGACY_DB.exists():
            for t in result.trials:
                if t.timestamp is not None and t.video_n_frames is not None:
                    continue
                key = TrialKey.from_manifest(t)
                try:
                    db_ts, db_n = read_trial_meta_for_manifest(LEGACY_DB, key)
                    if t.timestamp is None and db_ts is not None:
                        t.timestamp = db_ts
                    if t.video_n_frames is None and db_n is not None:
                        t.video_n_frames = db_n
                except Exception:
                    pass
        for t in result.trials:
            if t.h5_n_frames is not None and t.video_n_frames is not None:
                try:
                    write_trial_frame_counts(LEGACY_DB, TrialKey.from_manifest(t), t.h5_n_frames, t.video_n_frames)
                except Exception:
                    pass
        save_manifest_csv(result, LEGACY_MANIFEST)
        write_trial_manifest_rows(LEGACY_DB, result.trials)
        if had_existing_db:
            print("Compacting database file...")
            _compact_h5_file(LEGACY_DB)
            print("  Database compacted.")
        print(f"Manifest saved: {LEGACY_MANIFEST}")
    print(f"Sync complete: {LEGACY_DB}")


# -----------------------------------------------------------------------------
# Subcommand: run-inference
# -----------------------------------------------------------------------------
def _run_sleap_inference(
    video_path: Path,
    output_path: Path,
    model_path: Path,
    batch_size: int,
    device: str,
) -> bool:
    try:
        from sleap_nn.predict import run_inference
    except ImportError as e:
        print("sleap_nn not available. Run from sleap-nn env: uv run --project <sleap-nn-dir> python ...", file=sys.stderr)
        raise e
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_inference(
        data_path=str(video_path),
        model_paths=[str(model_path)],
        output_path=str(output_path),
        batch_size=batch_size,
        device=device,
        no_empty_frames=True,
    )
    return True


def cmd_run_inference(
    model_path: Path,
    animal_ids: Optional[list[str]],
    sessions: Optional[list[str]],
    trials: Optional[list[str]],
    output_dir: Optional[Path],
    batch_size: int,
    device: str,
    skip_existing: bool,
    dry_run: bool,
) -> None:
    if not LEGACY_DB.exists():
        print(f"Error: Database not found: {LEGACY_DB}. Run init first.", file=sys.stderr)
        sys.exit(1)
    if not model_path.exists() or not (model_path / "best.ckpt").exists():
        print(f"Error: Model path must contain best.ckpt: {model_path}", file=sys.stderr)
        sys.exit(1)

    manifests = load_manifests_from_db(LEGACY_DB)
    manifests = _filter_manifests(manifests, animal_ids, sessions, trials)
    with_video = [m for m in manifests if m.video_path and m.video_path.exists()]
    if not with_video:
        print("No trials with video to process.")
        return

    print(f"Running SLEAP-NN inference: {len(with_video)} trial(s), model={model_path}")
    if dry_run:
        planned = 0
        for m in with_video:
            out = output_dir / m.video_path.with_suffix(".predictions.slp").name if output_dir else m.video_path.with_suffix(".predictions.slp")
            if skip_existing and out.exists():
                continue
            print(f"  {m.trial_key} -> {out}")
            planned += 1
        if planned == 0:
            print("No trials would run (all outputs already exist).")
        return

    stats = {"success": 0, "failed": 0, "skipped": 0}
    for i, m in enumerate(with_video, 1):
        out_path = (output_dir / m.video_path.with_suffix(".predictions.slp").name) if output_dir else m.video_path.with_suffix(".predictions.slp")
        if skip_existing and out_path.exists():
            print(f"[{i}/{len(with_video)}] Skip (exists): {m.trial_key}")
            stats["skipped"] += 1
            continue
        print(f"[{i}/{len(with_video)}] {m.trial_key} -> {out_path}")
        try:
            start = time.perf_counter()
            _run_sleap_inference(m.video_path, out_path, model_path, batch_size, device)
            elapsed = time.perf_counter() - start
            print(f"  Done in {elapsed:.2f} s")
            stats["success"] += 1
            try:
                key = TrialKey.from_manifest(m)
                write_sleap_path(LEGACY_DB, key, str(out_path.resolve()))
                write_sleap_model_path(LEGACY_DB, key, str(model_path.resolve()))
            except Exception as e:
                print(f"  Warning: could not write sleap_path to DB: {e}")
        except Exception as e:
            print(f"  Failed: {e}", file=sys.stderr)
            stats["failed"] += 1

    print(f"Done: {stats['success']} success, {stats['skipped']} skipped, {stats['failed']} failed")
    if stats["failed"]:
        sys.exit(1)


# -----------------------------------------------------------------------------
# Subcommand: run-pipeline
# -----------------------------------------------------------------------------
def cmd_run_pipeline(
    animal_ids: Optional[list[str]],
    sessions: Optional[list[str]],
    trials: Optional[list[str]],
    no_qc: bool,
    no_skip_mistrials: bool,
    workers: int,
) -> None:
    if not LEGACY_DB.exists():
        print(f"Error: Database not found: {LEGACY_DB}. Run init first.", file=sys.stderr)
        sys.exit(1)

    sessions_norm = [_normalize_session(s) for s in sessions] if sessions else None
    trials_norm = [_normalize_trial(t) for t in trials] if trials else None

    if animal_ids and len(animal_ids) == 1 and sessions_norm and len(sessions_norm) == 1 and trials_norm and len(trials_norm) == 1:
        ok = run_single_trial(
            animal_id=animal_ids[0],
            session=sessions_norm[0],
            trial=trials_norm[0],
            db_path=LEGACY_DB,
            generate_qc=not no_qc,
        )
        sys.exit(0 if ok else 1)

    stats = run_pipeline(
        db_path=LEGACY_DB,
        animal_ids=animal_ids,
        sessions=sessions_norm,
        trial_names=trials_norm,
        generate_qc=not no_qc,
        skip_mistrials=not no_skip_mistrials,
        max_workers=workers,
        prefilter_mode="legacy",
    )
    if stats.get("failed", 0) > 0:
        sys.exit(1)


# -----------------------------------------------------------------------------
# Subcommand: run-exports
# -----------------------------------------------------------------------------
def cmd_run_exports(
    animal_ids: Optional[list[str]],
    sessions: Optional[list[str]],
    trials: Optional[list[str]],
    include_mistrials: bool,
) -> None:
    if not LEGACY_DB.exists():
        print(f"Error: Database not found: {LEGACY_DB}. Run init (and pipeline) first.", file=sys.stderr)
        sys.exit(1)

    output_dir = LEGACY_DIR / "exports"
    # export_all does not support per-trial filter; it exports all trials in DB.
    # If user passed filters, we could in theory filter the DB read inside export_all,
    # but the current export_all API does not support that. So we export all and note it.
    if animal_ids or sessions or trials:
        print("Note: run-exports currently exports all trials in the DB; id/session/trial filters are not applied to CSV export.")
    exports = export_all(LEGACY_DB, output_dir, include_mistrials=include_mistrials)
    print("Generated files:")
    for name, path in exports.items():
        print(f"  {name}: {path}")


# -----------------------------------------------------------------------------
# Subcommand: build-kpms-h5
# -----------------------------------------------------------------------------
def cmd_build_kpms_h5(
    *,
    db_path: Path,
    data_dirs: Optional[Sequence[Path]] = None,
    animal_ids: Optional[list[str]] = None,
    sessions: Optional[list[str]] = None,
    trials: Optional[list[str]] = None,
    skip_anatomical: bool = False,
    skip_blob: bool = False,
    overwrite_pose: bool = False,
    overwrite_blob: bool = False,
    profile_path: Path | None = None,
) -> None:
    """
    Discover trials and write a kpMS-ready H5 with tracking/anatomical + tracking/blob.

    No legacy exit/center settings or ambulation pipeline — paths, labels, and tracking only.
    """
    if skip_blob and not HAS_CV2:
        print("Note: cv2 not available; blob materialization requires opencv-python.")

    resolved_data_dirs = _resolve_data_dirs(data_dirs)
    print(f"Discovering trials in: {resolved_data_dirs or DATA_DIRS}")
    result = discover_trials(resolved_data_dirs)
    print(f"  Trials discovered: {len(result.trials)}")

    labels = load_treatment_labels(LABELS_PATH)
    apply_treatment_labels(result, labels)
    _apply_inferred_ids_from_csv(result)

    manifests = _filter_manifests(result.trials, animal_ids, sessions, trials)
    if not manifests:
        print("No trials matched filters.")
        return

    if not HAS_CV2 and not skip_blob:
        print("Warning: cv2 not available — skipping blob materialization (use --skip-blob to silence).")
        skip_blob = True

    for trial in manifests:
        if trial.video_path and trial.video_path.exists():
            n_frames = _get_video_frame_count(trial.video_path)
            if n_frames is not None:
                trial.video_n_frames = n_frames

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    blob_params = None
    if profile_path is not None:
        ft = load_fallback_tracking_from_profile(profile_path)
        blob_params = offline_blob_params_from_fallback(ft)
        print(f"Blob tracker from profile: {profile_path.resolve()}")
        print(
            f"  range [{blob_params.range_low}, {blob_params.range_high}], "
            f"min_area={blob_params.min_area}, min_circularity={blob_params.min_circularity}"
        )

    print(f"\nBuilding tracking H5: {db_path}")
    print(f"  Trials to process: {len(manifests)}")
    print(f"  Anatomical: {'off' if skip_anatomical else 'from sleap sidecar'}")
    print(f"  Blob: {'off' if skip_blob else 'offline re-track from video'}")

    def _log(msg: str) -> None:
        print(f"  {msg}")

    stats = build_tracking_h5(
        db_path,
        manifests,
        skip_anatomical=skip_anatomical,
        skip_blob=skip_blob,
        overwrite_pose=overwrite_pose,
        overwrite_blob=overwrite_blob,
        blob_params=blob_params,
        log=_log,
    )

    manifest_path = manifest_path_for_db(db_path)
    print("\nDone.")
    print(f"  Database: {db_path}")
    print(f"  Manifest: {manifest_path}")
    print(
        "  Anatomical: "
        f"written={stats.anatomical_written}, skipped={stats.anatomical_skipped}, failed={stats.anatomical_failed}"
    )
    print(
        f"  Blob: written={stats.blob_written}, skipped={stats.blob_skipped}, failed={stats.blob_failed}"
    )
    if stats.errors:
        print(f"  Errors ({len(stats.errors)}); first 5:")
        for err in stats.errors[:5]:
            print(f"    {err}")


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Legacy VAST DB: init/sync from discovery + treatment_labels; run inference, pipeline, exports.",
        epilog="Outputs: outputs/legacy/vast_results_legacy.h5, trial_manifest_legacy.csv, exports/",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to legacy H5 database (default: <repo>/outputs/legacy/vast_results_legacy.h5)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialize legacy DB and manifest from discovery + treatment_labels.csv")
    p_init.add_argument(
        "--data-dir",
        dest="data_dirs",
        action="append",
        type=Path,
        default=None,
        help="Override discovery root (repeat for multiple roots).",
    )
    p_init.set_defaults(func=lambda: cmd_init())

    # sync
    p_sync = sub.add_parser("sync", help="Sync DB and manifest; optionally --update-labels, prune missing trials")
    p_sync.add_argument(
        "--data-dir",
        dest="data_dirs",
        action="append",
        type=Path,
        default=None,
        help="Override discovery root (repeat for multiple roots).",
    )
    p_sync.add_argument("--update-labels", action="store_true", help="Add new IDs to treatment_labels.csv from discovery")
    p_sync.add_argument("--no-backup", action="store_true", help="Do not backup DB before sync")
    p_sync.add_argument("--dry-run", action="store_true", help="Only report what would be pruned")
    p_sync.add_argument(
        "--prune-unlabeled",
        action="store_true",
        help="Remove animal groups that have no row in treatment_labels.csv",
    )

    # run-inference
    p_inf = sub.add_parser("run-inference", help="Run SLEAP-NN inference on selected trials (requires sleap-nn env)")
    p_inf.add_argument("--model", "-m", type=Path, required=True, help="Path to sleap-nn model dir (best.ckpt)")
    p_inf.add_argument("--animal-id", type=str, nargs="*", default=None, help="Animal ID(s)")
    p_inf.add_argument("--session", type=str, nargs="*", default=None, help="Session(s), e.g. S01")
    p_inf.add_argument("--trial", type=str, nargs="*", default=None, help="Trial(s), e.g. T01")
    p_inf.add_argument("--output-dir", type=Path, default=None, help="Directory for .predictions.slp (default: next to video)")
    p_inf.add_argument("--batch-size", type=int, default=16)
    p_inf.add_argument("--device", type=str, default="auto")
    p_inf.add_argument("--skip-existing", action="store_true")
    p_inf.add_argument("--dry-run", action="store_true")

    # run-pipeline
    p_pl = sub.add_parser("run-pipeline", help="Run VAST pipeline (metrics, QC) on selected trials")
    p_pl.add_argument("--animal-id", type=str, nargs="*", default=None)
    p_pl.add_argument("--session", type=str, nargs="*", default=None)
    p_pl.add_argument("--trial", type=str, nargs="*", default=None)
    p_pl.add_argument("--no-qc", action="store_true", help="Skip QC image generation")
    p_pl.add_argument("--no-skip-mistrials", action="store_true", help="Process trials with missing data")
    p_pl.add_argument("--workers", "-w", type=int, default=4)

    # run-exports
    p_exp = sub.add_parser("run-exports", help="Export trial summary and mistrial CSVs to outputs/legacy/exports/")
    p_exp.add_argument("--animal-id", type=str, nargs="*", default=None)
    p_exp.add_argument("--session", type=str, nargs="*", default=None)
    p_exp.add_argument("--trial", type=str, nargs="*", default=None)
    p_exp.add_argument("--include-mistrials", action="store_true", help="Include mistrials in trial summary CSV")

    # build-kpms-h5
    p_kpms = sub.add_parser(
        "build-kpms-h5",
        help=(
            "Build kpMS-ready H5 with tracking/anatomical (SLEAP sidecar) and "
            "tracking/blob (offline video re-track); no legacy exit/center pipeline"
        ),
    )
    p_kpms.add_argument(
        "--data-dir",
        dest="data_dirs",
        action="append",
        type=Path,
        default=None,
        help="Override discovery root (repeat for multiple roots).",
    )
    p_kpms.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_KPMS_TRACKING_DB,
        help=f"Output H5 path (default: {DEFAULT_KPMS_TRACKING_DB})",
    )
    p_kpms.add_argument("--animal-id", type=str, nargs="*", default=None, help="Animal ID(s)")
    p_kpms.add_argument("--session", type=str, nargs="*", default=None, help="Session(s), e.g. S01")
    p_kpms.add_argument("--trial", type=str, nargs="*", default=None, help="Trial(s), e.g. T01")
    p_kpms.add_argument("--skip-anatomical", action="store_true", help="Do not write tracking/anatomical")
    p_kpms.add_argument("--skip-blob", action="store_true", help="Do not write tracking/blob")
    p_kpms.add_argument(
        "--overwrite-pose",
        action="store_true",
        help="Replace existing tracking/anatomical (default: keep_live policy)",
    )
    p_kpms.add_argument(
        "--overwrite-blob",
        action="store_true",
        help="Replace existing tracking/blob",
    )
    p_kpms.add_argument(
        "--profile",
        type=Path,
        default=None,
        help=(
            "Controller acquisition profile JSON; uses common.fallback_tracking "
            "for offline blob re-track (range_low/high, min_area, etc.)"
        ),
    )

    args = parser.parse_args()
    _set_legacy_paths(args.db_path if args.command != "build-kpms-h5" else None)

    if args.command == "init":
        cmd_init(data_dirs=args.data_dirs)
        return 0

    if args.command == "sync":
        cmd_sync(
            update_labels=args.update_labels,
            no_backup=args.no_backup,
            dry_run=args.dry_run,
            prune_unlabeled=args.prune_unlabeled,
            data_dirs=args.data_dirs,
        )
        return 0

    if args.command == "run-inference":
        cmd_run_inference(
            model_path=args.model,
            animal_ids=_expand_filter_arg(args.animal_id),
            sessions=_expand_filter_arg(args.session),
            trials=_expand_filter_arg(args.trial),
            output_dir=args.output_dir,
            batch_size=args.batch_size,
            device=args.device,
            skip_existing=args.skip_existing,
            dry_run=args.dry_run,
        )
        return 0

    if args.command == "run-pipeline":
        cmd_run_pipeline(
            animal_ids=_expand_filter_arg(args.animal_id),
            sessions=_expand_filter_arg(args.session),
            trials=_expand_filter_arg(args.trial),
            no_qc=args.no_qc,
            no_skip_mistrials=args.no_skip_mistrials,
            workers=args.workers,
        )
        return 0

    if args.command == "run-exports":
        cmd_run_exports(
            animal_ids=_expand_filter_arg(args.animal_id),
            sessions=_expand_filter_arg(args.session),
            trials=_expand_filter_arg(args.trial),
            include_mistrials=args.include_mistrials,
        )
        return 0

    if args.command == "build-kpms-h5":
        cmd_build_kpms_h5(
            db_path=args.db_path,
            data_dirs=args.data_dirs,
            animal_ids=_expand_filter_arg(args.animal_id),
            sessions=_expand_filter_arg(args.session),
            trials=_expand_filter_arg(args.trial),
            skip_anatomical=args.skip_anatomical,
            skip_blob=args.skip_blob,
            overwrite_pose=args.overwrite_pose,
            overwrite_blob=args.overwrite_blob,
            profile_path=args.profile,
        )
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
