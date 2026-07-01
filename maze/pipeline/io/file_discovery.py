"""
Legacy VAST manifest discovery and file matching.

Handles discovery and matching of:
- Input H5 files containing trial settings and legacy tracking
- Video files (.avi) for each trial
- SLEAP prediction files (.slp, .h5.slp, .analysis.h5)

The source data is organized across multiple folders under two researcher directories
(Kevan Lim, Nickolas Pasetto) with various cohort subfolders.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence, Union

import h5py

from ..paths import DATA_DIR, DATA_DIRS, MAX_SESSION_NUM, MAX_TRIAL_NUM, SESSION_RENUMBER

logger = logging.getLogger(__name__)

# Canonical CSV column order for trial manifests (discovery, legacy_db, kpMS selection).
# Labels first (identity + treatment), then QA counts, then paths.
MANIFEST_CSV_FIELDNAMES: tuple[str, ...] = (
    "animal_id",
    "session",
    "original_session",
    "trial",
    "phase",
    "exit_number",
    "sex",
    "strain",
    "tx",
    "experiment",
    "drug",
    "cohort",
    "researcher",
    "inferred_id",
    "timestamp",
    "h5_n_frames",
    "video_n_frames",
    "frame_diff",
    "input_h5_path",
    "video_path",
    "sleap_path",
    "has_tracking_pose",
    "kpms_recording_key",
)


def trial_manifest_csv_row_values(t: "TrialManifest") -> list[str]:
    """One CSV data row in :data:`MANIFEST_CSV_FIELDNAMES` order."""
    timestamp_str = t.timestamp.isoformat() if t.timestamp else ""
    h5_frames_str = str(t.h5_n_frames) if t.h5_n_frames is not None else ""
    vid_frames_str = str(t.video_n_frames) if t.video_n_frames is not None else ""
    if t.h5_n_frames is not None and t.video_n_frames is not None:
        diff_str = str(t.video_n_frames - t.h5_n_frames)
    else:
        diff_str = ""
    return [
        t.animal_id,
        t.session,
        t.original_session or "",
        t.trial,
        t.phase,
        "" if t.exit_number is None else str(int(t.exit_number)),
        t.sex or "",
        t.strain or "",
        t.tx or "",
        t.experiment or "",
        t.drug or "",
        t.cohort or "",
        t.researcher or "",
        t.inferred_id or "",
        timestamp_str,
        h5_frames_str,
        vid_frames_str,
        diff_str,
        str(t.input_h5_path),
        str(t.video_path) if t.video_path else "",
        str(t.sleap_path) if t.sleap_path else "",
        "1" if t.has_tracking_pose else "0",
        t.kpms_recording_key or "",
    ]


def enrich_manifests_from_treatment_labels(
    manifests: list["TrialManifest"],
    labels_path: Optional[Path] = None,
) -> None:
    """
    Fill missing label fields on each manifest from ``treatment_labels.csv``.

    Only updates attributes that are missing or blank so CSV values win when present.
    """
    labels = load_treatment_labels(labels_path)
    for trial in manifests:
        if trial.animal_id not in labels:
            continue
        label = labels[trial.animal_id]
        if not (trial.strain or "").strip():
            trial.strain = label.strain or trial.strain
        if not (trial.experiment or "").strip():
            trial.experiment = label.experiment or trial.experiment
        if not (trial.sex or "").strip():
            trial.sex = label.sex or trial.sex
        if not (trial.tx or "").strip():
            trial.tx = label.tx or trial.tx
        if not (trial.drug or "").strip():
            trial.drug = label.drug or trial.drug
        if not (trial.researcher or "").strip():
            trial.researcher = label.researcher or trial.researcher


@dataclass
class TrialManifest:
    """Container for a single trial's file paths and metadata."""

    animal_id: str
    session: str  # e.g., "S01", "S05", "hS01" (habituation)
    trial: str  # e.g., "T01", "T02"

    # File paths
    input_h5_path: Path
    video_path: Optional[Path] = None
    sleap_path: Optional[Path] = None

    # Metadata inferred from file structure
    is_habituation: bool = False
    cohort: Optional[str] = None
    researcher: Optional[str] = None  # "Kevan Lim" or "Nickolas Pasetto"

    # Treatment labels (populated from treatment_labels.csv)
    strain: Optional[str] = None  # F344-WT, F344t-AD, AZm -/-, AZm +/+
    experiment: Optional[str] = None  # VAST_NP, LAST_NP, VASTcontKL
    sex: Optional[str] = None  # M or F
    tx: Optional[str] = None  # treatment group e.g. SF, noSF
    drug: Optional[str] = None  # drug condition e.g. vehicle, compound name

    # For mislabeled trials (IDs 1-4), this holds the inferred correct ID
    inferred_id: Optional[str] = None

    # Timestamp from H5 settings (for matching and review)
    timestamp: Optional[datetime] = None

    # Frame counts for validation (more reliable than duration)
    h5_n_frames: Optional[int] = None  # Frame count from H5 data array
    video_n_frames: Optional[int] = None  # Frame count from AVI file

    # Original session key before renumbering (for loading from H5/video)
    # If None, session was not renumbered.
    original_session: Optional[str] = None

    #: When set, used as kpMS HDF5 / coordinates dict key (native path-style names).
    kpms_recording_key: Optional[str] = None

    #: True when ``tracking/anatomical`` is present in canonical trial H5 (v2 tracking).
    has_tracking_pose: bool = False

    #: VAST assigned exit (1-based); from legacy input H5 settings or results H5 attrs.
    exit_number: Optional[int] = None

    @property
    def h5_session(self) -> str:
        """Session key to use when loading from H5 (original if renumbered)."""
        return self.original_session if self.original_session else self.session

    @property
    def trial_key(self) -> str:
        """Unique identifier for this trial."""
        return f"{self.animal_id}/{self.session}/{self.trial}"

    @property
    def kpms_results_dict_key(self) -> str:
        """Key in kpMS ``coordinates`` / ``results`` dicts (matches :func:`maze.kpms.frame_alignment.kpms_recording_key`)."""
        if self.kpms_recording_key:
            return self.kpms_recording_key
        return f"{self.animal_id}-{self.session}-{self.trial}"

    @property
    def phase(self) -> str:
        """Return 'habituation' or 'experimental' based on is_habituation flag."""
        return "habituation" if self.is_habituation else "experimental"

    @property
    def effective_animal_id(self) -> str:
        """Return inferred_id if available, otherwise animal_id."""
        return self.inferred_id if self.inferred_id else self.animal_id


