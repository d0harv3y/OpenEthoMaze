"""Bout-level n-gram mining and span filters for NOR / impress kpMS."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterator, Mapping, Sequence

import h5py
import numpy as np

from .ngram_decisions import MAX_N_MINE, OTHER_PATTERN_ID
from .syllable_cleanup import maybe_absorb_short_bouts, rle_labels

NGRAM_OCC_FIELDS: tuple[str, ...] = (
    "kpms_key",
    "trial_key",
    "animal_id",
    "raw_session",
    "phase_layer",
    "condition_layer",
    "tx",
    "sex",
    "cohort",
    "pattern_len",
    "ngram_index",
    "pattern_json",
    "pattern_id",  # top-M remapped id; OTHER = -1 (filled later)
    "bout_index_start",
    "row_start",
    "row_end_exclusive",
    "span_frames",
    "bout_mean_dist_fam_m",
    "bout_mean_dist_nvl_m",
    "bout_mean_dist_obj_a_m",
    "bout_mean_dist_obj_b_m",
    "bout_mean_dist_locus_a_m",
    "bout_mean_dist_locus_b_m",
    "bout_mean_dist_any_m",
    "obj_a_id",
    "obj_b_id",
    "dist_any_source",
    "locus_label_policy",
    "role_at_locus_a",
    "role_at_locus_b",
    "nvl_nearest_hist_locus",
)

DIST_FIELDS: tuple[str, ...] = (
    "bout_mean_dist_fam_m",
    "bout_mean_dist_nvl_m",
    "bout_mean_dist_obj_a_m",
    "bout_mean_dist_obj_b_m",
    "bout_mean_dist_locus_a_m",
    "bout_mean_dist_locus_b_m",
    "bout_mean_dist_any_m",
)


def pattern_key(ids: Sequence[int]) -> tuple[int, ...]:
    return tuple(int(x) for x in ids)


def pattern_json(ids: Sequence[int]) -> str:
    return json.dumps([int(x) for x in ids], separators=(",", ":"))


def iter_ngrams_with_spans(
    labels: np.ndarray,
    durs: np.ndarray,
    starts: np.ndarray,
    *,
    max_n: int,
    max_span_frames: int | None = None,
) -> Iterator[tuple[int, tuple[int, ...], int, int, int, int]]:
    """Yield (n, pattern, bout_index_start, row_start, row_end_excl, span_frames)."""
    labels = np.asarray(labels, dtype=np.int64)
    durs = np.asarray(durs, dtype=np.int64)
    starts = np.asarray(starts, dtype=np.int64)
    n_bouts = int(labels.size)
    if n_bouts == 0:
        return
    c = np.cumsum(durs)
    ends = starts + durs
    for n in range(1, int(max_n) + 1):
        if n_bouts < n:
            continue
        for i in range(n_bouts - n + 1):
            span = int(c[i + n - 1] - (0 if i == 0 else c[i - 1]))
            if max_span_frames is not None and span > int(max_span_frames):
                continue
            pat = pattern_key(labels[i : i + n])
            yield n, pat, i, int(starts[i]), int(ends[i + n - 1]), span


def mine_results_h5(
    results_h5: Path | str,
    *,
    max_n: int = MAX_N_MINE,
    min_bout_frames: int | None = None,
    max_span_frames: int | None = None,
    min_count: int = 2,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Count n-grams across all recordings in a kpMS results.h5."""
    counts: dict[tuple[int, ...], int] = defaultdict(int)
    trials: dict[tuple[int, ...], set[str]] = defaultdict(set)
    span_sum: dict[tuple[int, ...], int] = defaultdict(int)
    span_n: dict[tuple[int, ...], int] = defaultdict(int)
    n_rec = 0
    n_frames = 0
    n_bouts_tot = 0
    with h5py.File(results_h5, "r") as f:
        for key in f.keys():
            z = maybe_absorb_short_bouts(f[key]["syllable"][()], min_bout_frames)
            labels, durs, starts = rle_labels(z)
            n_rec += 1
            n_frames += int(z.size)
            n_bouts_tot += int(labels.size)
            seen: set[tuple[int, ...]] = set()
            for n, pat, _i, _rs, _re, span in iter_ngrams_with_spans(
                labels,
                durs,
                starts,
                max_n=max_n,
                max_span_frames=max_span_frames,
            ):
                counts[pat] += 1
                span_sum[pat] += span
                span_n[pat] += 1
                if pat not in seen:
                    trials[pat].add(str(key))
                    seen.add(pat)
    rows: list[dict[str, object]] = []
    for pat, cnt in counts.items():
        if cnt < min_count:
            continue
        rows.append(
            {
                "pattern_json": pattern_json(pat),
                "pattern_len": len(pat),
                "count": int(cnt),
                "n_trials": len(trials[pat]),
                "mean_span_frames": float(span_sum[pat] / max(span_n[pat], 1)),
            }
        )
    rows.sort(key=lambda r: (-int(r["count"]), -int(r["pattern_len"]), str(r["pattern_json"])))
    summary = {
        "n_recordings": n_rec,
        "n_frames": n_frames,
        "n_bouts": n_bouts_tot,
        "max_n": int(max_n),
        "min_bout_frames": min_bout_frames,
        "max_span_frames": max_span_frames,
        "min_count": int(min_count),
        "n_patterns": len(rows),
    }
    return rows, summary


