"""Option D producer: bout AR-HMM tokens → S0 BehaviorLabeling artifact."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from maze.kpms.apply_summary import preprocess_config_from_apply_summary
from maze.kpms.frame_alignment import kpms_aligned_coordinates_and_indices, kpms_recording_key
from maze.kpms.preprocess import KpmsPreprocessConfig
from maze.pipeline.io.file_discovery import TrialManifest, load_manifest_csv

from maze.kpms.behavior_ethogram.anchor_buckets import bout_token_rows_from_table, token_anchor_buckets_from_bout_rows
from maze.kpms.behavior_ethogram.bout_table_io import read_bout_table_csv
from maze.kpms.behavior_ethogram.labeling import UNLABELED, BehaviorLabeling, TrialFrameLabels, hash_file, write_behavior_labeling
from maze.kpms.behavior_ethogram.locomotion import DEFAULT_LOCOMOTION_RULES, load_locomotion_rules_yaml
from maze.kpms.behavior_ethogram.paths import locomotion_rules_yaml, producer_dir, stage_iii_dir


def trial_frame_labels_from_bout_rows(
    trial_key: str,
    source_frame_index: np.ndarray,
    bout_rows: Sequence[Mapping[str, str]],
) -> TrialFrameLabels:
    """Expand bout-level ``behavior_token`` onto kpMS-aligned source frames."""
    sfi = np.asarray(source_frame_index, dtype=np.int64).ravel()
    n = len(sfi)
    behavior_id = np.full(n, UNLABELED, dtype=np.int32)

    ordered = sorted(bout_rows, key=lambda r: int(r["bout_index"]))
    for row in ordered:
        token_raw = str(row.get("behavior_token", "")).strip()
        if not token_raw:
            continue
        token = int(token_raw)
        lo = int(row["row_start"])
        hi = int(row["row_end_exclusive"])
        lo = max(0, min(lo, n))
        hi = max(lo, min(hi, n))
        behavior_id[lo:hi] = token

    return TrialFrameLabels(
        trial_key=trial_key,
        source_frame_index=sfi,
        behavior_id=behavior_id,
    )


def _manifest_by_recording_key(manifests: Sequence[TrialManifest]) -> dict[str, TrialManifest]:
    return {kpms_recording_key(m): m for m in manifests}


def export_option_d_labeling(
    *,
    kpms_root: Path | str,
    seed: str,
    tokens_csv: Path | str,
    manifest_path: Path | str,
    tracking_h5: Path | str,
    fit_id: str | None = None,
    fps: float = 30.0,
    locomotion_rules_path: Path | str | None = None,
    artifact_dir: Path | str | None = None,
) -> BehaviorLabeling:
    """Write ``producers/bout_arhmm/<fit_id>/`` from decoded bout token CSV."""
    kpms_root = Path(kpms_root)
    tokens_csv = Path(tokens_csv)
    fit_id = fit_id or f"seed_{seed}"
    artifact_dir = Path(artifact_dir) if artifact_dir is not None else producer_dir(kpms_root, "bout_arhmm", fit_id)

    table = read_bout_table_csv(tokens_csv)
    table = [r for r in table if str(r.get("seed", "")) == str(seed)]
    if not table:
        raise ValueError(f"no bout token rows for seed {seed} in {tokens_csv}")

    by_trial: dict[str, list[dict[str, str]]] = {}
    for row in table:
        by_trial.setdefault(str(row["trial_key"]), []).append(row)

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

    trials: list[TrialFrameLabels] = []
    token_ids: set[int] = set()
    for trial_key, bout_rows in sorted(by_trial.items()):
        manifest = manifests.get(trial_key)
        if manifest is None:
            continue
        aligned = kpms_aligned_coordinates_and_indices(manifest, pre_cfg)
        if aligned is None:
            continue
        _rk, _coord, src_idx = aligned
        trial = trial_frame_labels_from_bout_rows(trial_key, src_idx, bout_rows)
        trials.append(trial)
        labeled = trial.behavior_id[trial.behavior_id != UNLABELED]
        token_ids.update(int(x) for x in labeled)

    if not trials:
        raise ValueError("no trials exported — check manifest / tracking_h5 alignment")

    token_rows = bout_token_rows_from_table(table, seed=seed)
    rules_doc: dict[str, object] = dict(DEFAULT_LOCOMOTION_RULES)
    if locomotion_rules_path is not None:
        rules_doc = load_locomotion_rules_yaml(locomotion_rules_path)
    else:
        stage_rules = locomotion_rules_yaml(stage_iii_dir(kpms_root, seed=seed))
        if stage_rules.is_file():
            rules_doc = load_locomotion_rules_yaml(stage_rules)
    id_buckets = token_anchor_buckets_from_bout_rows(token_rows, rules_doc=rules_doc)

    behavior_names = {tid: f"token_{tid}" for tid in sorted(token_ids)}
    labeling = BehaviorLabeling(
        producer="bout_arhmm",
        fit_id=fit_id,
        fps=float(fps),
        trials=tuple(trials),
        behavior_names=behavior_names,
        behavior_anchor_buckets=id_buckets,
        params={"seed": seed},
        input_hashes={
            "bout_tokens_csv": hash_file(tokens_csv),
            "results_apply.h5": hash_file(results_h5),
        },
    )
    write_behavior_labeling(artifact_dir, labeling)
    return labeling