def _parse_manifest_bool(value: str | None) -> bool:
    if value is None:
        return False
    txt = str(value).strip().lower()
    return txt in ("1", "true", "yes", "y")


def _parse_manifest_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    txt = str(raw).strip()
    if not txt:
        return None
    try:
        return int(txt)
    except ValueError:
        return None


def enrich_manifests_exit_number(manifests: list[TrialManifest]) -> None:
    """
    Fill :attr:`TrialManifest.exit_number` from legacy input H5 settings or trial attrs.

    Skips rows that already have ``exit_number``. Uses ``input_h5_path`` (legacy
    acquisition H5 or kpMS results H5 with ``exit_number`` attr).
    """
    from ..db import open_db
    from ..db.trial_key import TrialKey
    from .input_h5_loader import load_trial_settings

    for manifest in manifests:
        if manifest.exit_number is not None:
            continue

        src = Path(manifest.input_h5_path) if str(manifest.input_h5_path).strip() else None
        if src is None or not src.is_file():
            continue

        try:
            settings = load_trial_settings(
                src,
                manifest.animal_id,
                manifest.h5_session,
                manifest.trial,
            )
            if settings.exit_number is not None:
                manifest.exit_number = int(settings.exit_number)
                continue
        except (OSError, KeyError, ValueError):
            pass

        try:
            key = TrialKey.from_manifest(manifest)
            with open_db(src, "r") as h5:
                g_trial = h5[key.path()]
                if "exit_number" in g_trial.attrs:
                    manifest.exit_number = int(g_trial.attrs["exit_number"])
        except (OSError, KeyError, TypeError, ValueError):
            continue


def enrich_manifests_has_tracking_pose(
    manifests: list[TrialManifest],
    *,
    db_path: Path | None = None,
) -> None:
    """
    Set :attr:`TrialManifest.has_tracking_pose` by probing canonical trial H5.

    Uses :func:`maze.kpms.h5_pose.resolve_canonical_trial_h5` (``input_h5_path`` first,
    then ``db_path``). Mutates manifests in place.
    """
    from maze.kpms.h5_pose import resolve_canonical_trial_h5

    db = Path(db_path) if db_path is not None else Path("")
    for manifest in manifests:
        manifest.has_tracking_pose = resolve_canonical_trial_h5(manifest, db) is not None


@dataclass
class DiscoveryResult:
    """Result of file discovery across the data directory."""

    trials: list[TrialManifest] = field(default_factory=list)
    input_h5_files: list[Path] = field(default_factory=list)
    video_files: list[Path] = field(default_factory=list)
    sleap_files: list[Path] = field(default_factory=list)

    # Statistics
    n_matched_videos: int = 0
    n_matched_sleap: int = 0
    n_unmatched_videos: int = 0

    def __repr__(self) -> str:
        return (
            f"DiscoveryResult(trials={len(self.trials)}, "
            f"h5_files={len(self.input_h5_files)}, "
            f"videos={len(self.video_files)}, "
            f"sleap={len(self.sleap_files)}, "
            f"matched_videos={self.n_matched_videos})"
        )


# Regex patterns for parsing filenames
VIDEO_PATTERN = re.compile(r"(\d+)_S(\d+)T(\d+)\.avi$", re.IGNORECASE)
# Controller acquisition: ``{animal_id}_{session}_{trial}.mp4`` (e.g. ``42_S01_T01.mp4``)
CONTROLLER_VIDEO_PATTERN = re.compile(
    r"^([\w.-]+)_(S\d+)_(T\d+)\.(?:mp4|avi)$",
    re.IGNORECASE,
)
SLEAP_PATTERN = re.compile(r"(\d+)_S(\d+)T(\d+).*\.(h5\.slp|slp|analysis\.h5)$", re.IGNORECASE)
CONTROLLER_SLEAP_PATTERN = re.compile(
    r"^([\w.-]+)_(S\d+)_(T\d+)(?:\.predictions)?\.(?:slp|h5\.slp)$",
    re.IGNORECASE,
)