def _weighted_mean(values: Sequence[float], weights: Sequence[int]) -> float:
    num = 0.0
    den = 0
    for v, w in zip(values, weights):
        fv = float(v)
        iw = int(w)
        if not np.isfinite(fv) or iw <= 0:
            continue
        num += fv * iw
        den += iw
    if den == 0:
        return float("nan")
    return float(num / den)


def ngram_rows_from_bout_rows(
    bout_rows: Sequence[Mapping[str, object]],
    *,
    pattern_len: int,
    max_span_frames: int | None = None,
) -> list[dict[str, object]]:
    """Build n-gram occurrences from ladder bout rows (span-mean distances)."""
    n = int(pattern_len)
    if n < 1:
        raise ValueError("pattern_len must be >= 1")
    by_trial: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in bout_rows:
        by_trial[str(row["trial_key"])].append(row)

    out: list[dict[str, object]] = []
    for trial_key, trows in by_trial.items():
        trows = sorted(trows, key=lambda r: int(r["bout_index"]))
        if len(trows) < n:
            continue
        meta = trows[0]
        for i in range(len(trows) - n + 1):
            window = trows[i : i + n]
            weights = [int(r["bout_frames"]) for r in window]
            span = int(sum(weights))
            if max_span_frames is not None and span > int(max_span_frames):
                continue
            ids = [int(r["raw_syllable_id"]) for r in window]
            occ: dict[str, object] = {
                "kpms_key": meta["kpms_key"],
                "trial_key": trial_key,
                "animal_id": meta["animal_id"],
                "raw_session": meta["raw_session"],
                "phase_layer": meta["phase_layer"],
                "condition_layer": meta["condition_layer"],
                "tx": meta["tx"],
                "sex": meta["sex"],
                "cohort": meta["cohort"],
                "pattern_len": n,
                "ngram_index": i,
                "pattern_json": pattern_json(ids),
                "pattern_id": "",  # filled by assign_top_m_other
                "bout_index_start": int(window[0]["bout_index"]),
                "row_start": int(window[0]["row_start"]),
                "row_end_exclusive": int(window[-1]["row_end_exclusive"]),
                "span_frames": span,
                "obj_a_id": meta.get("obj_a_id", ""),
                "obj_b_id": meta.get("obj_b_id", ""),
                "dist_any_source": meta.get("dist_any_source", ""),
                "locus_label_policy": meta.get("locus_label_policy", ""),
                "role_at_locus_a": meta.get("role_at_locus_a", ""),
                "role_at_locus_b": meta.get("role_at_locus_b", ""),
                "nvl_nearest_hist_locus": meta.get("nvl_nearest_hist_locus", ""),
            }
            for field in DIST_FIELDS:
                occ[field] = _weighted_mean([float(r[field]) for r in window], weights)
            out.append(occ)
    return out


def assign_top_m_other(
    rows: Sequence[Mapping[str, object]],
    *,
    top_m: int,
    other_id: int = OTHER_PATTERN_ID,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Remap pattern_json → pattern_id in {0..top_m-1} ∪ {other_id}.

    Ranking is by occurrence count in ``rows`` (stable: count desc, pattern_json).
    """
    top_m = int(top_m)
    if top_m < 1:
        raise ValueError("top_m must be >= 1")
    counts = Counter(str(r["pattern_json"]) for r in rows)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    codebook = {pat: i for i, (pat, _) in enumerate(ranked[:top_m])}
    out: list[dict[str, object]] = []
    n_other = 0
    for r in rows:
        row = dict(r)
        pat = str(row["pattern_json"])
        if pat in codebook:
            row["pattern_id"] = int(codebook[pat])
        else:
            row["pattern_id"] = int(other_id)
            n_other += 1
        out.append(row)
    meta = {
        "top_m": top_m,
        "other_id": int(other_id),
        "n_patterns_total": len(counts),
        "n_patterns_kept": len(codebook),
        "n_occ": len(rows),
        "n_occ_other": n_other,
        "codebook": [
            {"pattern_id": i, "pattern_json": pat, "count": int(counts[pat])}
            for pat, i in sorted(codebook.items(), key=lambda kv: kv[1])
        ],
    }
    return out, meta
