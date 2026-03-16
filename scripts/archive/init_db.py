"""
Initialize the VAST output database.

This script:
1. Creates the HDF5 database with metadata structure
2. Discovers all trials from input H5 files
3. Loads treatment labels and applies to trials
4. Optionally applies inferred ID mappings for mislabeled trials
5. Creates trial group skeletons for each discovered trial
6. Enriches manifests with timestamps, frame counts, and FPS from source data
7. Writes animal labels (strain, experiment) to database
8. Saves enriched manifest CSV

After this script runs, the output database contains all settings needed by
the pipeline -- the pipeline no longer reads from input H5 files at runtime.

Usage:
    python scripts/init_db.py
"""

import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from vast_pipeline.config import DATA_DIRS, OUTPUT_H5
from vast_pipeline.io.file_discovery import (
    apply_treatment_labels,
    check_duplicates,
    discover_trials,
    load_treatment_labels,
    save_manifest_csv,
)
from vast_pipeline.io.input_h5_loader import load_trial_data, load_trial_settings
from vast_pipeline.storage.h5_db import (
    TrialKey,
    ensure_trial_group,
    init_database,
    write_animal_label,
    write_feedback_series,
    write_trial_frame_counts,
    write_trial_settings,
)

# Try to import ID inference utilities
try:
    from infer_mislabeled_ids import apply_inferred_ids, load_mappings
    HAS_INFERENCE = True
except ImportError:
    HAS_INFERENCE = False