def _parse_session_range(h5_path: Path) -> tuple[bool, Optional[int], Optional[int]]:
    """
    Parse session range and phase from H5 filename.

    Filenames like:
    - VastcontKL_AZ_male_H3-5.hdf5 -> habituation, sessions 3-5
    - VASTcontKL_AZ_male_S1-10.hdf5 -> experimental, sessions 1-10

    Returns:
        (is_habituation, start_session, end_session)
        If range cannot be parsed, returns (is_habituation, None, None)
    """
    name = h5_path.stem.upper()

    # Look for _H<num>-<num> or _S<num>-<num> patterns
    hab_match = re.search(r"_H(\d+)-(\d+)", name)
    if hab_match:
        return (True, int(hab_match.group(1)), int(hab_match.group(2)))

    exp_match = re.search(r"_S(\d+)-(\d+)", name)
    if exp_match:
        return (False, int(exp_match.group(1)), int(exp_match.group(2)))

    # Fallback: check habituation-like tokens in file names.
    # Includes legacy day-style naming (e.g., "...day45.hdf5").
    if re.search(r"_H\d", name) or "HABITUATION" in name or re.search(r"_D\d|_DAY\d", name):
        return (True, None, None)

    return (False, None, None)


def _is_habituation_h5(h5_path: Path) -> bool:
    """
    Determine if an H5 file contains habituation sessions based on filename.

    Habituation files typically have 'H' in the session range (e.g., H3-5)
    rather than 'S' (e.g., S1-10).
    """
    is_hab, _, _ = _parse_session_range(h5_path)
    return is_hab


def _path_looks_habituation(path: Path) -> bool:
    """
    True if the path (folder or filename) suggests habituation content.

    Matches the same conventions as H5 filenames: habituation, _Habituation,
    _H3-5, etc. Used so we only match videos/SLEAP from habituation folders
    to habituation manifests, and experimental to experimental.
    """
    s = str(path).lower()
    if "habituation" in s:
        return True
    if re.search(r"_h\d|_h\d+-\d+", s):
        return True
    if re.search(r"_d\d|_day\d|_day\d+\d+", s):
        return True
    return False


def _normalize_habituation_session(
    session: str,
    is_habituation: bool,
) -> tuple[str, Optional[str]]:
    """
    Normalize habituation session names to "hS##" for storage.

    Returns:
        (normalized_session, original_session_if_changed)
    """
    if not is_habituation:
        return (session, None)

    # Habituation sessions are stored as hS## in the new DB schema.
    # Keep the original H5-style session (typically S##) for lookup/loading.
    if re.match(r"^[sS]\d+$", session):
        return (f"h{session.upper()}", session)

    return (session, None)


def _session_in_range(
    session: str,
    start: Optional[int],
    end: Optional[int],
) -> bool:
    """
    Check if a session key (e.g., "S03") falls within a range.

    Args:
        session: Session key like "S03", "S10"
        start: Start of range (inclusive), or None for no filtering
        end: End of range (inclusive), or None for no filtering

    Returns:
        True if session is in range or no range specified
    """
    if start is None or end is None:
        return True  # No range specified, include all

    # Extract session number from key like "S03" -> 3
    session_num_match = re.search(r"\d+", session)
    if not session_num_match:
        return True  # Can't parse, include by default

    session_num = int(session_num_match.group())
    return start <= session_num <= end


def _infer_cohort_from_path(file_path: Path) -> Optional[str]:
    """Extract cohort information from file path."""
    path_str = str(file_path).lower()

    # Look for cohort patterns in path
    cohort_match = re.search(r"cohort\s*(\d+)", path_str, re.IGNORECASE)
    if cohort_match:
        return f"cohort{cohort_match.group(1)}"

    return None


def _infer_researcher_from_path(file_path: Path) -> Optional[str]:
    """Extract researcher name from file path."""
    path_parts = file_path.parts

    for part in path_parts:
        if "kevan" in part.lower():
            return "Kevan Lim"
        elif "nickolas" in part.lower() or "pasetto" in part.lower():
            return "Nickolas Pasetto"

    return None


def discover_input_h5_files(
    data_dir: Path = DATA_DIR,
    *,
    exclude_resolved: Optional[set[Path]] = None,
) -> list[Path]:
    """
    Recursively find all input HDF5 files in the data directory.

    Args:
        data_dir: Root directory to search
        exclude_resolved: Resolved paths to omit (e.g. target ``trials.h5`` results DB)

    Returns:
        List of paths to .hdf5 files
    """
    h5_files = []
    skip = exclude_resolved or set()

    for ext in ("*.hdf5", "*.h5"):
        # Exclude SLEAP files (.h5.slp, .analysis.h5)
        for path in data_dir.rglob(ext):
            if not path.name.endswith((".h5.slp", ".analysis.h5", ".slp")):
                try:
                    if path.resolve() in skip:
                        continue
                except OSError:
                    pass
                h5_files.append(path)

    return sorted(h5_files)


def discover_video_files(data_dir: Path = DATA_DIR) -> list[Path]:
    """
    Recursively find all video files in the data directory.

    Args:
        data_dir: Root directory to search

    Returns:
        List of paths to .avi files
    """
    video_files: list[Path] = []
    for ext in ("*.avi", "*.mp4"):
        video_files.extend(data_dir.rglob(ext))
    return sorted(set(video_files))


def discover_sleap_files(data_dir: Path = DATA_DIR) -> list[Path]:
    """
    Recursively find all SLEAP prediction files in the data directory.

    Args:
        data_dir: Root directory to search

    Returns:
        List of paths to SLEAP files (.slp, .h5.slp, .analysis.h5)
    """
    sleap_files = []

    for ext in ("*.slp", "*.h5.slp", "*.analysis.h5"):
        sleap_files.extend(data_dir.rglob(ext))

    return sorted(sleap_files)


