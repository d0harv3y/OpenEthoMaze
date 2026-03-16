"""
Trial validation and review script.

Validates trial data and generates a review CSV for human decision-making.

This script:
1. Discovers all trials from H5 files
2. Extracts timestamps from H5 settings
3. Identifies issues:
   - Invalid key combos (IDs 0-4, session < 1)
   - Trials missing videos
   - Orphaned videos (no H5 match)
   - Potential duplicates (similar timestamps, different keys)
4. Outputs review_issues.csv for human review
5. Updates trial_manifest.csv with timestamps

Usage:
    python scripts/validate_trials.py
    python scripts/validate_trials.py --output-dir outputs/
"""

import argparse
import csv
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from vast_pipeline.config import DATA_DIR
from vast_pipeline.io.file_discovery import (
    DiscoveryResult,
    TrialManifest,
    apply_treatment_labels,
    discover_trials,
    find_orphaned_videos,
    find_potential_duplicates,
    find_trials_missing_videos,
    is_invalid_key_combo,
    load_treatment_labels,
    save_manifest_csv,
)
from vast_pipeline.io.input_h5_loader import load_trial_data, load_trial_settings

# Try to import cv2 for video frame counts
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def get_video_frame_count(video_path: Path) -> Optional[int]:
    """
    Get video frame count using OpenCV.

    Args:
        video_path: Path to video file

    Returns:
        Frame count, or None if unable to read
    """
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


def enrich_trial_metadata(result: DiscoveryResult) -> dict[str, int]:
    """
    Load timestamps and frame counts from H5 and video files.

    Modifies trials in-place to set timestamp, h5_n_frames, and video_n_frames.

    Args:
        result: DiscoveryResult with trials

    Returns:
        Dictionary with counts: timestamps, h5_frames, video_frames, failures
    """
    counts = {
        "timestamps": 0,
        "h5_frames": 0,
        "video_frames": 0,
        "failures": 0,
    }

    for trial in result.trials:
        # Use h5_session for loading (accounts for session renumbering)
        h5_session = trial.h5_session

        # Load timestamp from settings
        try:
            settings = load_trial_settings(
                trial.input_h5_path,
                trial.animal_id,
                h5_session,
                trial.trial,
            )
            trial.timestamp = settings.timestamp
            if settings.timestamp:
                counts["timestamps"] += 1
        except Exception:
            counts["failures"] += 1

        # Load H5 frame count from data
        try:
            data = load_trial_data(
                trial.input_h5_path,
                trial.animal_id,
                h5_session,
                trial.trial,
            )
            trial.h5_n_frames = data.n_frames
            if data.n_frames > 0:
                counts["h5_frames"] += 1
        except Exception:
            pass  # H5 frame count not critical

        # Load video frame count
        if trial.video_path and trial.video_path.exists():
            n_frames = get_video_frame_count(trial.video_path)
            if n_frames is not None:
                trial.video_n_frames = n_frames
                counts["video_frames"] += 1

    return counts


def find_candidate_matches(
    invalid_trial: TrialManifest,
    valid_trials: list[TrialManifest],
    max_delta_minutes: int = 30,
) -> list[tuple[TrialManifest, float, float]]:
    """
    Find potential matches for an invalid trial by timestamp.

    Args:
        invalid_trial: Trial with invalid key combo
        valid_trials: List of valid trials to match against
        max_delta_minutes: Maximum time difference for a match

    Returns:
        List of (candidate_trial, time_delta_seconds, confidence) tuples,
        sorted by confidence descending
    """
    if invalid_trial.timestamp is None:
        return []

    matches = []
    max_delta = timedelta(minutes=max_delta_minutes)

    for candidate in valid_trials:
        if candidate.timestamp is None:
            continue

        # Must have same session and trial number
        if candidate.session != invalid_trial.session:
            continue
        if candidate.trial != invalid_trial.trial:
            continue

        delta = abs(candidate.timestamp - invalid_trial.timestamp)
        if delta <= max_delta:
            # Confidence: 1.0 = exact match, 0.0 = at threshold
            confidence = 1.0 - (delta.total_seconds() / max_delta.total_seconds())
            confidence = max(0.0, min(1.0, confidence))
            matches.append((candidate, delta.total_seconds(), confidence))

    # Sort by confidence descending
    matches.sort(key=lambda x: -x[2])
    return matches


