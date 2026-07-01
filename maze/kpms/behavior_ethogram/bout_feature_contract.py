"""Bout scalar feature contract (Option D Stage II/III substrate).

Single source of truth for CSV columns and ML feature name lists.
Documented in ``docs/bout_feature_contract.md`` (schema id ``bout_feature_v2``).
"""

from __future__ import annotations

from dataclasses import dataclass

from maze.kpms.manifest_subset import STRATIFY_LABEL_COLUMNS

BOUT_FEATURE_SCHEMA_VERSION = "bout_feature_v2"

# Stage II HDBSCAN / default AR-HMM base (z-scored in cluster.py and arhmm.py).
CLUSTERING_FEATURE_NAMES: tuple[str, ...] = (
    "bout_mean_speed_mps",
    "bout_mean_abs_dheading",
    "bout_mean_blob_area_px2",
    "bout_iqr_speed_mps",
    "bout_iqr_abs_dheading",
    "bout_iqr_blob_area_px2",
    "bout_duration_s",
    "bout_net_dheading_rad",
    "bout_straightness",
)

# Appended when ``include_heading_direction=True`` (sin/cos, not raw radians).
OPTIONAL_HEADING_FEATURE_NAMES: tuple[str, ...] = (
    "bout_mean_heading_sin",
    "bout_mean_heading_cos",
)

# Stage III AR-HMM append — pooled kinematic signature per raw_syllable_id (ADR-0005).
SYLLABLE_SIGNATURE_FEATURE_NAMES: tuple[str, ...] = (
    "syllable_sig_mean_speed_mps",
    "syllable_sig_mean_abs_dheading",
    "syllable_sig_mean_blob_area_px2",
)

# ``stage_ii/bout_features.csv`` and ``stage_iii/bout_behavior_tokens.csv`` column order.
BOUT_TABLE_FIELDS: tuple[str, ...] = (
    "stream",
    "seed",
    "trial_key",
    *STRATIFY_LABEL_COLUMNS,
    "raw_syllable_id",
    "bout_index",
    "row_start",
    "row_end_exclusive",
    "bout_frames",
    "bout_duration_s",
    "bout_mean_speed_mps",
    "bout_mean_abs_dheading",
    "bout_mean_blob_area_px2",
    "bout_iqr_speed_mps",
    "bout_iqr_abs_dheading",
    "bout_iqr_blob_area_px2",
    "bout_mean_heading_rad",
    "bout_iqr_heading_rad",
    "bout_net_dheading_rad",
    "bout_straightness",
    "bout_primary_state",
    "ambiguous",
    "cluster_id",
    "behavior_token",
)


@dataclass(frozen=True)
class BoutFieldSpec:
    name: str
    units: str
    description: str
    group: str


BOUT_FIELD_SPECS: tuple[BoutFieldSpec, ...] = (
    BoutFieldSpec(
        "stream",
        "",
        "Pose stream that produced the kpMS syllable sequence (default ``anatomical``).",
        "identity",
    ),
    BoutFieldSpec(
        "seed",
        "",
        "kpMS apply seed id (e.g. ``042``) from ``anatomical/seed_<seed>/results_apply.h5``.",
        "identity",
    ),
    BoutFieldSpec(
        "trial_key",
        "",
        "kpMS recording key / manifest trial key (e.g. ``3243/S01/T01``).",
        "identity",
    ),
    *(
        BoutFieldSpec(
            name,
            "",
            f"Manifest stratification label ``{name}`` (from trial manifest; optional ``--enrich-labels``).",
            "stratify",
        )
        for name in STRATIFY_LABEL_COLUMNS
    ),
    BoutFieldSpec(
        "raw_syllable_id",
        "",
        "kpMS syllable id for this bout (maximal run of identical syllable labels).",
        "identity",
    ),
    BoutFieldSpec(
        "bout_index",
        "",
        "0-based bout index within the trial (syllable-run order along kpMS-aligned rows).",
        "identity",
    ),
    BoutFieldSpec(
        "row_start",
        "kpMS row",
        "Inclusive start index into the kpMS-aligned per-frame arrays for this bout.",
        "span",
    ),
    BoutFieldSpec(
        "row_end_exclusive",
        "kpMS row",
        "Exclusive end index into the kpMS-aligned per-frame arrays for this bout.",
        "span",
    ),
    BoutFieldSpec(
        "bout_frames",
        "frames",
        "``row_end_exclusive - row_start``; count of kpMS rows in the bout.",
        "extent",
    ),
    BoutFieldSpec(
        "bout_duration_s",
        "s",
        "``bout_frames / fps``.",
        "extent",
    ),
    BoutFieldSpec(
        "bout_mean_speed_mps",
        "m/s",
        "Mean centroid speed over the bout (legacy-aligned timeline; see compile).",
        "kinematic_mean",
    ),
    BoutFieldSpec(
        "bout_mean_abs_dheading",
        "rad/frame",
        "Mean absolute per-frame heading change (unwrapped heading delta).",
        "kinematic_mean",
    ),
    BoutFieldSpec(
        "bout_mean_blob_area_px2",
        "px²",
        "Mean tracking blob polygon area over the bout (NaN if blob missing).",
        "kinematic_mean",
    ),
    BoutFieldSpec(
        "bout_iqr_speed_mps",
        "m/s",
        "Interquartile range of per-frame speed within the bout.",
        "kinematic_spread",
    ),
    BoutFieldSpec(
        "bout_iqr_abs_dheading",
        "rad/frame",
        "Interquartile range of per-frame |Δheading| within the bout.",
        "kinematic_spread",
    ),
    BoutFieldSpec(
        "bout_iqr_blob_area_px2",
        "px²",
        "Interquartile range of per-frame blob area within the bout.",
        "kinematic_spread",
    ),
    BoutFieldSpec(
        "bout_mean_heading_rad",
        "rad",
        "Circular mean heading (optional CSV column when ``include_heading_direction`` at compile).",
        "heading",
    ),
    BoutFieldSpec(
        "bout_iqr_heading_rad",
        "rad",
        "Circular IQR of heading relative to circular mean (optional CSV column).",
        "heading",
    ),
    BoutFieldSpec(
        "bout_net_dheading_rad",
        "rad",
        "Signed net heading change across the bout (unwrapped end − start).",
        "path_geometry",
    ),
    BoutFieldSpec(
        "bout_straightness",
        "0–1",
        "Net displacement / path length along centroid track, clipped to [0, 1].",
        "path_geometry",
    ),
    BoutFieldSpec(
        "bout_primary_state",
        "",
        "Majority legacy ``trial_state`` label over bout rows (e.g. run, iti); empty if unavailable.",
        "qc",
    ),
    BoutFieldSpec(
        "ambiguous",
        "0/1",
        "1 when ``bout_iqr_speed_mps`` exceeds the ambiguous-speed threshold (default 0.08 m/s).",
        "qc",
    ),
    BoutFieldSpec(
        "cluster_id",
        "",
        "HDBSCAN cluster label from Stage II (QC / exploration; not an AR-HMM feature in S2).",
        "stage_ii",
    ),
    BoutFieldSpec(
        "behavior_token",
        "",
        "Decoded Stage III bout AR-HMM state id (Option D producer mechanism).",
        "stage_iii",
    ),
)