# Try to import cv2 for video frame counts
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def get_video_frame_count(video_path: Path) -> Optional[int]:
    """Get video frame count using OpenCV. Returns None on failure."""
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
    print(f"Initializing VAST database: {OUTPUT_H5}")
    print(f"Data directories: {DATA_DIRS}")
    print()

    # Initialize database with metadata
    init_database(OUTPUT_H5)
    print("Created metadata structure")

    # Discover all trials (from all roots in DATA_DIRS)
    print("\nDiscovering trials...")
    result = discover_trials()

    print("\nDiscovery summary:")
    print(f"  Input H5 files: {len(result.input_h5_files)}")
    print(f"  Video files: {len(result.video_files)}")
    print(f"  SLEAP files: {len(result.sleap_files)}")
    print(f"  Total trials: {len(result.trials)}")
    print(f"  Matched videos: {result.n_matched_videos}")
    print(f"  Matched SLEAP: {result.n_matched_sleap}")

    # Check for duplicate trial keys
    duplicates = check_duplicates(result)
    if duplicates:
        print(f"\nWARNING: Found {len(duplicates)} duplicate trial keys!")
        for key, trials in duplicates[:10]:  # Show first 10
            print(f"  {key}:")
            for t in trials:
                print(f"    - {t.input_h5_path}")
        if len(duplicates) > 10:
            print(f"  ... and {len(duplicates) - 10} more")

    # Load and apply treatment labels
    print("\nLoading treatment labels...")
    labels = load_treatment_labels()
    apply_treatment_labels(result, labels)

    # Count trials with labels
    n_with_strain = sum(1 for t in result.trials if t.strain)
    n_with_experiment = sum(1 for t in result.trials if t.experiment)
    print(f"  Trials with strain: {n_with_strain}")
    print(f"  Trials with experiment: {n_with_experiment}")

    # Apply inferred ID mappings if available
    mappings_path = Path(__file__).parent.parent / "inputs" / "inferred_id_mappings.csv"
    if HAS_INFERENCE and mappings_path.exists():
        print("\nApplying inferred ID mappings...")
        mappings = load_mappings(mappings_path)
        n_inferred = apply_inferred_ids(result, mappings)
        print(f"  Applied {n_inferred} inferred IDs")
    elif mappings_path.exists():
        # Try inline import if module import failed
        print("\nApplying inferred ID mappings (inline)...")
        import csv
        mappings = {}
        with open(mappings_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row["original_id"], row["session"], row["trial"])
                mappings[key] = row["inferred_id"]

        n_inferred = 0
        for trial in result.trials:
            key = (trial.animal_id, trial.session, trial.trial)
            if key in mappings:
                trial.inferred_id = mappings[key]
                n_inferred += 1
        print(f"  Applied {n_inferred} inferred IDs")

    # Create trial groups, load settings, and enrich metadata
    print("\nCreating trial groups and loading source data...")
    if not HAS_CV2:
        print("  Note: cv2 not available, video frame counts will not be extracted")

    counts = {"timestamps": 0, "h5_frames": 0, "video_frames": 0, "settings_failures": 0}

    for trial in result.trials:
        key = TrialKey.from_manifest(trial)
        ensure_trial_group(
            OUTPUT_H5,
            key,
            video_path=str(trial.video_path) if trial.video_path else None,
            sleap_path=str(trial.sleap_path) if trial.sleap_path else None,
            input_h5_path=str(trial.input_h5_path),
        )

        # Load settings from input H5 and write to output database
        # Use h5_session for loading (accounts for session renumbering)
        h5_fps = None
        try:
            settings = load_trial_settings(
                trial.input_h5_path,
                trial.animal_id,
                trial.h5_session,
                trial.trial,
            )

            # Enrich manifest with timestamp
            trial.timestamp = settings.timestamp
            if settings.timestamp:
                counts["timestamps"] += 1

            # Load trial data for FPS, frame count, trial start (subtrial 0->1), and W/M
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
                pass  # H5 data read not critical

            timestamp_str = settings.timestamp.isoformat() if settings.timestamp else None
            write_trial_settings(
                OUTPUT_H5,
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

            # Write W and M to output H5 (analysis window only)
            if h5_data is not None and h5_data.n_frames > 0:
                start = trial_start_frame if trial_start_frame is not None else 0
                start = min(start, h5_data.n_frames)
                w_analysis = h5_data.w[start:]
                m_analysis = h5_data.m[start:]
                if len(w_analysis) > 0 and len(w_analysis) == len(m_analysis):
                    try:
                        write_feedback_series(OUTPUT_H5, key, w_analysis, m_analysis)
                    except Exception as e:
                        print(f"  Warning: Could not write feedback series for {key.path()}: {e}")
                else:
                    print(f"  Warning: Skipping feedback series for {key.path()} (no W/M or length mismatch)")
        except Exception as e:
            counts["settings_failures"] += 1
            print(f"  Warning: Could not load settings for {key.path()}: {e}")

        # Get video frame count
        if trial.video_path and trial.video_path.exists():
            n_frames = get_video_frame_count(trial.video_path)
            if n_frames is not None:
                trial.video_n_frames = n_frames
                counts["video_frames"] += 1

        # Persist frame counts to DB for pipeline frame_diff filtering
        if trial.h5_n_frames is not None and trial.video_n_frames is not None:
            try:
                write_trial_frame_counts(
                    OUTPUT_H5, key, trial.h5_n_frames, trial.video_n_frames
                )
            except Exception:
                pass

    print(f"Created {len(result.trials)} trial groups")
    print(f"  Timestamps: {counts['timestamps']}")
    print(f"  H5 frame counts: {counts['h5_frames']}")
    print(f"  Video frame counts: {counts['video_frames']}")
    print(f"  Settings failures: {counts['settings_failures']}")

    # Write animal labels to database
    print("\nWriting animal labels to database...")
    unique_animals = set()
    for trial in result.trials:
        animal_id = trial.effective_animal_id
        if animal_id in unique_animals:
            continue
        unique_animals.add(animal_id)

        write_animal_label(
            OUTPUT_H5,
            animal_id,
            strain=trial.strain,
            experiment=trial.experiment,
            sex=trial.sex,
            tx=trial.tx,
            researcher=trial.researcher,
            drug=trial.drug,
        )

    print(f"  Wrote labels for {len(unique_animals)} unique animals")

    # Save manifest CSV
    manifest_path = Path(__file__).parent.parent / "inputs" / "trial_manifest.csv"
    save_manifest_csv(result, manifest_path)

    print(f"\nDatabase initialized: {OUTPUT_H5}")
    print(f"Manifest saved: {manifest_path}")


if __name__ == "__main__":
    main()
