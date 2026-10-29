#!/usr/bin/env python3
"""One-shot / idempotent frontmatter for openethomaze vault notes.

UTF-8, no BOM. Skips files that already start with ---.
Infers type/status/assay/claim_kind; applies Concordance aliases.
"""

from __future__ import annotations

import re
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]

# Old filename stem (no .md) → list of alias display names for Obsidian
CONCORDANCE_ALIASES: dict[str, list[str]] = {
    "H Alphabet Equating": ["Q Accent Alphabet Equating"],
    "H Assay Validity NOR": ["Q0 Assay Validity NOR"],
    "H Novelty Preference DR": ["Q1 Condition Effect on DR"],
    "H Physio Coupling": ["Q2 Behavior Physio Association"],
    "V Engagement Physio Null": ["Q2 Engagement Physio Honesty Pass"],
    "V DR Physio Null": ["Q2 Honesty Pass"],
    "H Syllable Task State": ["Q3 Syllable Task State"],
    "H Investigation Quality": ["Q4 Investigation Quality"],
    "V Visit Grammar Null": ["Q5 BoutGrammar Honesty Pass"],
    "E Visit Grammar Counts": ["Q5 BoutGrammar Score Contract"],
    "V Candidate Lattice Null": ["Q5 Candidates Honesty Pass"],
    "H Recognition Separators": ["Q5 Condition Separating Behavior"],
    "V Engagement Delta": ["Q5 Honesty Pass", "V Engagement Delta Treasure"],
    "V Near Misses Watchlist": ["Q5 Near Misses"],
    "V Occupancy Delta Null": ["Q5 Occupancy Session-Delta Honesty Pass"],
    "E Occupancy Session Delta": ["Q5 Occupancy Session-Delta Score Contract"],
    "V Recognition Lattice Null": ["Q5 Recognition Honesty Pass"],
    "V Side Geometry Null": ["Q5 SideMass Honesty Pass"],
    "E Side Geometry": ["Q5 SideMass Score Contract"],
    "V TransStruct Cross-Campaign": ["Q5 Transition Structure Cross-Campaign Readout"],
    "V TransStruct Null": ["Q5 Transition Structure Honesty Pass"],
    "V TransStruct Raw Exploratory": ["Q5 Transition Structure Raw Exploratory"],
    "Q5 Transition Structure Score Contract": ["Q5 Transition Structure Score Contract"],
}

# Manual overrides: stem → property bag (merged on top of inference)
OVERRIDES: dict[str, dict] = {
    "V Engagement Delta": {
        "status": "treasure",
        "verdict": "partial",
        "claim_kind": "clock-portable",
    },
    "V Composition Companion Partial": {
        "status": "treasure",
        "verdict": "partial",
        "claim_kind": "mixed",
    },
    "V Protocol Step Clocks": {
        "status": "ladder",
        "verdict": "partial",
        "claim_kind": "clock-portable",
    },
    "V Near Misses Watchlist": {
        "status": "rabbit-hole",
        "verdict": "na",
        "claim_kind": "mixed",
    },
    "H Assay Validity NOR": {
        "status": "ladder",
        "verdict": "na",
        "claim_kind": "clock-portable",
    },
    "H Recognition Separators": {
        "status": "rabbit-hole",
        "verdict": "na",
        "claim_kind": "mixed",
    },
    "H Non-Recognition Condition Separators": {
        "status": "treasure",
        "verdict": "na",
        "claim_kind": "mixed",
    },
    "T0 Altered Behavior": {"status": "treasure", "verdict": "na"},
    "T1 Recognition NOR": {"status": "rabbit-hole", "verdict": "na"},
    "Prune Map": {"type": "ops", "status": "lava", "assay": "shared"},
    "NOR IMPRESS Index": {"type": "ops", "status": "treasure", "assay": "nor-impress"},
    "VAST Alz Index": {"type": "ops", "status": "open", "assay": "vast-alz"},
    "Motion Sequencing Honest Report": {
        "type": "report",
        "status": "ladder",
        "assay": "nor-impress",
        "claim_kind": "mixed",
    },
    "README": {"type": "ops", "status": "na", "assay": "shared"},
}


def yaml_escape(s: str) -> str:
    if any(c in s for c in ":{}[]&*#?|,!<>=!%@`"):
        return '"' + s.replace('"', '\\"') + '"'
    return s


def infer_type(rel: Path, stem: str) -> str:
    parts = rel.parts
    if "theories" in parts:
        return "theory"
    if "hypotheses" in parts:
        return "hypothesis"
    if "estimands" in parts or stem.startswith("E "):
        return "estimand"
    if "families" in parts or stem.startswith("F "):
        return "family"
    if stem.startswith("V "):
        return "verdict"
    if stem.startswith("Run "):
        return "run"
    if stem.startswith("H "):
        return "hypothesis"
    if stem.startswith("T"):
        return "theory"
    if "Score Contract" in stem:
        return "family"
    if parts[0] == "shared":
        return "ops"
    if parts[0] == "questions":
        if stem.startswith("Q"):
            return "ops"
        return "verdict"
    return "ops"