def parse_video_filename(video_path: Path) -> Optional[tuple[str, str, str]]:
    """
    Parse animal_id, session, trial from video filename.

    Args:
        video_path: Path to video file

    Returns:
        Tuple of (animal_id, session, trial) or None if parsing fails
        Session/trial are formatted as "S01", "T01" etc.
    """
    name = video_path.name
    match = VIDEO_PATTERN.search(name)
    if match:
        animal_id = match.group(1)
        session = f"S{match.group(2).zfill(2)}"
        trial = f"T{match.group(3).zfill(2)}"
        return (animal_id, session, trial)

    ctrl = CONTROLLER_VIDEO_PATTERN.match(name)
    if ctrl:
        return (ctrl.group(1), ctrl.group(2).upper(), ctrl.group(3).upper())

    return None


def parse_sleap_filename(sleap_path: Path) -> Optional[tuple[str, str, str]]:
    """
    Parse animal_id, session, trial from SLEAP filename.

    Args:
        sleap_path: Path to SLEAP file

    Returns:
        Tuple of (animal_id, session, trial) or None if parsing fails
    """
    name = sleap_path.name
    match = SLEAP_PATTERN.search(name)
    if match:
        animal_id = match.group(1)
        session = f"S{match.group(2).zfill(2)}"
        trial = f"T{match.group(3).zfill(2)}"
        return (animal_id, session, trial)

    ctrl = CONTROLLER_SLEAP_PATTERN.match(name)
    if ctrl:
        return (ctrl.group(1), ctrl.group(2).upper(), ctrl.group(3).upper())

    return None


def extract_trials_from_h5(h5_path: Path) -> list[tuple[str, str, str]]:
    """
    Extract all trial paths from an input H5 file.

    The H5 structure is: <animal_id>/<session>/<trial>/[data, settings]

    Args:
        h5_path: Path to input H5 file

    Returns:
        List of (animal_id, session, trial) tuples
    """
    trials = []

    try:
        with h5py.File(h5_path, "r") as f:
            for animal_id in f.keys():
                animal_group = f[animal_id]
                if not isinstance(animal_group, h5py.Group):
                    continue

                for session in animal_group.keys():
                    session_group = animal_group[session]
                    if not isinstance(session_group, h5py.Group):
                        continue

                    for trial in session_group.keys():
                        trial_group = session_group[trial]
                        if isinstance(trial_group, h5py.Group):
                            # Verify it has data/settings structure
                            if "data" in trial_group or "settings" in trial_group:
                                trials.append((animal_id, session, trial))
    except Exception as e:
        print(f"Warning: Failed to read H5 file {h5_path}: {e}")

    return trials


def _resolved_exclude_set(paths: Optional[Sequence[Path]]) -> set[Path]:
    out: set[Path] = set()
    if not paths:
        return out
    for p in paths:
        try:
            out.add(Path(p).resolve())
        except OSError:
            continue
    return out


def _discover_controller_video_trials(
    result: DiscoveryResult,
    *,
    controller_db: Path,
) -> None:
    """
    Build trial manifests from videos under scanned dirs (controller acquisition layout).

    Used when no legacy input-H5 trials were found. ``input_h5_path`` is set to the
    results database path for manifest bookkeeping.
    """
    sleap_lookup: dict[tuple[str, str, str], Path] = {}
    for sleap_path in result.sleap_files:
        parsed = parse_sleap_filename(sleap_path)
        if not parsed:
            continue
        key = parsed
        existing = sleap_lookup.get(key)
        if existing is None or sleap_path.name.endswith(".h5.slp"):
            sleap_lookup[key] = sleap_path

    trial_dict: dict[tuple[str, str, str, str], TrialManifest] = {}
    for video_path in result.video_files:
        parsed = parse_video_filename(video_path)
        if not parsed:
            continue
        animal_id, session, trial = parsed
        phase = "habituation" if session.upper().startswith("H") else "experimental"
        key = (animal_id, phase, session, trial)
        if key in trial_dict:
            continue
        sleap_path = sleap_lookup.get((animal_id, session, trial))
        trial_dict[key] = TrialManifest(
            animal_id=animal_id,
            session=session,
            trial=trial,
            input_h5_path=controller_db,
            video_path=video_path,
            sleap_path=sleap_path,
            is_habituation=phase == "habituation",
        )

    result.trials = []
    result.n_matched_videos = 0
    result.n_matched_sleap = 0
    for manifest in trial_dict.values():
        result.trials.append(manifest)
        if manifest.video_path:
            result.n_matched_videos += 1
        if manifest.sleap_path:
            result.n_matched_sleap += 1