OPTIONAL_HEADING_FIELD_SPECS: tuple[BoutFieldSpec, ...] = (
    BoutFieldSpec(
        "bout_mean_heading_sin",
        "",
        "sin component of circular mean heading (AR-HMM / clustering matrix when ``include_heading_direction``).",
        "heading",
    ),
    BoutFieldSpec(
        "bout_mean_heading_cos",
        "",
        "cos component of circular mean heading (AR-HMM / clustering matrix when ``include_heading_direction``).",
        "heading",
    ),
)


SYLLABLE_SIGNATURE_FIELD_SPECS: tuple[BoutFieldSpec, ...] = (
    BoutFieldSpec(
        "syllable_sig_mean_speed_mps",
        "m/s",
        "Cohort-pooled mean of ``bout_mean_speed_mps`` for this bout's ``raw_syllable_id``.",
        "syllable_signature",
    ),
    BoutFieldSpec(
        "syllable_sig_mean_abs_dheading",
        "rad/frame",
        "Cohort-pooled mean of ``bout_mean_abs_dheading`` for this bout's ``raw_syllable_id``.",
        "syllable_signature",
    ),
    BoutFieldSpec(
        "syllable_sig_mean_blob_area_px2",
        "px²",
        "Cohort-pooled mean of ``bout_mean_blob_area_px2`` for this bout's ``raw_syllable_id``.",
        "syllable_signature",
    ),
)


def arhmm_feature_names(*, include_heading_direction: bool = False) -> tuple[str, ...]:
    """Default Stage III feature vector: clustering base + optional heading + signature."""
    names: list[str] = list(CLUSTERING_FEATURE_NAMES)
    if include_heading_direction:
        names.extend(OPTIONAL_HEADING_FEATURE_NAMES)
    names.extend(SYLLABLE_SIGNATURE_FEATURE_NAMES)
    return tuple(names)


def field_spec_by_name() -> dict[str, BoutFieldSpec]:
    specs = {s.name: s for s in BOUT_FIELD_SPECS}
    for s in OPTIONAL_HEADING_FIELD_SPECS:
        specs[s.name] = s
    for s in SYLLABLE_SIGNATURE_FIELD_SPECS:
        specs[s.name] = s
    return specs


def assert_contract_in_sync() -> None:
    """Raise ``AssertionError`` if tuples and field specs drift (used by contract tests)."""
    spec_names = [s.name for s in BOUT_FIELD_SPECS]
    if tuple(spec_names) != BOUT_TABLE_FIELDS:
        raise AssertionError("BOUT_FIELD_SPECS names must match BOUT_TABLE_FIELDS order")
    sig_names = [s.name for s in SYLLABLE_SIGNATURE_FIELD_SPECS]
    if tuple(sig_names) != SYLLABLE_SIGNATURE_FEATURE_NAMES:
        raise AssertionError("SYLLABLE_SIGNATURE_FIELD_SPECS must match SYLLABLE_SIGNATURE_FEATURE_NAMES")
    specs = field_spec_by_name()
    for name in CLUSTERING_FEATURE_NAMES:
        if name not in specs:
            raise AssertionError(f"missing field spec for clustering feature {name}")
    for name in OPTIONAL_HEADING_FEATURE_NAMES:
        if name not in specs:
            raise AssertionError(f"missing field spec for optional heading feature {name}")
    opt_names = [s.name for s in OPTIONAL_HEADING_FIELD_SPECS]
    if tuple(opt_names) != OPTIONAL_HEADING_FEATURE_NAMES:
        raise AssertionError("OPTIONAL_HEADING_FIELD_SPECS must match OPTIONAL_HEADING_FEATURE_NAMES")
    for name in CLUSTERING_FEATURE_NAMES:
        if name not in BOUT_TABLE_FIELDS:
            raise AssertionError(f"clustering feature {name} missing from BOUT_TABLE_FIELDS")
