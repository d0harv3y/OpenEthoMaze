"""NOR SLEAP discovery + per-animal param-sweep wiring."""

from __future__ import annotations

from pathlib import Path

from maze.kpms.nor_slp_manifest import (
    discover_nor_animal_bundles,
    parse_nor_slp_stem,
    stem_from_slp_name,
    write_animal_manifest_csv,
)
from maze.kpms.paramscan import iter_nor_per_animal_paramscan_grid


def test_parse_nor_slp_stem_with_and_without_seq() -> None:
    a = parse_nor_slp_stem("NOR2 NVL OBJ Arena 3 04-16-25 100 3015 17-18")
    assert a == ("2", "NVL", "3", "04-16-25", "3015")
    b = parse_nor_slp_stem("NOR1 NO OBJ Arena 5 04-03-25 3007 14-16")
    assert b == ("1", "NO", "5", "04-03-25", "3007")
    assert parse_nor_slp_stem("Habituation something") is None


def test_stem_from_slp_name() -> None:
    assert (
        stem_from_slp_name("NOR1 ID OBJ Arena 1 04-09-25 55 3013 17-17.h5.slp")
        == "NOR1 ID OBJ Arena 1 04-09-25 55 3013 17-17"
    )
    assert stem_from_slp_name("foo.slp") == "foo"


def _touch_slp(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def test_discover_and_manifest_mirror_tree(tmp_path: Path) -> None:
    root = tmp_path / "standard format"
    animal = root / "exp2" / "3015"
    names = [
        "NOR1 NO OBJ Arena 1 04-09-25 10 3015 10-00.h5.slp",
        "NOR1 ID OBJ Arena 1 04-09-25 11 3015 10-10.h5.slp",
        "NOR1 NVL OBJ Arena 1 04-09-25 12 3015 10-20.h5.slp",
        "NOR2 NVL OBJ Arena 3 04-16-25 100 3015 17-18.h5.slp",
        "Habituation Arena 1 04-01-25 3015 09-00.h5.slp",
        "junk.slp",
    ]
    for n in names:
        _touch_slp(animal / n)

    # Wrong folder ID mismatch should be skipped
    other = root / "exp2" / "9999"
    _touch_slp(other / "NOR1 NVL OBJ Arena 1 04-09-25 1 3015 10-00.h5.slp")

    bundles = discover_nor_animal_bundles(root)
    assert len(bundles) == 1
    b = bundles[0]
    assert b.cohort == "exp2"
    assert b.animal_id == "3015"
    assert len(b.recordings) == 4

    out = tmp_path / "F_mirror" / "exp2" / "3015" / "trial_manifest.csv"
    write_animal_manifest_csv(b, out)
    text = out.read_text(encoding="utf-8")
    assert "3015" in text
    assert "no_obj" in text and "id_obj" in text and "nvl_obj" in text
    assert "NOR1" in text and "NOR2" in text
    rows = [ln for ln in text.splitlines() if ln and not ln.startswith("animal_id")]
    assert len(rows) == 4
    assert all(r.split(",")[0] == "3015" for r in rows)
    # SLEAP-only: blank input_h5_path column
    header = text.splitlines()[0].split(",")
    h5_i = header.index("input_h5_path")
    assert all(r.split(",")[h5_i] == "" for r in rows)


def test_per_animal_sweep_discover_only(tmp_path: Path) -> None:
    from maze.cli.kpms_per_animal_param_sweep import main, parse_args

    root = tmp_path / "standard format"
    animal = root / "exp1" / "3007"
    _touch_slp(animal / "NOR1 NVL OBJ Arena 5 04-03-25 3007 14-16.h5.slp")
    _touch_slp(animal / "NOR1 NO OBJ Arena 5 04-03-25 1 3007 14-00.h5.slp")

    out = tmp_path / "F_out"
    argv = [
        "--data-root",
        str(root),
        "--output-root",
        str(out),
        "--discover-only",
    ]
    args = parse_args(argv)
    assert args.discover_only
    main(argv)

    manifest = out / "exp1" / "3007" / "trial_manifest.csv"
    assert manifest.is_file()
    plan = out / "per_animal_paramscan_plan.json"
    assert plan.is_file()
    payload = plan.read_text(encoding="utf-8")
    assert '"n_animals": 1' in payload
    assert '"n_jobs_per_animal": 9' in payload

    jobs = list(iter_nor_per_animal_paramscan_grid())
    animal_plan = (out / "exp1" / "3007" / "paramscan_animal_plan.json").read_text(
        encoding="utf-8"
    )
    assert "3007_paramscan_" in animal_plan
    assert len(jobs) == 9
