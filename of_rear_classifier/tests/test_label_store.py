from __future__ import annotations

from pathlib import Path

import pandas as pd

from of_rear_classifier.label_store import (
    add_manual_interval,
    bout_label_map,
    default_labels_path,
    labels_to_sturman_intervals,
    load_labels,
    migrate_bout_labels_into_store,
    save_labels,
    upsert_syllable_label,
)
from of_rear_classifier.syllable_bouts import save_bout_table


def test_upsert_and_manual_export(tmp_path: Path):
    labels = load_labels(None, scorer="alice")
    labels = upsert_syllable_label(
        labels,
        scorer="alice",
        bout_index=3,
        syllable_id=7,
        t0_frame=10,
        t1_frame=20,
        label="Supported",
    )
    labels = add_manual_interval(
        labels, scorer="alice", t0_frame=18, t1_frame=40, label="Supported"
    )
    # overwrite same bout
    labels = upsert_syllable_label(
        labels,
        scorer="alice",
        bout_index=3,
        syllable_id=7,
        t0_frame=10,
        t1_frame=20,
        label="Unsupported",
    )
    assert bout_label_map(labels)[3] == "Unsupported"
    assert (labels["source"] == "manual").sum() == 1

    path = tmp_path / "labels" / "alice.csv"
    save_labels(labels, path)
    again = load_labels(path, scorer="alice")
    assert len(again) == 2

    stur = labels_to_sturman_intervals(again, fps=30.0, video_id="Test 42", scorer="alice")
    assert set(stur["Experimenter"]) == {"alice"}
    assert len(stur) == 2
    assert "Supported" in set(stur["type"]) and "Unsupported" in set(stur["type"])


def test_default_path_and_migrate(tmp_path: Path):
    bouts = tmp_path / "model" / "syllable_bouts.csv"
    bouts.parent.mkdir(parents=True)
    save_bout_table(
        pd.DataFrame(
            {
                "bout_index": [0, 1],
                "syllable_id": [1, 2],
                "t0_frame": [0, 10],
                "t1_frame": [9, 19],
                "n_frames": [10, 10],
                "label": ["Grooming", ""],
            }
        ),
        bouts,
    )
    assert default_labels_path(bouts, "Bob Smith") == bouts.parent / "labels" / "Bob_Smith.csv"
    labels = migrate_bout_labels_into_store(bouts, scorer="Bob_Smith")
    assert bout_label_map(labels)[0] == "Grooming"
    assert 1 not in bout_label_map(labels)
