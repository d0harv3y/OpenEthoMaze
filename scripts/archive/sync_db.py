"""
Synchronize the VAST output database with discovery and treatment labels (incremental sync).

- Runs discovery (multi-dir), optionally updates treatment_labels.csv from discovery (--update-labels).
- Applies treatment labels and merges into the DB: ensures trial groups and paths, writes
  settings/feedback only for trials that do not already have them; always refreshes animal labels.
- Prunes trial groups (and animal groups with no trials) that are no longer in discovery.
- Optionally backs up the DB before changes (default on; use --no-backup to disable).
- With --dry-run, only reports what would be pruned; no backup or DB writes.

Usage:
    python scripts/sync_db.py [--db PATH] [--no-backup] [--update-labels] [--dry-run]
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from tqdm import tqdm

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from vast_pipeline.config import DATA_DIRS, OUTPUT_H5
from vast_pipeline.io.file_discovery import (
    apply_treatment_labels,
    discover_trials,
    load_manifest_csv,
    load_treatment_labels,
    save_manifest_csv,
    update_treatment_labels_from_discovery,
)
from vast_pipeline.io.input_h5_loader import load_trial_data, load_trial_settings
from vast_pipeline.storage.h5_db import (
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
)

# Optional cv2 for video frame count
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def get_video_frame_count(video_path: Path):
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


def main():
    parser = argparse.ArgumentParser(
        description="Incremental sync: update DB from discovery and labels, prune missing trials."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to output HDF5 database (default: from config OUTPUT_H5)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a backup of the DB before syncing",
    )
    parser.add_argument(
        "--update-labels",
        action="store_true",
        help="Update treatment_labels.csv from discovery (add new IDs as blank rows)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be pruned; no backup or DB writes",
    )
    args = parser.parse_args()

    db_path = args.db or OUTPUT_H5
    db_path = Path(db_path)
    project_root = Path(__file__).parent.parent
    labels_path = project_root / "inputs" / "treatment_labels.csv"
    manifest_path = project_root / "inputs" / "trial_manifest.csv"

    if args.dry_run:
        print("Dry run: no backup or DB writes; will report prune list only.")
        print()

    # Backup (default on; skip in dry-run)
    if not args.dry_run and not args.no_backup and db_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path(str(db_path) + f".backup_{timestamp}")
        shutil.copy(db_path, backup_path)
        print(f"Backed up database to {backup_path}")
        print()

    # Ensure DB exists when not dry-run (bootstrap empty DB)
    if not args.dry_run and (not db_path.exists() or db_path.stat().st_size == 0):
        init_database(db_path)
        print(f"Initialized database: {db_path}")
        print()

    # Discovery
    print("Discovering trials...")
    result = discover_trials()
    print(f"  Trials: {len(result.trials)}")
    print()

    # Optional: update treatment_labels.csv from discovery
    if args.update_labels:
        if args.dry_run:
            print("(Dry run: skipping --update-labels write to CSV)")
        else:
            update_treatment_labels_from_discovery(result, labels_path)
        print()

    # Load and apply treatment labels
    print("Loading and applying treatment labels...")
    labels = load_treatment_labels()
    apply_treatment_labels(result, labels)
    print()

    discovery_key_set = {
        (t.animal_id, t.phase, t.session, t.trial) for t in result.trials
    }

    if not args.dry_run:
        # Apply discovery to DB: ensure trial groups, write settings/feedback for new trials only
        print("Syncing trial groups and paths...")
        for trial in tqdm(result.trials, desc="Syncing trials", unit="trial"):
            key = TrialKey.from_manifest(trial)
            ensure_trial_group(
                db_path,
                key,
                video_path=str(trial.video_path) if trial.video_path else None,
                sleap_path=str(trial.sleap_path) if trial.sleap_path else None,
                input_h5_path=str(trial.input_h5_path),
            )
            if trial_has_settings(db_path, key):
                continue
            # New trial: load from input H5 and write settings + feedback (same as init_db)
            h5_fps = None
            try:
                settings = load_trial_settings(
                    trial.input_h5_path,
                    trial.animal_id,
                    trial.h5_session,
                    trial.trial,
                )
                trial.timestamp = settings.timestamp
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
                    trial_start_frame = h5_data.trial_start_frame
                except Exception:
                    pass
                timestamp_str = (
                    settings.timestamp.isoformat() if settings.timestamp else None
                )
                write_trial_settings(
                    db_path,
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
                    start = (
                        trial_start_frame
                        if trial_start_frame is not None
                        else 0
                    )
                    start = min(start, h5_data.n_frames)
                    w_analysis = h5_data.w[start:]
                    m_analysis = h5_data.m[start:]
                    if len(w_analysis) > 0 and len(w_analysis) == len(m_analysis):
                        try:
                            write_feedback_series(
                                db_path, key, w_analysis, m_analysis
                            )
                        except Exception:
                            pass
            except Exception:
                pass
            if trial.video_path and trial.video_path.exists():
                n_frames = get_video_frame_count(trial.video_path)
                if n_frames is not None:
                    trial.video_n_frames = n_frames
        print(f"  Ensured {len(result.trials)} trial groups")
        print()

        # Animal labels (always refresh from CSV)
        print("Writing animal labels...")
        unique_animals = set()
        for trial in result.trials:
            animal_id = trial.effective_animal_id
            if animal_id in unique_animals:
                continue
            unique_animals.add(animal_id)
            write_animal_label(
                db_path,
                animal_id,
                strain=trial.strain,
                experiment=trial.experiment,
                sex=trial.sex,
                tx=trial.tx,
                researcher=trial.researcher,
                drug=trial.drug,
            )
        print(f"  Wrote labels for {len(unique_animals)} unique animals")
        print()

    # Prune: trials in DB but not in discovery (and empty animal groups)
    if db_path.exists():
        db_trials = list_trials(db_path)
    else:
        db_trials = []
    to_prune = [
        t
        for t in db_trials
        if (t.animal_id, t.phase, t.session, t.trial) not in discovery_key_set
    ]
    animal_ids_with_pruned = set(t.animal_id for t in to_prune)
    # Remove animal group only if it has no trials left in discovery (all its trials were pruned).
    animals_to_remove = {
        aid
        for aid in animal_ids_with_pruned
        if not any(t.animal_id == aid for t in result.trials)
    }
    # Wait - if we prune some trials of animal A but discovery still has other trials for A, we don't delete A. If we prune all trials of animal A (A not in result.trials at all? No - result.trials has discovery trials. So animal A might have 5 trials in DB, 3 in discovery after sync. We prune 2. We should not delete A. So: animals_to_remove = animal_ids that have at least one pruned trial AND have no trial in discovery. So for each aid in animal_ids_with_pruned, if there is no result trial with animal_id == aid, then after pruning this animal will have no trials in DB, so remove the animal group.
    animals_to_remove = {
        aid
        for aid in animal_ids_with_pruned
        if not any(t.animal_id == aid for t in result.trials)
    }

    if to_prune or animals_to_remove:
        if args.dry_run:
            print("Would prune:")
            for t in to_prune:
                print(f"  Trial: {t.path()}")
            for aid in sorted(animals_to_remove):
                print(f"  Animal group (no trials left): {aid}")
            print()
        else:
            for t in to_prune:
                delete_trial_group(db_path, t)
            print(f"Pruned {len(to_prune)} trial group(s)")
            for aid in sorted(animals_to_remove):
                delete_animal_group(db_path, aid)
            if animals_to_remove:
                print(f"Removed {len(animals_to_remove)} empty animal group(s)")
            print()
    else:
        print("Nothing to prune.")
        print()

    if not args.dry_run:
        # Preserve enriched QC columns (timestamp, h5_n_frames, video_n_frames, frame_diff,
        # cohort, researcher, strain, experiment, inferred_id) from existing manifest
        def _norm(s):
            return (s or "").strip()

        if manifest_path.exists():
            existing_manifests = load_manifest_csv(manifest_path)
            existing_by_key = {
                (_norm(m.animal_id), _norm(m.session), _norm(m.trial)): m
                for m in existing_manifests
            }
            for t in result.trials:
                key = (_norm(t.animal_id), _norm(t.session), _norm(t.trial))
                if key in existing_by_key:
                    m = existing_by_key[key]
                    t.timestamp = m.timestamp
                    t.h5_n_frames = m.h5_n_frames
                    t.video_n_frames = m.video_n_frames
                    t.original_session = m.original_session
                    t.researcher = m.researcher
                    t.drug = m.drug
                    t.inferred_id = m.inferred_id
        # Backfill timestamp and video_n_frames from DB when still missing (e.g. existing
        # manifest had blanks or was overwritten by a previous sync)
        if db_path.exists():
            for t in result.trials:
                if t.timestamp is not None and t.video_n_frames is not None:
                    continue
                key = TrialKey.from_manifest(t)
                try:
                    db_ts, db_n_frames = read_trial_meta_for_manifest(db_path, key)
                    if t.timestamp is None and db_ts is not None:
                        t.timestamp = db_ts
                    if t.video_n_frames is None and db_n_frames is not None:
                        t.video_n_frames = db_n_frames
                except Exception:
                    pass
        # Persist frame counts to DB for pipeline frame_diff filtering
        for t in result.trials:
            if t.h5_n_frames is not None and t.video_n_frames is not None:
            key = TrialKey.from_manifest(t)
            try:
                write_trial_frame_counts(db_path, key, t.h5_n_frames, t.video_n_frames)
                except Exception:
                    pass
        save_manifest_csv(result, manifest_path)
        print(f"Manifest saved: {manifest_path}")
        print(f"Sync complete: {db_path}")
    else:
        print("Dry run complete (no changes written).")


if __name__ == "__main__":
    main()
