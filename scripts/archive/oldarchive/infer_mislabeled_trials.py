"""
DEPRECATED: Use validate_trials.py instead.

This script has been superseded by validate_trials.py which provides:
- Invalid key combo detection (IDs 0-4, session < 1)
- Missing video detection
- Orphaned video detection
- Potential duplicate detection
- Comprehensive review CSV output

Usage:
    python scripts/validate_trials.py

Legacy usage (still works but deprecated):
    python scripts/infer_mislabeled_trials.py [--output mappings.csv]
"""

import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from vast_pipeline.config import DATA_DIR
from vast_pipeline.io.file_discovery import (
    DiscoveryResult,
    apply_treatment_labels,
    discover_trials,
    load_treatment_labels,
)
from vast_pipeline.io.input_h5_loader import load_trial_settings


@dataclass
class TrialTimestamp:
    """Trial with its timestamp for matching."""

    animal_id: str
    session: str
    trial: str
    input_h5_path: Path
    timestamp: Optional[datetime]
    experiment: Optional[str]  # VASTcontKL, VAST_NP, LAST_NP, etc.


def extract_timestamps(result: DiscoveryResult) -> list[TrialTimestamp]:
    """
    Extract timestamps from all trials.

    Returns:
        List of TrialTimestamp objects with timestamp data
    """
    timestamps = []

    for t in result.trials:
        ts = None
        try:
            settings = load_trial_settings(
                t.input_h5_path,
                t.animal_id,
                t.session,
                t.trial
            )
            ts = settings.timestamp
        except Exception as e:
            print(f"  Warning: Could not load settings for {t.trial_key}: {e}")

        timestamps.append(TrialTimestamp(
            animal_id=t.animal_id,
            session=t.session,
            trial=t.trial,
            input_h5_path=t.input_h5_path,
            timestamp=ts,
            experiment=t.experiment,
        ))

    return timestamps


def find_matches(
    mislabeled: list[TrialTimestamp],
    reference: list[TrialTimestamp],
    max_time_delta: timedelta = timedelta(minutes=30),
) -> dict[tuple[str, str, str], tuple[str, float]]:
    """
    Match mislabeled trials to reference trials by timestamp proximity.

    Matches are done within the same experiment type and session.

    Args:
        mislabeled: Trials with IDs 0-4 to match
        reference: Properly-labeled trials to match against
        max_time_delta: Maximum time difference for a valid match

    Returns:
        Dictionary mapping (animal_id, session, trial) -> (inferred_id, confidence_score)
        where confidence_score is 0-1 (1 = exact match, 0 = no match found)
    """
    mappings = {}

    # Group reference trials by (experiment, session) for faster lookup
    ref_by_exp_session: dict[tuple[str, str], list[TrialTimestamp]] = defaultdict(list)
    for ref in reference:
        key = (ref.experiment or "unknown", ref.session)
        ref_by_exp_session[key].append(ref)

    for mis in mislabeled:
        if mis.timestamp is None:
            print(f"  No timestamp for mislabeled trial {mis.animal_id}/{mis.session}/{mis.trial}")
            continue

        if mis.experiment is None:
            print(f"  No experiment type for mislabeled trial {mis.animal_id}/{mis.session}/{mis.trial}")
            continue

        # Find best match in the same experiment and session
        best_match = None
        best_delta = max_time_delta

        lookup_key = (mis.experiment, mis.session)
        for ref in ref_by_exp_session.get(lookup_key, []):
            if ref.timestamp is None:
                continue

            # Also check if trial numbers match (different animals same session/trial)
            if ref.trial != mis.trial:
                continue

            delta = abs(ref.timestamp - mis.timestamp)

            if delta < best_delta:
                best_delta = delta
                best_match = ref

        if best_match is not None:
            # Calculate confidence (1.0 = exact match, 0.0 = at threshold)
            confidence = 1.0 - (best_delta.total_seconds() / max_time_delta.total_seconds())
            confidence = max(0.0, min(1.0, confidence))

            key = (mis.animal_id, mis.session, mis.trial)
            mappings[key] = (best_match.animal_id, confidence)

            print(f"  Matched {mis.animal_id}/{mis.session}/{mis.trial} -> {best_match.animal_id} "
                  f"(exp={mis.experiment}, delta={best_delta}, confidence={confidence:.2f})")
        else:
            print(f"  No match found for {mis.animal_id}/{mis.session}/{mis.trial} (exp={mis.experiment})")

    return mappings


