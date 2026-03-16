"""
SLEAP-NN inference for VAST trial manifest (any/all combo of animal ID, session, trial).

Loads trials from the VAST trial manifest (database or CSV), filters by optional
--animal-id, --session, --trial, and runs sleap-nn inference on each selected trial's
video. Writes .predictions.slp alongside the video (or to --output-dir).

Requires sleap-nn: run with uv from the sleap-nn project, e.g.:
    cd C:\\Users\\admin\\code\\sleap-nn
    uv run python C:\\Users\\admin\\code\\IMPRESS\\VAST\\scripts\\sleap_nn_inference_oldVAST.py --model <path> [filters]

Usage:
    # All trials in manifest (from DB)
    python scripts/sleap_nn_inference_oldVAST.py --model path/to/model

    # From trial_manifest.csv (old VAST / no DB)
    python scripts/sleap_nn_inference_oldVAST.py --manifest-csv inputs/trial_manifest.csv --model path/to/model

    # Specific animal(s)
    python scripts/sleap_nn_inference_oldVAST.py --model path/to/model --animal-id 5416 3017

    # Specific session(s) and/or trial(s)
    python scripts/sleap_nn_inference_oldVAST.py --model path/to/model --session S01 S02 --trial T01

    # Dry run
    python scripts/sleap_nn_inference_oldVAST.py --manifest-csv inputs/trial_manifest.csv --model path/to/model --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# VAST project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from vast_pipeline.config import OUTPUT_H5
from vast_pipeline.io.file_discovery import TrialManifest, load_manifest_csv
from vast_pipeline.pipeline.orchestrator import load_manifests_from_db
from vast_pipeline.storage.h5_db import TrialKey, write_sleap_model_path, write_sleap_path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / "sleap_nn_inference.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def _run_inference(
    video_path: Path,
    output_path: Path,
    model_path: Path,
    batch_size: int,
    device: str,
) -> bool:
    """Run sleap-nn inference on one video. Returns True on success."""
    try:
        from sleap_nn.predict import run_inference
    except ImportError as e:
        logger.error(
            "sleap_nn not available. Run from sleap-nn env: uv run --project <sleap-nn-dir> python ..."
        )
        raise e

    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_inference(
        data_path=str(video_path),
        model_paths=[str(model_path)],
        output_path=str(output_path),
        batch_size=batch_size,
        device=device,
        no_empty_frames=True,
    )
    return True


def _parse_list_arg(s: str | None) -> list[str]:
    """Parse comma-separated or space-separated list; empty/None => []."""
    if not s or not s.strip():
        return []
    return [x.strip() for x in s.replace(",", " ").split() if x.strip()]


def filter_manifests(
    manifests: list[TrialManifest],
    animal_ids: list[str] | None,
    sessions: list[str] | None,
    trials: list[str] | None,
) -> list[TrialManifest]:
    """Keep only manifests matching any of the given animal_id, session, trial (omit = no filter)."""
    out = list(manifests)
    if animal_ids:
        out = [m for m in out if m.animal_id in animal_ids]
    if sessions:
        out = [m for m in out if m.session in sessions]
    if trials:
        out = [m for m in out if m.trial in trials]
    return out


def get_output_path(manifest: TrialManifest, output_dir: Path | None) -> Path:
    """Default: same dir as video, same stem + .predictions.slp. If output_dir set, same basename there."""
    if not manifest.video_path:
        raise FileNotFoundError(f"No video_path for {manifest.trial_key}")
    if output_dir is None:
        return manifest.video_path.with_suffix(".predictions.slp")
    return output_dir / manifest.video_path.with_suffix(".predictions.slp").name


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run SLEAP-NN inference on VAST trial manifest (filter by ID/session/trial)"
    )
    # Manifest source: DB (default) or CSV
    parser.add_argument(
        "--db",
        type=str,
        default=r"C:\Users\admin\code\IMPRESS\VAST\vast_results.h5",
        help="VAST database path (default: config OUTPUT_H5). Used when not using --manifest-csv.",
    )
    parser.add_argument(
        "--manifest-csv",
        type=str,
        default=None,
        help="Load trials from this CSV (e.g. inputs/trial_manifest.csv) instead of DB.",
    )
    # Filters: any/all combo; omit = all
    parser.add_argument(
        "--animal-id",
        type=str,
        nargs="*",
        default=None,
        help="Animal ID(s), e.g. 5416 3017. Omit = all.",
    )
    parser.add_argument(
        "--session",
        type=str,
        nargs="*",
        default=None,
        help="Session(s), e.g. S01 S02. Omit = all.",
    )
    parser.add_argument(
        "--trial",
        type=str,
        nargs="*",
        default=None,
        help="Trial(s), e.g. T01 T02. Omit = all.",
    )
    # Inference
    parser.add_argument(
        "--model",
        type=str,
        default=r"D:\work sack\vibration maze\models\260212_085317.single_instance.n=1375",
        help="Path to sleap-nn model directory (best.ckpt, training_config.yaml).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for .predictions.slp files (default: same dir as each video).",
    )
    parser.add_argument("--batch-size", type=int, default=16, help="Inference batch size")
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        help="Device: auto, cuda:0, cpu, etc.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip trials that already have a .predictions.slp output.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List selected trials and output paths only.",
    )
    args = parser.parse_args()

    # Resolve manifest source
    if args.manifest_csv:
        manifest_path = Path(args.manifest_csv)
        if not manifest_path.is_absolute():
            manifest_path = Path(__file__).parent.parent / manifest_path
        if not manifest_path.exists():
            logger.error("Manifest CSV not found: %s", manifest_path)
            sys.exit(1)
        logger.info("Loading manifests from CSV: %s", manifest_path)
        manifests = load_manifest_csv(manifest_path)
    else:
        db_path = Path(args.db) if args.db else OUTPUT_H5
        if not db_path.exists():
            logger.error("Database not found: %s. Run init_db first or use --manifest-csv.", db_path)
            sys.exit(1)
        logger.info("Loading manifests from DB: %s", db_path)
        manifests = load_manifests_from_db(db_path)

    if not manifests:
        logger.warning("No trials in manifest.")
        sys.exit(0)

    # Flatten and split comma-separated values (e.g. --animal-id 5416,3017 or 5416 3017)
    def _expand(vals):
        if not vals:
            return None
        out = []
        for v in vals:
            out.extend(x.strip() for x in str(v).split(",") if x.strip())
        return out if out else None

    animal_ids = _expand(args.animal_id)
    sessions = _expand(args.session)
    trials = _expand(args.trial)

    selected = filter_manifests(manifests, animal_ids, sessions, trials)
    # Only those with a video
    with_video = [m for m in selected if m.video_path and m.video_path.exists()]
    missing = [m for m in selected if not m.video_path or not m.video_path.exists()]
    if missing:
        logger.warning("Skipping %d trial(s) with missing video: %s", len(missing), [m.trial_key for m in missing])

    logger.info("Manifest total: %d, selected: %d, with video: %d", len(manifests), len(selected), len(with_video))
    if not with_video:
        logger.warning("No trials to process.")
        sys.exit(0)

    output_dir = Path(args.output_dir) if args.output_dir else None
    model_path = Path(args.model)
    if not model_path.exists() or not (model_path / "best.ckpt").exists():
        logger.error("Model path must contain best.ckpt: %s", model_path)
        sys.exit(1)

    if args.dry_run:
        logger.info("DRY RUN - would run inference on:")
        for m in with_video:
            out = get_output_path(m, output_dir)
            logger.info("  %s -> %s", m.trial_key, out)
        return

    stats = {"total": len(with_video), "success": 0, "failed": 0, "skipped": 0}
    for i, manifest in enumerate(with_video, 1):
        out_path = get_output_path(manifest, output_dir)
        if args.skip_existing and out_path.exists():
            logger.info("[%d/%d] Skip (exists): %s", i, stats["total"], out_path)
            stats["skipped"] += 1
            continue
        logger.info("[%d/%d] %s -> %s", i, stats["total"], manifest.trial_key, out_path)
        try:
            start = time.perf_counter()
            _run_inference(
                video_path=manifest.video_path,
                output_path=out_path,
                model_path=model_path,
                batch_size=args.batch_size,
                device=args.device,
            )
            elapsed = time.perf_counter() - start
            logger.info("  Done in %.2f s", elapsed)
            stats["success"] += 1
            # Record sleap_path and model in the VAST DB so sync_db is not required after inference
            db_path = Path(args.db) if args.db else OUTPUT_H5
            if db_path.exists():
                try:
                    key = TrialKey.from_manifest(manifest)
                    write_sleap_path(db_path, key, str(out_path.resolve()))
                    write_sleap_model_path(db_path, key, str(model_path.resolve()))
                except Exception as e:
                    logger.warning("  Could not write sleap_path/sleap_model_path to DB: %s", e)
        except Exception as e:
            logger.exception("  Failed: %s", e)
            stats["failed"] += 1

    logger.info("Done: %d success, %d skipped, %d failed", stats["success"], stats["skipped"], stats["failed"])
    if stats["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
