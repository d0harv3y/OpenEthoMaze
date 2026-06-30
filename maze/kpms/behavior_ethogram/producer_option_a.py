"""Option A producer: syllable-sequence grammar → S0 BehaviorLabeling artifact."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import h5py
import numpy as np

from maze.kpms.apply_summary import preprocess_config_from_apply_summary
from maze.kpms.frame_alignment import kpms_aligned_coordinates_and_indices, kpms_recording_key
from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.io.file_discovery import TrialManifest, load_manifest_csv

from .bout_scalars import syllable_runs
from .grammar_mine import bout_syllable_ids
from .grammar_rules import (
    GrammarRules,
    behavior_name_to_id_map,
    label_bouts_with_grammar,
    read_grammar_rules_json,
)
from .labeling import UNLABELED, BehaviorLabeling, TrialFrameLabels, hash_file, write_behavior_labeling
from .paths import producer_dir


@dataclass(frozen=True)
class SyllableBoutSpan:
    syllable_id: int
    bout_index: int
    row_start: int
    row_end_exclusive: int


def syllable_bout_spans(z: np.ndarray) -> list[SyllableBoutSpan]:
    return [
        SyllableBoutSpan(int(sid), idx, int(lo), int(hi))
        for idx, (sid, lo, hi) in enumerate(syllable_runs(z))
    ]


def trial_frame_labels_from_grammar(
    trial_key: str,
    source_frame_index: np.ndarray,
    bouts: Sequence[SyllableBoutSpan],
    bout_behavior_names: Sequence[str | None],
    name_to_id: Mapping[str, int],
) -> TrialFrameLabels:
    sfi = np.asarray(source_frame_index, dtype=np.int64).ravel()
    n = len(sfi)
    behavior_id = np.full(n, UNLABELED, dtype=np.int32)
    for bout, name in zip(bouts, bout_behavior_names, strict=True):
        if name is None:
            continue
        bid = name_to_id.get(str(name))
        if bid is None:
            continue
        lo = max(0, min(int(bout.row_start), n))
        hi = max(lo, min(int(bout.row_end_exclusive), n))
        behavior_id[lo:hi] = int(bid)
    return TrialFrameLabels(trial_key=trial_key, source_frame_index=sfi, behavior_id=behavior_id)


def _load_syllables(results_h5: Path, recording_key: str) -> np.ndarray | None:
    with h5py.File(results_h5, "r") as h5:
        if recording_key not in h5:
            return None
        rec = h5[recording_key]
        if "syllable" not in rec:
            return None
        return np.asarray(rec["syllable"], dtype=np.int64)


def _manifest_by_recording_key(manifests: Sequence[TrialManifest]) -> dict[str, TrialManifest]:
    return {kpms_recording_key(m): m for m in manifests}


def export_option_a_labeling(
    *,
    kpms_root: Path | str,
    seed: str,
    rules_json: Path | str,
    manifest_path: Path | str,
    tracking_h5: Path | str,
    fit_id: str | None = None,
    fps: float = 30.0,
    artifact_dir: Path | str | None = None,
    grammar: GrammarRules | None = None,
) -> BehaviorLabeling:
    """Write ``producers/syllable_grammar/<fit_id>/`` from curated grammar rules."""
    kpms_root = Path(kpms_root)
    rules_json = Path(rules_json)
    fit_id = fit_id or f"seed_{seed}"
    artifact_dir = (
        Path(artifact_dir) if artifact_dir is not None else producer_dir(kpms_root, "syllable_grammar", fit_id)
    )
    grammar = grammar or read_grammar_rules_json(rules_json)

    manifests = _manifest_by_recording_key(load_manifest_csv(Path(manifest_path)))
    results_h5 = kpms_root / "anatomical" / f"seed_{seed}" / "results_apply.h5"
    pre_cfg = preprocess_config_from_apply_summary(results_h5) or KpmsPreprocessConfig()
    pre_cfg = KpmsPreprocessConfig(
        min_fragment_frames=pre_cfg.min_fragment_frames,
        jump_filter_cm=pre_cfg.jump_filter_cm,
        jump_filter_lookahead_frames=pre_cfg.jump_filter_lookahead_frames,
        px_per_cm=pre_cfg.px_per_cm,
        retain_all_frames=pre_cfg.retain_all_frames,
        db_path=Path(tracking_h5),
        pose_stream=pre_cfg.pose_stream,
    )

    name_to_id = behavior_name_to_id_map(grammar.behavior_names())
    trials: list[TrialFrameLabels] = []
    for trial_key, manifest in sorted(manifests.items()):
        z = _load_syllables(results_h5, trial_key)
        if z is None or len(z) == 0:
            continue
        aligned = kpms_aligned_coordinates_and_indices(manifest, pre_cfg)
        if aligned is None:
            continue
        _rk, _coord, src_idx = aligned
        if len(src_idx) != len(z):
            continue
        bouts = syllable_bout_spans(z)
        bout_ids = bout_syllable_ids(z)
        bout_names = label_bouts_with_grammar(bout_ids, grammar.rules)
        trial = trial_frame_labels_from_grammar(
            trial_key, src_idx, bouts, bout_names, name_to_id
        )
        if np.any(trial.behavior_id != UNLABELED):
            trials.append(trial)

    if not trials:
        raise ValueError("no trials labeled — check grammar rules / manifest alignment")

    behavior_names = {bid: name for name, bid in name_to_id.items()}
    labeling = BehaviorLabeling(
        producer="syllable_grammar",
        fit_id=fit_id,
        fps=float(fps),
        trials=tuple(trials),
        behavior_names=behavior_names,
        params={"seed": seed, "n_rules": len(grammar.rules)},
        input_hashes={
            "grammar_rules.json": hash_file(rules_json),
            "results_apply.h5": hash_file(results_h5),
        },
    )
    write_behavior_labeling(artifact_dir, labeling)
    return labeling
