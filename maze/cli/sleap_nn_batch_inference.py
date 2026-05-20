#!/usr/bin/env python3
"""
SLEAP-NN Batch Inference Script

Runs sleap-nn inference on all videos in a directory and saves results as
.predictions.slp files (native SLP format). Uses sleap_nn.predict.run_inference
directly instead of the legacy sleap-track CLI.

Usage (from OpenEthoMaze repo root, requires ``--extra sleap``)::

    uv run maze-sleap-nn-batch-inference --model <model_dir> --video-dir <dir> [options]
"""

import sys
import time
from pathlib import Path
import argparse
from datetime import datetime
import logging

# Configure logging before importing sleap_nn (it uses loguru; we keep stdlib for script output)
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "sleap_nn_inference.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def _run_inference(video_path: Path, output_path: Path, model_path: Path, batch_size: int, device: str) -> bool:
    """Run sleap-nn inference on one video. Returns True on success."""
    try:
        from sleap_nn.predict import run_inference
    except ImportError as e:
        logger.error("sleap_nn not installed or not on PATH. Install with: pip install -e <sleap-nn repo>")
        raise e

    output_path = Path(output_path)
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


class SLEAPNNBatchInference:
    def __init__(
        self,
        model_path: str,
        video_dir: str,
        output_dir: str | None = None,
        batch_size: int = 16,
        device: str = "auto",
        start_substring: str | None = None,
    ):
        """
        Args:
            model_path: Path to sleap-nn model directory (contains best.ckpt and training_config.yaml).
            video_dir: Directory to search recursively for videos.
            output_dir: Where to write .predictions.slp files; defaults to same as video_dir.
            batch_size: Inference batch size.
            device: "auto", "cuda:0", "cpu", etc.
            start_substring: If set, start from first video whose path contains this substring (resume).
        """
        self.model_path = Path(model_path)
        self.video_dir = Path(video_dir)
        self.output_dir = Path(output_dir) if output_dir else self.video_dir
        self.batch_size = batch_size
        self.device = device
        self.start_substring = start_substring

        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not self.model_path.exists():
            raise FileNotFoundError(f"Model path does not exist: {self.model_path}")

        ckpt = self.model_path / "best.ckpt"
        if not ckpt.exists():
            raise FileNotFoundError(f"Model checkpoint not found: {ckpt}")

        logger.info("Initialized SLEAP-NN batch inference")
        logger.info("Model path: %s", self.model_path)
        logger.info("Video directory: %s", self.video_dir)
        logger.info("Output directory: %s", self.output_dir)
        logger.info("Batch size: %s", self.batch_size)
        logger.info("Device: %s", self.device)
        if self.start_substring:
            logger.info("Start substring: %s", self.start_substring)

    def find_video_files(self) -> list[Path]:
        """Find all .mp4 or .avi files under video_dir, sorted for deterministic order."""
        video_files = sorted(
            [*self.video_dir.rglob("*.mp4"), *self.video_dir.rglob("*.avi")],
            key=lambda p: str(p).lower()
        )
        logger.info("Found %d video files", len(video_files))
        return video_files

    def get_output_path(self, video_path: Path) -> Path:
        """Output path: under output_dir, same relative structure, suffix .predictions.slp."""
        rel = video_path.relative_to(self.video_dir)
        out = self.output_dir / rel.with_suffix(".predictions.slp")
        out.parent.mkdir(parents=True, exist_ok=True)
        return out

    def run_inference(self, video_path: Path, output_path: Path) -> bool:
        """Run inference on a single video. Returns True on success."""
        try:
            logger.info("Running inference on: %s", video_path.name)
            start = time.perf_counter()
            _run_inference(
                video_path=video_path,
                output_path=output_path,
                model_path=self.model_path,
                batch_size=self.batch_size,
                device=self.device,
            )
            elapsed = time.perf_counter() - start
            logger.info("Processed %s in %.2f s", video_path.name, elapsed)
            return True
        except Exception as e:
            logger.exception("Error processing %s: %s", video_path.name, e)
            return False

    def process_all_videos(self) -> dict:
        """Process all videos (respecting start_substring and skipping existing)."""
        video_files = self.find_video_files()
        to_process = video_files

        if self.start_substring:
            idx = next((i for i, p in enumerate(video_files) if self.start_substring in str(p)), None)
            if idx is None:
                logger.warning("No video path contains substring %r. Nothing to process.", self.start_substring)
                now = datetime.now()
                return {"total": 0, "successful": 0, "failed": 0, "start_time": now, "end_time": now, "duration": now - now}
            to_process = video_files[idx:]
            logger.info("Resuming from %s (matched %r)", to_process[0].name, self.start_substring)

        if not to_process:
            logger.warning("No videos to process.")
            return {"total": 0, "successful": 0, "failed": 0}

        stats = {"total": len(to_process), "successful": 0, "failed": 0, "start_time": datetime.now()}
        logger.info("Starting batch processing of %d videos", len(to_process))

        for i, video_path in enumerate(to_process, 1):
            logger.info("Processing video %d/%d: %s", i, len(to_process), video_path.name)
            output_path = self.get_output_path(video_path)

            if output_path.exists():
                logger.info("Output exists, skipping: %s", output_path)
                stats["successful"] += 1
                continue

            if self.run_inference(video_path, output_path):
                stats["successful"] += 1
            else:
                stats["failed"] += 1

        stats["end_time"] = datetime.now()
        stats["duration"] = stats["end_time"] - stats["start_time"]
        return stats

    def print_summary(self, stats: dict) -> None:
        """Log a short summary of processing."""
        logger.info("=" * 50)
        logger.info("PROCESSING SUMMARY")
        logger.info("=" * 50)
        logger.info("Total videos: %d", stats["total"])
        logger.info("Successful: %d", stats["successful"])
        logger.info("Failed: %d", stats["failed"])
        if stats.get("total", 0):
            logger.info("Success rate: %.1f%%", stats["successful"] / stats["total"] * 100)
            logger.info("Total duration: %s", stats["duration"])
            logger.info("Average time per video: %s", stats["duration"] / stats["total"])
        else:
            logger.info("Success rate: N/A (no videos)")
            logger.info("Total duration: %s", stats.get("duration", "N/A"))
            logger.info("Average time per video: N/A")
        logger.info("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SLEAP-NN batch inference: run inference on all videos and save .predictions.slp"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=r"D:\work sack\vibration maze\models\260212_085317.single_instance.n=1375",
        help="Path to sleap-nn model directory (best.ckpt, training_config.yaml)",
    )
    parser.add_argument(
        "--video-dir",
        type=str,
        default=r"D:\work sack\vibration maze\Kevan Lim",
        help="Directory containing videos to process (searched recursively for .mp4 or .avi)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for .predictions.slp files (default: same as --video-dir)",
    )
    parser.add_argument("--batch-size", type=int, default=16, help="Inference batch size")
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        help="Device: 'auto', 'cuda:0', 'cpu', etc.",
    )
    parser.add_argument(
        "--start-substring",
        type=str,
        default=None,
        help="Resume at first video whose path contains this substring (e.g. '3017')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List videos and output paths without running inference",
    )
    args = parser.parse_args()

    try:
        processor = SLEAPNNBatchInference(
            model_path=args.model,
            video_dir=args.video_dir,
            output_dir=args.output_dir,
            batch_size=args.batch_size,
            device=args.device,
            start_substring=args.start_substring,
        )

        if args.dry_run:
            video_files = processor.find_video_files()
            to_show = video_files
            if processor.start_substring:
                idx = next((i for i, p in enumerate(video_files) if processor.start_substring in str(p)), None)
                if idx is None:
                    logger.info("DRY RUN - No video path contains substring %r.", processor.start_substring)
                    return
                to_show = video_files[idx:]
                logger.info("DRY RUN - Resuming from %s (matched %r)", to_show[0].name, processor.start_substring)
            logger.info("DRY RUN - Would process:")
            for video_path in to_show:
                out = processor.get_output_path(video_path)
                logger.info("  %s -> %s", video_path, out)
            return

        stats = processor.process_all_videos()
        processor.print_summary(stats)
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