def infer_assay(rel: Path) -> str:
    s = str(rel).replace("\\", "/")
    if "vast-alz" in s:
        return "vast-alz"
    if "nor-impress" in s:
        return "nor-impress"
    if rel.parts[0] in {"theories", "hypotheses", "estimands", "families", "questions", "shared"}:
        # shared claim layer — nor-primary unless VAST-named
        if "VAST" in rel.stem or "Flexibility" in rel.stem or "Prodromal" in rel.stem:
            return "vast-alz"
        return "nor-impress"
    return "shared"


def infer_claim_kind(text: str) -> str:
    has_clock = "#clock-portable" in text or "clock-portable" in text
    has_alpha = "#alphabet-bound" in text or "alphabet-bound" in text
    if has_clock and has_alpha:
        return "mixed"
    if has_clock:
        return "clock-portable"
    if has_alpha:
        return "alphabet-bound"
    return "na"


def infer_verdict_outcome(stem: str, text: str) -> str:
    head = text[:2500].lower()
    if stem.startswith("V ") and "null" in stem.lower():
        return "fail"
    if "partial pass" in head:
        return "partial"
    if re.search(r"\*\*fail\b", head) or re.search(r"\bfail\.\*\*", head):
        return "fail"
    if "**pass" in head or "locked" in head and "engagement" in head:
        return "pass"
    if stem.startswith("F ") and "fail" in head:
        return "fail"
    if stem.startswith("Run ") and "fail" in head:
        return "fail"
    return "na"


def infer_status(stem: str, ntype: str, verdict: str, text: str) -> str:
    head = text[:2000]
    if "#lava" in head or stem == "Prune Map":
        return "lava"
    if "#treasure" in head or (stem == "V Engagement Delta"):
        return "treasure"
    if "#snake" in head:
        return "snake"
    if "#ladder" in head:
        return "ladder"
    if "#rabbit-hole" in head or "rabbit-hole" in head.lower():
        return "rabbit-hole"
    if ntype == "verdict":
        if verdict == "partial" and "Engagement" in stem:
            return "treasure"
        if verdict == "fail" or "Null" in stem:
            return "lava"
        if verdict == "partial":
            return "ladder"
        return "ladder"
    if ntype == "run":
        if verdict == "fail":
            return "ladder"
        return "ladder"
    if ntype == "family":
        return "lava" if verdict == "fail" else "open"
    if ntype == "hypothesis":
        if "open" in head.lower() or "hunt" in head.lower():
            return "rabbit-hole"
        return "open"
    if ntype == "theory":
        return "open"
    if ntype == "estimand":
        return "open"
    return "na"


def build_frontmatter(rel: Path, text: str) -> str:
    stem = rel.stem
    ntype = infer_type(rel, stem)
    assay = infer_assay(rel)
    claim_kind = infer_claim_kind(text)
    verdict = infer_verdict_outcome(stem, text)
    status = infer_status(stem, ntype, verdict, text)

    props: dict = {
        "title": stem,
        "type": ntype,
        "assay": assay,
        "status": status,
        "claim_kind": claim_kind,
        "verdict": verdict,
    }
    props.update(OVERRIDES.get(stem, {}))

    tags = [f"claim/{props['type']}", f"assay/{props['assay']}"]
    st = props["status"]
    if st and st != "na":
        tags.append(st)
    ck = props["claim_kind"]
    if ck and ck != "na":
        tags.append(ck)

    aliases = list(CONCORDANCE_ALIASES.get(stem, []))
    # Also alias filename without V/H prefix quirks
    if stem.startswith("V ") and stem.endswith(" Null"):
        pass

    lines = ["---"]
    lines.append(f"title: {yaml_escape(props['title'])}")
    lines.append(f"type: {props['type']}")
    lines.append(f"assay: {props['assay']}")
    lines.append(f"status: {props['status']}")
    lines.append(f"claim_kind: {props['claim_kind']}")
    lines.append(f"verdict: {props['verdict']}")
    lines.append("tags:")
    for t in tags:
        lines.append(f"  - {t}")
    if aliases:
        lines.append("aliases:")
        for a in aliases:
            lines.append(f"  - {yaml_escape(a)}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def move_stray_estimands() -> None:
    src = VAULT / "questions"
    dst = VAULT / "estimands"
    dst.mkdir(exist_ok=True)
    for p in list(src.glob("E *.md")):
        target = dst / p.name
        if target.exists():
            print(f"skip move (exists): {p.name}")
            continue
        p.rename(target)
        print(f"moved {p.name} → estimands/")


def main() -> None:
    move_stray_estimands()
    n_add = 0
    n_skip = 0
    for path in sorted(VAULT.rglob("*.md")):
        if ".obsidian" in path.parts:
            continue
        rel = path.relative_to(VAULT)
        raw = path.read_text(encoding="utf-8")
        if raw.startswith("---\n") or raw.startswith("---\r\n"):
            n_skip += 1
            continue
        fm = build_frontmatter(rel, raw)
        path.write_text(fm + raw, encoding="utf-8", newline="\n")
        n_add += 1
        print(f"+ {rel}")
    print(f"done: added={n_add} skipped={n_skip}")


if __name__ == "__main__":
    main()
