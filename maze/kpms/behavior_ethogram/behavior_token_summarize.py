"""Occupancy and transition summaries for Stage III behavior tokens."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, Sequence

from maze.pipeline.io.file_discovery import TrialManifest

from .behavior_token_labels import validate_ethology_curation_complete

Grain = Literal["token", "ethology"]
PhaseName = Literal["run", "iti"]


@dataclass(frozen=True)
class SummarizeBoutRow:
    trial_key: str
    bout_index: int
    behavior_token: int
    bout_duration_s: float
    bout_primary_state: str
    seed: str


def _parse_float(raw: str, default: float = 0.0) -> float:
    text = str(raw).strip()
    if not text:
        return default
    return float(text)


def summarize_bout_rows_from_table(
    table: Sequence[Mapping[str, str]],
    *,
    seed: str | None = None,
) -> list[SummarizeBoutRow]:
    """Build summarize rows from ``bout_behavior_tokens.csv``."""
    out: list[SummarizeBoutRow] = []
    for row in table:
        if seed is not None and str(row.get("seed", "")) != str(seed):
            continue
        token_raw = str(row.get("behavior_token", "")).strip()
        if not token_raw:
            continue
        out.append(
            SummarizeBoutRow(
                trial_key=str(row["trial_key"]),
                bout_index=int(row["bout_index"]),
                behavior_token=int(token_raw),
                bout_duration_s=_parse_float(str(row.get("bout_duration_s", "0"))),
                bout_primary_state=str(row.get("bout_primary_state", "")),
                seed=str(row["seed"]),
            )
        )
    return out


def bout_in_phase(primary_state: str, phase: PhaseName) -> bool:
    """Return whether a bout belongs to the requested phase."""
    state = str(primary_state).strip().lower()
    if not state:
        state = "run"
    if phase == "run":
        return state == "run"
    return state != "run"


def label_for_grain(
    behavior_token: int,
    *,
    grain: Grain,
    token_to_label: Mapping[int, str],
) -> str:
    if grain == "token":
        return str(int(behavior_token))
    return str(token_to_label[int(behavior_token)])


def _strata_key(
    manifest: TrialManifest,
    *,
    by_session: bool,
) -> tuple[str, str, str, str]:
    session = str(manifest.session) if by_session else ""
    return (
        session,
        str(manifest.tx or ""),
        str(manifest.sex or ""),
        str(manifest.strain or ""),
    )


def _manifests_for_rows(
    bout_rows: Sequence[SummarizeBoutRow],
    manifests_by_trial_key: Mapping[str, TrialManifest],
) -> list[tuple[SummarizeBoutRow, TrialManifest]]:
    paired: list[tuple[SummarizeBoutRow, TrialManifest]] = []
    for row in bout_rows:
        manifest = manifests_by_trial_key.get(row.trial_key)
        if manifest is None:
            continue
        paired.append((row, manifest))
    return paired


def aggregate_occupancy_rows(
    bout_rows: Sequence[SummarizeBoutRow],
    *,
    manifests_by_trial_key: Mapping[str, TrialManifest],
    grain: Grain,
    phase: PhaseName,
    token_to_label: Mapping[int, str],
    by_session: bool,
) -> list[dict[str, str]]:
    """Compute occupancy fractions per stratum (pooled or session-stratified)."""
    label_duration: dict[tuple[str, str, str, str, str], float] = defaultdict(float)
    phase_duration: dict[tuple[str, str, str, str], float] = defaultdict(float)
    trials: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    animals: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)

    for row, manifest in _manifests_for_rows(bout_rows, manifests_by_trial_key):
        if not bout_in_phase(row.bout_primary_state, phase):
            continue
        session, tx, sex, strain = _strata_key(manifest, by_session=by_session)
        stratum = (session, tx, sex, strain)
        label = label_for_grain(row.behavior_token, grain=grain, token_to_label=token_to_label)
        duration = max(0.0, float(row.bout_duration_s))
        phase_duration[stratum] += duration
        label_duration[(session, tx, sex, strain, label)] += duration
        trials[stratum].add(row.trial_key)
        animals[stratum].add(str(manifest.animal_id))

    out: list[dict[str, str]] = []
    for (session, tx, sex, strain, label), label_dur in sorted(label_duration.items()):
        stratum = (session, tx, sex, strain)
        total = phase_duration[stratum]
        frac = (label_dur / total) if total > 0 else 0.0
        out.append(
            {
                "grain": grain,
                "label": label,
                "phase": phase,
                "session": session,
                "tx": tx,
                "sex": sex,
                "strain": strain,
                "occupancy_fraction": f"{frac:.6f}",
                "label_duration_s": f"{label_dur:.6f}",
                "phase_duration_s": f"{total:.6f}",
                "n_trials": str(len(trials[stratum])),
                "n_animals": str(len(animals[stratum])),
            }
        )
    return out


def build_transition_rows(
    bout_rows: Sequence[SummarizeBoutRow],
    *,
    manifests_by_trial_key: Mapping[str, TrialManifest],
    grain: Grain,
    phase: PhaseName,
    token_to_label: Mapping[int, str],
    by_session: bool,
) -> list[dict[str, str]]:
    """Count consecutive bout transitions within trials for one phase."""
    by_trial: dict[str, list[SummarizeBoutRow]] = defaultdict(list)
    for row in bout_rows:
        if row.trial_key in manifests_by_trial_key:
            by_trial[row.trial_key].append(row)

    transition_counts: dict[tuple[str, str, str, str, str, str], int] = defaultdict(int)
    trials: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    animals: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)

    for trial_key, trial_rows in by_trial.items():
        manifest = manifests_by_trial_key[trial_key]
        session, tx, sex, strain = _strata_key(manifest, by_session=by_session)
        stratum = (session, tx, sex, strain)
        phase_rows = [r for r in sorted(trial_rows, key=lambda r: r.bout_index) if bout_in_phase(r.bout_primary_state, phase)]
        if len(phase_rows) < 2:
            continue
        trials[stratum].add(trial_key)
        animals[stratum].add(str(manifest.animal_id))
        for left, right in zip(phase_rows, phase_rows[1:]):
            label_i = label_for_grain(left.behavior_token, grain=grain, token_to_label=token_to_label)
            label_j = label_for_grain(right.behavior_token, grain=grain, token_to_label=token_to_label)
            transition_counts[(session, tx, sex, strain, label_i, label_j)] += 1

    stratum_totals: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for (session, tx, sex, strain, _i, _j), count in transition_counts.items():
        stratum_totals[(session, tx, sex, strain)] += int(count)

    out: list[dict[str, str]] = []
    for (session, tx, sex, strain, label_i, label_j), count in sorted(transition_counts.items()):
        stratum = (session, tx, sex, strain)
        total = stratum_totals[stratum]
        rate = (float(count) / float(total)) if total > 0 else 0.0
        out.append(
            {
                "grain": grain,
                "label_i": label_i,
                "label_j": label_j,
                "phase": phase,
                "session": session,
                "tx": tx,
                "sex": sex,
                "strain": strain,
                "transition_count": str(int(count)),
                "transition_rate": f"{rate:.6f}",
                "n_trials": str(len(trials[stratum])),
                "n_animals": str(len(animals[stratum])),
            }
        )
    return out


def write_summary_csv(
    path: Path | str,
    rows: Sequence[Mapping[str, str]],
    *,
    fieldnames: Sequence[str],
) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    return p


def resolve_token_to_label(
    bout_rows: Sequence[SummarizeBoutRow],
    label_rows: Sequence[Mapping[str, str]] | None,
    *,
    grain: Grain,
    allow_partial: bool,
    min_token_bouts: int,
) -> dict[int, str]:
    """Build token→label map for summarize, enforcing ethology review gate."""
    tokens = sorted({int(r.behavior_token) for r in bout_rows})
    if grain == "token":
        return {token: str(token) for token in tokens}

    if not label_rows:
        raise ValueError("ethology grain requires behavior_token_labels.csv")

    errors = validate_ethology_curation_complete(label_rows, min_token_bouts=min_token_bouts)
    if errors and not allow_partial:
        raise ValueError("ethology curation incomplete:\n" + "\n".join(errors))

    label_map = token_to_label_map(label_rows, grain=grain, allow_partial=allow_partial)
    for token in tokens:
        if token not in label_map:
            if allow_partial:
                label_map[token] = f"token_{token}"
            else:
                raise ValueError(f"behavior_token {token} missing from behavior_token_labels.csv")
    return label_map


def token_to_label_map(
    label_rows: Sequence[Mapping[str, str]],
    *,
    grain: Grain,
    allow_partial: bool,
) -> dict[int, str]:
    """Build behavior_token → summary label map for the requested grain."""
    out: dict[int, str] = {}
    for row in label_rows:
        token = int(str(row["behavior_token"]).strip())
        if grain == "token":
            out[token] = str(token)
            continue
        name = str(row.get("behavior_name", "")).strip()
        if name:
            out[token] = name
        elif allow_partial:
            out[token] = f"token_{token}"
    return out


def summarize_behavior_tokens(
    *,
    bout_rows: Sequence[SummarizeBoutRow],
    manifests_by_trial_key: Mapping[str, TrialManifest],
    grain: Grain,
    phases: Sequence[PhaseName],
    token_to_label: Mapping[int, str],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Return occupancy, occupancy_by_session, and transition row lists."""
    occupancy: list[dict[str, str]] = []
    occupancy_by_session: list[dict[str, str]] = []
    transitions: list[dict[str, str]] = []
    for phase in phases:
        occupancy.extend(
            aggregate_occupancy_rows(
                bout_rows,
                manifests_by_trial_key=manifests_by_trial_key,
                grain=grain,
                phase=phase,
                token_to_label=token_to_label,
                by_session=False,
            )
        )
        occupancy_by_session.extend(
            aggregate_occupancy_rows(
                bout_rows,
                manifests_by_trial_key=manifests_by_trial_key,
                grain=grain,
                phase=phase,
                token_to_label=token_to_label,
                by_session=True,
            )
        )
        transitions.extend(
            build_transition_rows(
                bout_rows,
                manifests_by_trial_key=manifests_by_trial_key,
                grain=grain,
                phase=phase,
                token_to_label=token_to_label,
                by_session=False,
            )
        )
        transitions.extend(
            build_transition_rows(
                bout_rows,
                manifests_by_trial_key=manifests_by_trial_key,
                grain=grain,
                phase=phase,
                token_to_label=token_to_label,
                by_session=True,
            )
        )
    return occupancy, occupancy_by_session, transitions