def discover_trials(
    data_dir: Union[Path, list[Path], None] = None,
    *,
    exclude_h5_paths: Optional[Sequence[Path]] = None,
    controller_results_h5: Optional[Path] = None,
) -> DiscoveryResult:
    """
    Discover all trials by scanning input H5 files and matching to videos/SLEAP files.

    This function:
    1. Finds all input H5 files and extracts trial structure
    2. Finds all video files and parses their filenames
    3. Finds all SLEAP prediction files
    4. Matches videos/SLEAP to trials from H5 files

    Args:
        data_dir: Root directory or list of root directories to search. If None, uses DATA_DIRS from config.
        exclude_h5_paths: HDF5 paths to omit from the input-H5 scan (e.g. target ``trials.h5``).
        controller_results_h5: When set and no legacy input-H5 trials match, build manifests
            from ``{animal}_{session}_{trial}.mp4`` videos in the scan roots.

    Returns:
        DiscoveryResult containing all discovered trials and file mappings
    """
    if data_dir is None:
        dirs = list(DATA_DIRS)
    elif isinstance(data_dir, Path):
        dirs = [data_dir]
    else:
        dirs = list(data_dir)

    exclude_resolved = _resolved_exclude_set(exclude_h5_paths)
    if controller_results_h5 is not None:
        exclude_resolved |= _resolved_exclude_set([controller_results_h5])

    result = DiscoveryResult()
    for d in dirs:
        if not d.exists():
            print(f"Warning: Data directory does not exist: {d}")
            continue
        result.input_h5_files.extend(
            discover_input_h5_files(d, exclude_resolved=exclude_resolved)
        )
        result.video_files.extend(discover_video_files(d))
        result.sleap_files.extend(discover_sleap_files(d))

    result.input_h5_files = sorted(set(result.input_h5_files))
    result.video_files = sorted(set(result.video_files))
    result.sleap_files = sorted(set(result.sleap_files))

    print(f"Scanning {len(dirs)} directory(ies) for files...")
    print(f"  Found {len(result.input_h5_files)} input H5 files")
    print(f"  Found {len(result.video_files)} video files")
    print(f"  Found {len(result.sleap_files)} SLEAP files")

    # Build phase-aware lookups so habituation manifests get files from habituation
    # folders and experimental from the rest (avoids mixing long hab videos into experimental).
    video_lookup_hab: dict[tuple[str, str, str], Path] = {}
    video_lookup_exp: dict[tuple[str, str, str], Path] = {}
    for video_path in result.video_files:
        parsed = parse_video_filename(video_path)
        if not parsed:
            continue
        if _path_looks_habituation(video_path):
            d = video_lookup_hab
        else:
            d = video_lookup_exp
        if parsed not in d or len(str(video_path)) > len(str(d[parsed])):
            d[parsed] = video_path

    sleap_lookup_hab: dict[tuple[str, str, str], Path] = {}
    sleap_lookup_exp: dict[tuple[str, str, str], Path] = {}
    for sleap_path in result.sleap_files:
        parsed = parse_sleap_filename(sleap_path)
        if not parsed:
            continue
        if _path_looks_habituation(sleap_path):
            d = sleap_lookup_hab
        else:
            d = sleap_lookup_exp
        existing = d.get(parsed)
        if existing is None:
            d[parsed] = sleap_path
        elif sleap_path.name.endswith(".h5.slp") and not existing.name.endswith(".h5.slp"):
            d[parsed] = sleap_path

    # Extract trials from each H5 file and create manifests
    # Use a dict keyed by (animal_id, phase, session, trial) to deduplicate true duplicates
    # (same phase from different files), while keeping both habituation and experimental trials
    trial_dict: dict[tuple[str, str, str, str], TrialManifest] = {}

    for h5_path in result.input_h5_files:
        is_hab, range_start, range_end = _parse_session_range(h5_path)
        researcher = _infer_researcher_from_path(h5_path)
        cohort = _infer_cohort_from_path(h5_path)

        trials_in_file = extract_trials_from_h5(h5_path)

        for animal_id, session, trial in trials_in_file:
            # Filter: only include trials whose session falls within the file's stated range
            if not _session_in_range(session, range_start, range_end):
                continue

            # --- Trial number filter: exclude trials > MAX_TRIAL_NUM ---
            trial_match = re.search(r"\d+", trial)
            if trial_match and int(trial_match.group()) > MAX_TRIAL_NUM:
                continue

            # --- Session renumbering (e.g., Cohort 5: S02->S01) ---
            # Must happen BEFORE the session number filter so that the filter
            # applies to the renumbered session (e.g., original S06 -> S05).
            session_match = re.search(r"\d+", session)
            original_session = None
            offset = SESSION_RENUMBER.get(animal_id, 0)
            if offset != 0 and session_match:
                orig_num = int(session_match.group())
                new_num = orig_num + offset
                if new_num < 1:
                    continue  # Renumbering would produce invalid session
                original_session = session
                session = f"S{new_num:02d}"

            # --- Session number filter: exclude sessions > MAX_SESSION_NUM ---
            # Applied to the (possibly renumbered) session number.
            renumbered_match = re.search(r"\d+", session)
            if renumbered_match and int(renumbered_match.group()) > MAX_SESSION_NUM:
                continue

            # Normalize habituation session keys for DB storage (hS##), while
            # preserving the source key for H5/video/SLEAP lookups.
            normalized_session, hab_original_session = _normalize_habituation_session(
                session=session,
                is_habituation=is_hab,
            )
            if hab_original_session and original_session is None:
                original_session = hab_original_session
            session = normalized_session

            phase = "habituation" if is_hab else "experimental"
            key = (animal_id, phase, session, trial)

            # Look up matching video and SLEAP from the same phase (habituation path vs rest)
            lookup_session = original_session if original_session else session
            video_key = (animal_id, lookup_session, trial)
            if is_hab:
                video_path = video_lookup_hab.get(video_key)
                sleap_path = sleap_lookup_hab.get(video_key)
            else:
                video_path = video_lookup_exp.get(video_key)
                sleap_path = sleap_lookup_exp.get(video_key)

            manifest = TrialManifest(
                animal_id=animal_id,
                session=session,
                trial=trial,
                input_h5_path=h5_path,
                video_path=video_path,
                sleap_path=sleap_path,
                is_habituation=is_hab,
                cohort=cohort,
                researcher=researcher,
                original_session=original_session,
            )

            # Only add if not already present (true duplicate from same phase)
            if key not in trial_dict:
                trial_dict[key] = manifest

    # Convert dict to list
    for manifest in trial_dict.values():
        result.trials.append(manifest)
        if manifest.video_path:
            result.n_matched_videos += 1
        if manifest.sleap_path:
            result.n_matched_sleap += 1

    if not result.trials and controller_results_h5 is not None:
        print(
            "  No legacy input-H5 trials; using controller video filenames "
            f"with results DB {controller_results_h5}"
        )
        _discover_controller_video_trials(result, controller_db=Path(controller_results_h5))

    # Count unmatched videos (keys in either phase lookup that no manifest used)
    all_video_keys = set(video_lookup_hab.keys()) | set(video_lookup_exp.keys())
    matched_video_keys = {
        (t.animal_id, t.original_session if t.original_session else t.session, t.trial)
        for t in result.trials
        if t.video_path is not None
    }
    result.n_unmatched_videos = len(all_video_keys) - len(matched_video_keys)

    print(f"  Created {len(result.trials)} trial manifests")
    print(f"  Matched {result.n_matched_videos} videos, {result.n_matched_sleap} SLEAP files")

    enrich_manifests_has_tracking_pose(
        result.trials,
        db_path=Path(controller_results_h5) if controller_results_h5 is not None else None,
    )

    return result


