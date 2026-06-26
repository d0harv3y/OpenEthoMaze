"""Phase I behavioral ethogram pure logic (scratch, no GPU/H5)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

_SCRATCH = Path(__file__).resolve().parents[1] / "scratch" / "kpms_ensemble_compare"
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from behavior_ethogram_phase_i import (  # noqa: E402
    CONTRAST_SIDECAR_FIELDS,
    DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS,
    DEFAULT_LOW_CONTRAST_MPS,
    StreamPrototypeScalars,
    bout_speed_iqr,
    build_contrast_sidecar_from_dirs,
    build_contrast_sidecar_rows,
    build_speed_rank_table,
    contrast_sidecar_path,
    default_phase_i_out_dir,
    extend_features_tmax,
    frac_still,
    fused_validates_ab,
    hdbscan_labels_path,
    load_hdbscan_label_table,
    mean_abs_dheading,
    parse_stream_jobs,
    prototype_ambiguous,
    prototype_scalars_from_bouts,
    resolve_available_seeds,
    write_contrast_sidecar_csv,
)


def test_extend_features_tmax_pads_with_channel_means() -> None:
    t_s, t_from, t_to = 4, 4, 6
    speed = np.array([0.0, 1.0, 2.0, 3.0])
    cos_h = np.zeros(4)
    sin_h = np.ones(4)
    feat = np.concatenate([speed, cos_h, sin_h])
    out = extend_features_tmax(feat, t_s=t_s, t_max_from=t_from, t_max_to=t_to)
    assert out.shape == (3 * t_to,)
    assert np.allclose(out[0:t_s], speed)
    assert np.allclose(out[t_s:t_to], 1.5)


def test_bout_speed_iqr_and_ambiguous_flag() -> None:
    coherent = [0.10, 0.11, 0.10, 0.12]
    bimodal = [0.02, 0.03, 0.25, 0.28]
    coherent_iqr = bout_speed_iqr(coherent)
    bimodal_iqr = bout_speed_iqr(bimodal)
    assert coherent_iqr < bimodal_iqr
    assert not prototype_ambiguous(coherent_iqr, threshold_mps=0.05)
    assert prototype_ambiguous(bimodal_iqr, threshold_mps=0.05)


def test_prototype_scalars_from_synthetic_bouts() -> None:
    is_moving = np.array([0, 0, 0, 1, 1, 0, 0], dtype=bool)
    heading = np.array([0.0, 0.2, 0.5, 0.9, 1.1, 1.0, 0.8])
    scalars = prototype_scalars_from_bouts(
        is_moving_frames=is_moving,
        heading_frames=heading,
        bout_mean_speeds=[0.05, 0.06, 0.04],
        ambiguous_threshold_mps=0.02,
    )
    assert scalars.frac_still == pytest.approx(frac_still(is_moving))
    assert scalars.mean_abs_dheading == pytest.approx(mean_abs_dheading(heading))
    assert scalars.bout_speed_iqr == pytest.approx(bout_speed_iqr([0.05, 0.06, 0.04]))
    assert scalars.ambiguous is False


def test_build_speed_rank_table_orders_by_mean_speed() -> None:
    @dataclass
    class _Stat:
        mean_speed: float

    stats = {
        ("042", 3): _Stat(0.30),
        ("042", 1): _Stat(0.05),
        ("042", 2): _Stat(0.15),
    }
    rank = build_speed_rank_table(stats)
    assert rank[("042", 1)] == 0
    assert rank[("042", 2)] == 1
    assert rank[("042", 3)] == 2


def test_parse_stream_jobs_and_resolve_available_seeds(tmp_path: Path) -> None:
    root = tmp_path / "kpms"
    apply_dir = root / "anatomical" / "seed_042"
    apply_dir.mkdir(parents=True)
    (apply_dir / "results_apply.h5").write_bytes(b"\x00")

    jobs = parse_stream_jobs(["anatomical/seed_042"], kpms_root=root)
    assert jobs == [("anatomical", ("042",), ("042",))]

    missing = resolve_available_seeds("anatomical", ("042", "999"), root)
    assert missing == ("042",)


def test_default_phase_i_out_dir() -> None:
    root = Path("/data/test2")
    assert default_phase_i_out_dir(root) == Path("/data/test2/behavior_ethogram/phase_i")


def test_default_ambiguous_threshold_is_conservative() -> None:
    assert DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS > 0.0
    borderline = bout_speed_iqr([0.10, 0.10, 0.10, 0.22])
    assert prototype_ambiguous(borderline) == (borderline > DEFAULT_AMBIGUOUS_BOUT_SPEED_IQR_MPS)


def test_fused_validates_ab_groom_and_freeze_patterns() -> None:
    # Groom-like: anatomical faster than blob; fused between them.
    assert fused_validates_ab(0.12, 0.02, 0.08, low_contrast_mps=DEFAULT_LOW_CONTRAST_MPS)
    # Freeze-like: all streams slow and similar.
    assert fused_validates_ab(0.02, 0.02, 0.025, low_contrast_mps=DEFAULT_LOW_CONTRAST_MPS)
    # Fused disagrees: anatomical > blob but fused even faster than anatomical.
    assert not fused_validates_ab(0.12, 0.02, 0.20, low_contrast_mps=DEFAULT_LOW_CONTRAST_MPS)


def test_build_contrast_sidecar_rows_anatomical_primary() -> None:
    key = ("042", 3)
    anatomical = {
        key: StreamPrototypeScalars(mean_speed_mps=0.12, frac_still=0.4, cluster_id=2, ambiguous=False),
    }
    blob = {key: StreamPrototypeScalars(mean_speed_mps=0.02, frac_still=0.9)}
    fused = {key: StreamPrototypeScalars(mean_speed_mps=0.08, frac_still=0.5)}
    rows = build_contrast_sidecar_rows(anatomical, blob, fused)
    assert len(rows) == 1
    row = rows[0]
    assert row["delta_speed_ab"] == pytest.approx(0.10)
    assert row["delta_speed_af"] == pytest.approx(0.04)
    assert row["delta_frac_still_ab"] == pytest.approx(-0.5)
    assert row["blob_present"] == 1
    assert row["fused_present"] == 1
    assert row["fused_validates_ab"] == 1
    assert row["cluster_id"] == 2


def test_build_contrast_sidecar_rows_missing_blob_fused() -> None:
    key = ("042", 1)
    anatomical = {key: StreamPrototypeScalars(mean_speed_mps=0.05, frac_still=0.8, cluster_id=0)}
    rows = build_contrast_sidecar_rows(anatomical, {}, {})
    assert rows[0]["blob_present"] == 0
    assert rows[0]["fused_present"] == 0
    assert rows[0]["fused_validates_ab"] == 0
    assert rows[0]["mean_speed_mps_blob"] == ""


def test_load_and_write_contrast_sidecar_roundtrip(tmp_path: Path) -> None:
    phase_i = tmp_path / "behavior_ethogram" / "phase_i"
    header = (
        "seed,raw_syllable_id,cluster_id,T_s,T_max,n_pad_dims,mean_speed_mps,"
        "global_occupancy,n_instances,speed_index,frac_still,mean_abs_dheading,"
        "bout_speed_iqr,ambiguous\n"
    )
    for stream, speed in (("anatomical", "0.12"), ("blob", "0.02"), ("fused", "0.08")):
        path = hdbscan_labels_path(phase_i, stream)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            header + f"042,3,2,8,8,0,{speed},0.1,4,1,0.4,0.2,0.01,0\n",
            encoding="utf-8",
        )

    rows = build_contrast_sidecar_from_dirs(phase_i)
    out = contrast_sidecar_path(phase_i)
    write_contrast_sidecar_csv(out, rows)
    text = out.read_text(encoding="utf-8")
    assert "delta_speed_ab" in text
    assert text.splitlines()[1].startswith("042,3,")
    loaded = load_hdbscan_label_table(hdbscan_labels_path(phase_i, "anatomical"))
    assert loaded[("042", 3)].mean_speed_mps == pytest.approx(0.12)
    assert list(CONTRAST_SIDECAR_FIELDS)[0] == "seed"
