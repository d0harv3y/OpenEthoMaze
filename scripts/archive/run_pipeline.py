"""
Main entry point for running the VAST pipeline.

Usage:
    python scripts/run_pipeline.py                    # Process all trials
    python scripts/run_pipeline.py --animal 2314      # Process single animal
    python scripts/run_pipeline.py --animals 1 2 3 4 5 6  # Process multiple animals
    python scripts/run_pipeline.py --phase experimental  # Process only experimental trials
    python scripts/run_pipeline.py --session S01 S02 --trial T01  # Specific sessions/trials
    python scripts/run_pipeline.py --no-qc           # Skip QC image generation
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from vast_pipeline.pipeline.orchestrator import run_pipeline, run_single_trial
from vast_pipeline.config import OUTPUT_H5


def main():
    parser = argparse.ArgumentParser(
        description="Run VAST data processing pipeline"
    )
    
    parser.add_argument(
        '--animal', '--animals', '-a',
        type=str,
        nargs='+',
        dest='animal',
        help='Animal ID(s) to process (e.g. --animals 1 2 3 4 5 6)'
    )
    
    parser.add_argument(
        '--phase', '-p',
        type=str,
        choices=['habituation', 'experimental'],
        help='Process only specific phase'
    )
    
    parser.add_argument(
        '--session', '-s',
        type=str,
        nargs='*',
        default=None,
        help='Session(s) to process, e.g. S01 S02. Omit = all.'
    )
    
    parser.add_argument(
        '--trial', '-t',
        type=str,
        nargs='*',
        default=None,
        help='Trial(s) to process, e.g. T01 T02. Omit = all.'
    )
    
    parser.add_argument(
        '--no-qc',
        action='store_true',
        help='Skip QC image generation'
    )

    parser.add_argument(
        '--no-skip-mistrials',
        action='store_true',
        help='Process trials with missing data (default: skip them and write mistrial_reason to DB)'
    )

    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output database path (default: vast_results.h5)'
    )
    
    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=4,
        help='Number of parallel workers (default: 4)'
    )
    
    args = parser.parse_args()
    
    db_path = Path(args.output) if args.output else OUTPUT_H5
    generate_qc = not args.no_qc

    def _normalize_session(s: str) -> str:
        """Convert bare number to canonical session name (e.g. 4 -> S04)."""
        if s and s[0].upper() in ("S", "H"):
            return s
        return f"S{int(s):02d}" if s.isdigit() else s

    def _normalize_trial(s: str) -> str:
        """Convert bare number to canonical trial name (e.g. 1 -> T01)."""
        if s and s[0].upper() == "T":
            return s
        return f"T{int(s):02d}" if s.isdigit() else s

    # Single trial mode when exactly one animal, one session, one trial
    sessions_list = args.session if args.session else []
    trials_list = args.trial if args.trial else []
    if (args.animal and len(args.animal) == 1 and
            len(sessions_list) == 1 and len(trials_list) == 1):
        session = _normalize_session(sessions_list[0])
        trial = _normalize_trial(trials_list[0])
        success = run_single_trial(
            animal_id=args.animal[0],
            phase=args.phase,
            session=session,
            trial=trial,
            db_path=db_path,
            generate_qc=generate_qc,
        )
        sys.exit(0 if success else 1)
    
    # Batch processing mode
    stats = run_pipeline(
        db_path=db_path,
        animal_ids=args.animal,
        phase=args.phase,
        sessions=args.session or None,
        trial_names=args.trial or None,
        max_workers=args.workers,
        generate_qc=generate_qc,
        skip_mistrials=not args.no_skip_mistrials,
    )
    
    # Exit with error if any trials failed
    if stats['failed'] > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