def get_unique_animals(result: DiscoveryResult) -> list[str]:
    """Get list of unique animal IDs from discovery result."""
    return sorted(set(t.animal_id for t in result.trials))


def get_trials_for_animal(
    result: DiscoveryResult, animal_id: str, phase: Optional[str] = None
) -> list[TrialManifest]:
    """
    Get all trials for a specific animal.

    Args:
        result: DiscoveryResult from discover_trials()
        animal_id: Animal ID to filter by
        phase: Optional phase filter ("habituation" or "experimental")

    Returns:
        List of TrialManifest objects for the animal
    """
    trials = [t for t in result.trials if t.animal_id == animal_id]

    if phase:
        trials = [t for t in trials if t.phase == phase]

    # Sort by session then trial
    return sorted(trials, key=lambda t: (t.session, t.trial))


@dataclass
class TreatmentLabel:
    """Treatment label for an animal or cohort."""

    type: str  # "cohort" or "animal_id"
    key: str  # cohort name (e.g., "cohort2") or animal ID (e.g., "2314")
    strain: str
    experiment: str
    researcher: str
    sex: str = "M"  # M or F
    tx: str = ""  # treatment group e.g. SF, noSF
    drug: str = ""  # drug condition e.g. vehicle, compound name
    notes: str = ""


_TREATMENT_LABELS_CACHE: dict[Path, tuple[float, dict[str, "TreatmentLabel"]]] = {}


