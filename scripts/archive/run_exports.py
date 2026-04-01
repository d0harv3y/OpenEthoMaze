"""
Export VAST results to CSV files for analysis.

Usage:
    python scripts/run_exports.py                # Export all
    python scripts/run_exports.py --output-dir ./exports  # Custom output directory
"""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from maze.pipeline.exports import export_all
from maze.pipeline.config import OUTPUT_H5


def main():
    parser = argparse.ArgumentParser(
        description="Export VAST results to CSV files"
    )
    
    parser.add_argument(
        '--db', '-d',
        type=str,
        help='Path to VAST database (default: vast_results.h5)'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        help='Output directory for CSV files'
    )

    parser.add_argument(
        '--include-mistrials',
        action='store_true',
        help='Include mistrial trials in trial summary CSV (default: exclude them)'
    )

    args = parser.parse_args()

    db_path = Path(args.db) if args.db else OUTPUT_H5
    output_dir = Path(args.output_dir) if args.output_dir else None

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        print("Run the pipeline first: python scripts/run_pipeline.py")
        sys.exit(1)

    exports = export_all(db_path, output_dir, include_mistrials=args.include_mistrials)
    
    print("\nGenerated files:")
    for name, path in exports.items():
        print(f"  {name}: {path}")


if __name__ == '__main__':
    main()