def save_mappings(
    mappings: dict[tuple[str, str, str], tuple[str, float]],
    output_path: Path,
) -> None:
    """Save inferred ID mappings to CSV."""
    import csv

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["original_id", "session", "trial", "inferred_id", "confidence"])

        for (animal_id, session, trial), (inferred_id, confidence) in sorted(mappings.items()):
            writer.writerow([animal_id, session, trial, inferred_id, f"{confidence:.3f}"])

    print(f"Saved {len(mappings)} mappings to {output_path}")


def load_mappings(mappings_path: Path) -> dict[tuple[str, str, str], str]:
    """
    Load ID mappings from CSV file.

    Returns:
        Dictionary mapping (original_id, session, trial) -> inferred_id
    """
    import csv

    mappings = {}

    if not mappings_path.exists():
        return mappings

    with open(mappings_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["original_id"], row["session"], row["trial"])
            mappings[key] = row["inferred_id"]

    return mappings


def apply_inferred_ids(result: DiscoveryResult, mappings: dict[tuple[str, str, str], str]) -> int:
    """
    Apply inferred IDs to trials in discovery result.

    Args:
        result: DiscoveryResult with trials
        mappings: Dictionary from load_mappings()

    Returns:
        Number of trials updated
    """
    count = 0

    for trial in result.trials:
        key = (trial.animal_id, trial.session, trial.trial)
        if key in mappings:
            trial.inferred_id = mappings[key]
            count += 1

    return count


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Infer correct animal IDs for mislabeled trials")
    parser.add_argument(
        "--output",
        type=str,
        default=str(Path(__file__).parent.parent / "inputs" / "inferred_id_mappings.csv"),
        help="Output path for mappings CSV",
    )
    parser.add_argument(
        "--max-delta-minutes",
        type=int,
        default=30,
        help="Maximum time difference (minutes) for valid match",
    )
    args = parser.parse_args()

    print(f"Discovering trials from {DATA_DIR}...")
    result = discover_trials(DATA_DIR)

    # Load and apply treatment labels to get experiment types
    print("\nLoading treatment labels...")
    labels = load_treatment_labels()
    apply_treatment_labels(result, labels)

    print(f"\nExtracting timestamps from {len(result.trials)} trials...")
    timestamps = extract_timestamps(result)

    # Separate mislabeled (0-4) and reference (>=500) trials
    mislabeled = [
        t for t in timestamps
        if t.animal_id in ("0", "1", "2", "3", "4")
    ]

    reference = [
        t for t in timestamps
        if t.animal_id.isdigit() and int(t.animal_id) >= 500
    ]

    # Group by experiment for reporting
    exp_counts_mis = defaultdict(int)
    exp_counts_ref = defaultdict(int)
    for t in mislabeled:
        exp_counts_mis[t.experiment or "unknown"] += 1
    for t in reference:
        exp_counts_ref[t.experiment or "unknown"] += 1

    print(f"\nMislabeled trials (IDs 0-4): {len(mislabeled)}")
    for exp, count in sorted(exp_counts_mis.items()):
        print(f"  {exp}: {count}")

    print(f"\nReference trials (IDs >= 500): {len(reference)}")
    for exp, count in sorted(exp_counts_ref.items()):
        print(f"  {exp}: {count}")

    if not mislabeled:
        print("\nNo mislabeled trials found. Nothing to do.")
        return

    if not reference:
        print("\nNo reference trials found. Cannot infer IDs.")
        return

    print("\nMatching by timestamp within experiment...")
    max_delta = timedelta(minutes=args.max_delta_minutes)
    mappings = find_matches(mislabeled, reference, max_delta)

    print(f"\nMatched {len(mappings)} / {len(mislabeled)} mislabeled trials")

    # Save mappings
    output_path = Path(args.output)
    save_mappings(mappings, output_path)

    # Report unmatched
    unmatched = len(mislabeled) - len(mappings)
    if unmatched > 0:
        print(f"\nWarning: {unmatched} mislabeled trials could not be matched.")
        print("These trials may need manual review.")


if __name__ == "__main__":
    main()