def load_treatment_labels(labels_path: Optional[Path] = None) -> dict[str, TreatmentLabel]:
    """
    Load treatment labels from CSV file.

    Args:
        labels_path: Path to treatment_labels.csv. If None, uses default in inputs/.

    Returns:
        Dictionary mapping key (cohort name or animal_id) to TreatmentLabel
    """
    import csv

    if labels_path is None:
        # Default location relative to this module
        labels_path = Path(__file__).parent.parent.parent.parent / "inputs" / "treatment_labels.csv"

    labels: dict[str, TreatmentLabel] = {}

    labels_path = Path(labels_path).resolve()

    if not labels_path.exists():
        logger.warning("Treatment labels file not found: %s", labels_path)
        return labels

    mtime = labels_path.stat().st_mtime
    cached = _TREATMENT_LABELS_CACHE.get(labels_path)
    if cached is not None and cached[0] == mtime:
        return dict(cached[1])

    with open(labels_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = TreatmentLabel(
                type=row["type"],
                key=row["key"],
                strain=row["strain"],
                experiment=row["experiment"],
                researcher=row["researcher"],
                sex=row.get("sex", "M"),
                tx=row.get("tx", ""),
                drug=row.get("drug", ""),
                notes=row.get("notes", ""),
            )
            labels[row["key"]] = label

    logger.debug("Loaded %d treatment labels from %s", len(labels), labels_path)
    _TREATMENT_LABELS_CACHE[labels_path] = (mtime, dict(labels))
    return labels


TREATMENT_LABELS_HEADER = [
    "type",
    "key",
    "strain",
    "experiment",
    "researcher",
    "sex",
    "tx",
    "drug",
    "notes",
]


def update_treatment_labels_from_discovery(
    result: DiscoveryResult,
    labels_path: Optional[Path] = None,
) -> None:
    """
    Update treatment_labels.csv from discovery: add rows for any animal_id or cohort
    that appears in discovery but not yet in the CSV. Existing rows are preserved
    (human-filled values are not overwritten). New rows get blank strain/experiment/sex/tx/notes.

    Args:
        result: DiscoveryResult from discover_trials()
        labels_path: Path to treatment_labels.csv. If None, uses default in inputs/.
    """
    import csv

    if labels_path is None:
        labels_path = Path(__file__).parent.parent.parent / "inputs" / "treatment_labels.csv"
    labels_path = Path(labels_path)
    labels_path.parent.mkdir(parents=True, exist_ok=True)

    existing_rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()  # (type, key)
    if labels_path.exists():
        with open(labels_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                r = {k: (row.get(k) or "") for k in TREATMENT_LABELS_HEADER}
                existing_rows.append(r)
                t = (r.get("type") or "").strip()
                k = (r.get("key") or "").strip()
                if t and k:
                    seen.add((t, k))

    # Collect unique animal_ids from discovery (no cohort rows)
    animal_ids = sorted(set(t.animal_id for t in result.trials))

    new_rows: list[dict[str, str]] = []
    for aid in animal_ids:
        if ("animal_id", aid) not in seen:
            new_rows.append(
                {
                    "type": "animal_id",
                    "key": aid,
                    "strain": "",
                    "experiment": "",
                    "researcher": "",
                    "sex": "",
                    "tx": "",
                    "drug": "",
                    "notes": "",
                }
            )
            seen.add(("animal_id", aid))

    with open(labels_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TREATMENT_LABELS_HEADER)
        writer.writeheader()
        for row in existing_rows:
            writer.writerow({k: row.get(k, "") for k in TREATMENT_LABELS_HEADER})
        writer.writerows(new_rows)

    if new_rows:
        print(
            f"Updated {labels_path}: added {len(new_rows)} new row(s) (fill in strain/experiment/sex/tx as needed)."
        )
    else:
        print(f"Treatment labels already up to date: {labels_path}")


def _infer_experiment_from_path(file_path: Path) -> Optional[str]:
    """
    Infer experiment type from file path.

    Returns:
        "VASTcontKL" for Kevan Lim data, None for Nick's data (use cohort lookup)
    """
    path_str = str(file_path).lower()

    if "vastcontkl" in path_str or "kevan" in path_str:
        return "VASTcontKL"

    return None


def apply_treatment_labels(
    result: DiscoveryResult,
    labels: dict[str, TreatmentLabel],
) -> None:
    """
    Apply treatment labels to all trials in a discovery result.

    Modifies trials in-place to set strain, experiment, and sex fields.

    Args:
        result: DiscoveryResult with trials
        labels: Dictionary from load_treatment_labels()
    """
    for trial in result.trials:
        # Direct animal_id lookup
        if trial.animal_id in labels:
            label = labels[trial.animal_id]
            trial.strain = label.strain
            trial.experiment = label.experiment
            trial.sex = label.sex
            trial.tx = label.tx or None
            trial.drug = label.drug or None
            trial.researcher = label.researcher or None
            continue

        # Infer experiment from path as fallback
        trial.experiment = _infer_experiment_from_path(trial.input_h5_path)


def check_duplicates(result: DiscoveryResult) -> list[tuple[str, list[TrialManifest]]]:
    """
    Check for duplicate trial keys in discovery result.

    A duplicate is when multiple trials have the same (animal_id, phase, session, trial) tuple.
    Trials with the same session number but different phases (habituation vs experimental)
    are NOT considered duplicates.

    Args:
        result: DiscoveryResult from discover_trials()

    Returns:
        List of (trial_key, [trials...]) tuples for any duplicates found.
        Empty list if no duplicates.
    """
    from collections import defaultdict

    by_key: dict[str, list[TrialManifest]] = defaultdict(list)

    for trial in result.trials:
        # Include phase in the key to distinguish habituation from experimental
        key = f"{trial.animal_id}/{trial.phase}/{trial.session}/{trial.trial}"
        by_key[key].append(trial)

    duplicates = [(key, trials) for key, trials in by_key.items() if len(trials) > 1]

    return duplicates


def is_invalid_key_combo(trial: TrialManifest) -> tuple[bool, str]:
    """
    Check if trial has an invalid key combo.

    Invalid key combos are:
    - Animal IDs 0-4 (placeholder/mislabeled)
    - Session number < 1 (e.g., S00)

    Args:
        trial: TrialManifest to check

    Returns:
        (is_invalid, reason_string) tuple.
        reason_string is empty if valid, otherwise describes the issue.
    """
    # Check for placeholder animal IDs
    if trial.animal_id in ("0", "1", "2", "3", "4"):
        return True, "invalid_id_0_4"

    # Check for invalid session number
    session_match = re.search(r"\d+", trial.session)
    if session_match:
        session_num = int(session_match.group())
        if session_num < 1:
            return True, "invalid_session_lt_1"

    return False, ""


def find_orphaned_videos(result: DiscoveryResult) -> list[tuple[Path, tuple[str, str, str]]]:
    """
    Find video files that don't match any H5 trial.

    These are videos where we can parse the filename but no corresponding
    trial exists in the H5 files.

    Args:
        result: DiscoveryResult from discover_trials()

    Returns:
        List of (video_path, (animal_id, session, trial)) tuples for orphaned videos
    """
    # Build set of all trial keys from H5 files.
    # Include BOTH the renumbered session AND the original session (if different)
    # so that videos with original-numbered filenames are recognized as matched.
    h5_trial_keys: set[tuple[str, str, str]] = set()
    for t in result.trials:
        h5_trial_keys.add((t.animal_id, t.session, t.trial))
        if t.original_session:
            h5_trial_keys.add((t.animal_id, t.original_session, t.trial))

    orphaned = []
    for video_path in result.video_files:
        parsed = parse_video_filename(video_path)
        if parsed and parsed not in h5_trial_keys:
            orphaned.append((video_path, parsed))

    return orphaned


def find_trials_missing_videos(result: DiscoveryResult) -> list[TrialManifest]:
    """
    Find trials that have valid key combos but no associated video.

    Args:
        result: DiscoveryResult from discover_trials()

    Returns:
        List of TrialManifest objects without video associations
    """
    missing = []
    for trial in result.trials:
        is_invalid, _ = is_invalid_key_combo(trial)
        if not is_invalid and trial.video_path is None:
            missing.append(trial)
    return missing


def find_potential_duplicates(
    trials: list[TrialManifest],
    threshold_minutes: int = 2,
) -> list[tuple[TrialManifest, TrialManifest, float]]:
    """
    Find pairs of trials with different key combos but similar timestamps.

    These may indicate duplicate data or mislabeled trials that need human review.

    Args:
        trials: List of TrialManifest objects with timestamps populated
        threshold_minutes: Maximum time difference to consider as potential duplicate

    Returns:
        List of (trial1, trial2, time_delta_seconds) tuples for potential duplicates
    """
    from datetime import timedelta

    # Filter to trials with timestamps
    with_timestamps = [t for t in trials if t.timestamp is not None]

    # Sort by timestamp for efficient comparison
    with_timestamps.sort(key=lambda t: t.timestamp)

    duplicates = []
    threshold = timedelta(minutes=threshold_minutes)

    for i, t1 in enumerate(with_timestamps):
        # Only compare with subsequent trials (avoid duplicate pairs)
        for t2 in with_timestamps[i + 1 :]:
            delta = t2.timestamp - t1.timestamp

            # Stop checking if we're past the threshold (list is sorted)
            if delta > threshold:
                break

            # Skip if same key combo (not a duplicate issue)
            if (t1.animal_id, t1.session, t1.trial) == (t2.animal_id, t2.session, t2.trial):
                continue

            # Skip if same phase and session (habituation vs experimental is expected)
            if t1.phase == t2.phase and t1.session == t2.session and t1.trial == t2.trial:
                # Different animal IDs but same timestamp = potential duplicate
                duplicates.append((t1, t2, delta.total_seconds()))

    return duplicates


def save_manifest_csv(result: DiscoveryResult, output_path: Path) -> None:
    """
    Save discovery result to a CSV manifest file.

    Column order is :data:`MANIFEST_CSV_FIELDNAMES` (labels, QA counts, paths).

    Args:
        result: DiscoveryResult from discover_trials()
        output_path: Path for output CSV file
    """
    import csv

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(list(MANIFEST_CSV_FIELDNAMES))
        for t in sorted(result.trials, key=lambda x: (x.animal_id, x.session, x.trial)):
            writer.writerow(trial_manifest_csv_row_values(t))

    print(f"Saved manifest to {output_path}")


def load_manifest_csv(
    manifest_path: Path,
) -> list[TrialManifest]:
    """
    Load trial manifests from a CSV file (e.g. inputs/trial_manifest.csv).

    Expects headers compatible with :data:`MANIFEST_CSV_FIELDNAMES`; older manifests
    without ``sex`` / ``tx`` / ``cohort`` columns still load (those fields stay empty).

    Returns:
        List of TrialManifest (video_path/sleap_path as Path or None).
    """
    import csv
    from datetime import datetime

    def _cell(row: dict[str, str], key: str) -> Optional[str]:
        v = (row.get(key) or "").strip()
        return v if v else None

    manifests = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            video_path = row.get("video_path", "").strip()
            sleap_path = row.get("sleap_path", "").strip()
            ts = row.get("timestamp", "").strip()
            try:
                timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None
            except (ValueError, AttributeError):
                timestamp = None
            h5_frames = row.get("h5_n_frames", "").strip()
            vid_frames = row.get("video_n_frames", "").strip()
            manifests.append(
                TrialManifest(
                    animal_id=row["animal_id"],
                    session=(
                        _normalize_habituation_session(
                            row["session"],
                            (row.get("phase", "") == "habituation"),
                        )[0]
                    ),
                    trial=row["trial"],
                    input_h5_path=Path(row.get("input_h5_path", "")),
                    video_path=Path(video_path) if video_path else None,
                    sleap_path=Path(sleap_path) if sleap_path else None,
                    is_habituation=(row.get("phase", "") == "habituation"),
                    original_session=row.get("original_session") or None,
                    timestamp=timestamp,
                    h5_n_frames=int(h5_frames) if h5_frames.isdigit() else None,
                    video_n_frames=int(vid_frames) if vid_frames.isdigit() else None,
                    cohort=_cell(row, "cohort"),
                    researcher=_cell(row, "researcher"),
                    strain=_cell(row, "strain"),
                    experiment=_cell(row, "experiment"),
                    sex=_cell(row, "sex"),
                    tx=_cell(row, "tx"),
                    drug=_cell(row, "drug"),
                    inferred_id=_cell(row, "inferred_id"),
                    kpms_recording_key=_cell(row, "kpms_recording_key"),
                    has_tracking_pose=_parse_manifest_bool(row.get("has_tracking_pose")),
                    exit_number=_parse_manifest_int(row.get("exit_number")),
                )
            )
    return manifests


if __name__ == "__main__":
    # Test discovery
    result = discover_trials()
    print(f"\n{result}")
    print(f"\nUnique animals: {len(get_unique_animals(result))}")

    # Show first few trials
    for trial in result.trials[:5]:
        print(
            f"  {trial.trial_key}: video={trial.video_path is not None}, sleap={trial.sleap_path is not None}"
        )