def generate_review_csv(
    result: DiscoveryResult,
    output_path: Path,
    max_delta_minutes: int = 30,
) -> dict[str, int]:
    """
    Generate review CSV with all identified issues.

    Args:
        result: DiscoveryResult with timestamps populated
        output_path: Path for output CSV
        max_delta_minutes: Max time delta for candidate matching

    Returns:
        Dictionary with issue counts by type
    """
    issues: list[dict] = []
    counts: dict[str, int] = defaultdict(int)

    # Separate valid and invalid trials
    valid_trials = []
    invalid_trials = []

    for trial in result.trials:
        is_invalid, reason = is_invalid_key_combo(trial)
        if is_invalid:
            invalid_trials.append((trial, reason))
        else:
            valid_trials.append(trial)

    # 1. Invalid key combos with candidate matches
    for trial, reason in invalid_trials:
        issue_type = reason
        counts[issue_type] += 1

        candidates = find_candidate_matches(trial, valid_trials, max_delta_minutes)
        best_candidate = candidates[0] if candidates else None

        issues.append({
            "issue_type": issue_type,
            "animal_id": trial.animal_id,
            "session": trial.session,
            "trial": trial.trial,
            "phase": trial.phase,
            "timestamp": trial.timestamp.isoformat() if trial.timestamp else "",
            "h5_n_frames": str(trial.h5_n_frames) if trial.h5_n_frames is not None else "",
            "video_n_frames": str(trial.video_n_frames) if trial.video_n_frames is not None else "",
            "frame_diff": "",
            "input_h5_path": str(trial.input_h5_path),
            "video_path": str(trial.video_path) if trial.video_path else "",
            "candidate_animal_id": best_candidate[0].animal_id if best_candidate else "",
            "candidate_timestamp": (
                best_candidate[0].timestamp.isoformat()
                if best_candidate and best_candidate[0].timestamp
                else ""
            ),
            "time_delta_sec": f"{best_candidate[1]:.1f}" if best_candidate else "",
            "confidence": f"{best_candidate[2]:.3f}" if best_candidate else "",
            "resolution": "",
        })

    # 2. Valid trials missing videos
    missing_video = find_trials_missing_videos(result)
    for trial in missing_video:
        counts["missing_video"] += 1
        issues.append({
            "issue_type": "missing_video",
            "animal_id": trial.animal_id,
            "session": trial.session,
            "trial": trial.trial,
            "phase": trial.phase,
            "timestamp": trial.timestamp.isoformat() if trial.timestamp else "",
            "h5_n_frames": str(trial.h5_n_frames) if trial.h5_n_frames is not None else "",
            "video_n_frames": "",
            "frame_diff": "",
            "input_h5_path": str(trial.input_h5_path),
            "video_path": "",
            "candidate_animal_id": "",
            "candidate_timestamp": "",
            "time_delta_sec": "",
            "confidence": "",
            "resolution": "",
        })

    # 3. Orphaned videos
    orphaned = find_orphaned_videos(result)
    for video_path, (animal_id, session, trial_id) in orphaned:
        counts["orphaned_video"] += 1
        # Try to get video frame count for orphaned videos
        vid_frames = get_video_frame_count(video_path) if video_path else None
        issues.append({
            "issue_type": "orphaned_video",
            "animal_id": animal_id,
            "session": session,
            "trial": trial_id,
            "phase": "",
            "timestamp": "",
            "h5_n_frames": "",
            "video_n_frames": str(vid_frames) if vid_frames is not None else "",
            "frame_diff": "",
            "input_h5_path": "",
            "video_path": str(video_path),
            "candidate_animal_id": "",
            "candidate_timestamp": "",
            "time_delta_sec": "",
            "confidence": "",
            "resolution": "",
        })

    # 4. Potential duplicates
    duplicates = find_potential_duplicates(result.trials, threshold_minutes=2)
    for t1, t2, delta_sec in duplicates:
        counts["potential_duplicate"] += 1
        issues.append({
            "issue_type": "potential_duplicate",
            "animal_id": t1.animal_id,
            "session": t1.session,
            "trial": t1.trial,
            "phase": t1.phase,
            "timestamp": t1.timestamp.isoformat() if t1.timestamp else "",
            "h5_n_frames": "",
            "video_n_frames": "",
            "frame_diff": "",
            "input_h5_path": str(t1.input_h5_path),
            "video_path": str(t1.video_path) if t1.video_path else "",
            "candidate_animal_id": t2.animal_id,
            "candidate_timestamp": t2.timestamp.isoformat() if t2.timestamp else "",
            "time_delta_sec": f"{delta_sec:.1f}",
            "confidence": "",
            "resolution": "",
        })

    # 5. Frame count mismatch (H5 vs video)
    # Expected: video has h5_n_frames - 1 (off-by-one is normal).
    # Flag anything where abs(diff) > 1.
    for trial in result.trials:
        if trial.h5_n_frames is None or trial.video_n_frames is None:
            continue

        diff = trial.video_n_frames - trial.h5_n_frames  # positive = video has more

        # Off-by-one is expected (H5 counts rows, video may differ by 1)
        if abs(diff) > 1:
            counts["frame_mismatch"] += 1
            issues.append({
                "issue_type": "frame_mismatch",
                "animal_id": trial.animal_id,
                "session": trial.session,
                "trial": trial.trial,
                "phase": trial.phase,
                "timestamp": trial.timestamp.isoformat() if trial.timestamp else "",
                "h5_n_frames": str(trial.h5_n_frames),
                "video_n_frames": str(trial.video_n_frames),
                "frame_diff": str(diff),
                "input_h5_path": str(trial.input_h5_path),
                "video_path": str(trial.video_path) if trial.video_path else "",
                "candidate_animal_id": "",
                "candidate_timestamp": "",
                "time_delta_sec": "",
                "confidence": "",
                "resolution": "",
            })

    # Write CSV
    fieldnames = [
        "issue_type", "animal_id", "session", "trial", "phase", "timestamp",
        "h5_n_frames", "video_n_frames", "frame_diff",
        "input_h5_path", "video_path",
        "candidate_animal_id", "candidate_timestamp", "time_delta_sec", "confidence",
        "resolution",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(issues)

    print(f"Saved {len(issues)} issues to {output_path}")
    return dict(counts)


def main():
    parser = argparse.ArgumentParser(
        description="Validate trial data and generate review CSV"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(Path(__file__).parent.parent / "inputs"),
        help="Output directory for CSV files",
    )
    parser.add_argument(
        "--max-delta-minutes",
        type=int,
        default=30,
        help="Maximum time difference (minutes) for matching candidates",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Discover trials
    print(f"Discovering trials from {DATA_DIR}...")
    result = discover_trials(DATA_DIR)

    # Step 2: Load treatment labels
    print("\nLoading treatment labels...")
    labels = load_treatment_labels()
    apply_treatment_labels(result, labels)

    # Step 3: Enrich with timestamps and frame counts
    print(f"\nExtracting metadata from {len(result.trials)} trials...")
    if not HAS_CV2:
        print("  Note: cv2 not available, video frame counts will not be extracted")
    counts = enrich_trial_metadata(result)
    print(f"  Timestamps: {counts['timestamps']}")
    print(f"  H5 frame counts: {counts['h5_frames']}")
    print(f"  Video frame counts: {counts['video_frames']}")
    print(f"  Failures: {counts['failures']}")

    # Step 4: Generate review CSV
    print("\nAnalyzing issues...")
    review_path = output_dir / "review_issues.csv"
    counts = generate_review_csv(result, review_path, args.max_delta_minutes)

    print("\nIssue summary:")
    for issue_type, count in sorted(counts.items()):
        print(f"  {issue_type}: {count}")

    total_issues = sum(counts.values())
    print(f"\nTotal issues: {total_issues}")

    # Step 5: Save updated manifest with timestamps
    manifest_path = output_dir / "trial_manifest.csv"
    save_manifest_csv(result, manifest_path)

    print("\nDone! Review the issues in:")
    print(f"  {review_path}")


if __name__ == "__main__":
    main()
