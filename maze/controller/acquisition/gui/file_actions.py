from __future__ import annotations

import csv
import time
import webbrowser
from pathlib import Path
from typing import Callable, Literal, Optional, Tuple, Union

from ..h5_writer import open_db
from ..h5web_server import get_h5web_static_dir, run_server

try:
    from PySide6.QtWidgets import QMessageBox, QWidget

    HAS_QT = True
except ImportError:
    HAS_QT = False
    QWidget = object  # type: ignore[assignment,misc]


def export_trials_csv(db_path: Path, output_csv: Path) -> None:
    """Export trial list and paths to CSV for the merged ORM H5 layout."""
    import h5py

    rows: list[dict[str, object]] = []
    with h5py.File(db_path, "r") as h5:
        for animal_id in h5.keys():
            if animal_id == "metadata":
                continue
            g_animal = h5[animal_id]
            if not hasattr(g_animal, "keys"):
                continue
            for level1 in g_animal.keys():
                g1 = g_animal[level1]
                if not hasattr(g1, "keys"):
                    continue
                if hasattr(g1, "attrs") and "run_mode" in g1.attrs:
                    run_mode = str(g1.attrs.get("run_mode", ""))
                    for trial in g1.keys():
                        g_trial = g1[trial]
                        if hasattr(g_trial, "attrs"):
                            attrs = g_trial.attrs
                            rows.append(
                                {
                                    "animal_id": animal_id,
                                    "session_id": level1,
                                    "trial": trial,
                                    "run_mode": run_mode,
                                    "video_path": str(attrs.get("video_path", "")),
                                    "sleap_path": str(attrs.get("sleap_path", "")),
                                }
                            )
                else:
                    for session_id in g1.keys():
                        g_session = g1[session_id]
                        if not hasattr(g_session, "keys"):
                            continue
                        run_mode = str(g_session.attrs.get("run_mode", ""))
                        for trial in g_session.keys():
                            g_trial = g_session[trial]
                            if hasattr(g_trial, "attrs"):
                                attrs = g_trial.attrs
                                rows.append(
                                    {
                                        "animal_id": animal_id,
                                        "session_id": session_id,
                                        "trial": trial,
                                        "run_mode": run_mode,
                                        "video_path": str(attrs.get("video_path", "")),
                                        "sleap_path": str(attrs.get("sleap_path", "")),
                                    }
                                )
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["animal_id", "session_id", "trial", "run_mode", "video_path", "sleap_path"],
        )
        writer.writeheader()
        writer.writerows(rows)


def launch_h5web_for_path(h5_path: Path, status_cb: Callable[[str], None]) -> None:
    """Start the local h5web server and open the browser for one H5 file."""
    if not h5_path.exists():
        status_cb(f"File not found: {h5_path}")
        return
    static_dir = get_h5web_static_dir()
    if static_dir is None:
        status_cb("h5web viewer not found (run: cd web/h5web && npm run build)")
        return
    try:
        port, _ = run_server(h5_path, static_dir)
        url = f"http://127.0.0.1:{port}/?file={h5_path.name}"
        time.sleep(0.4)
        webbrowser.open(url)
        status_cb("Launched h5web")
    except Exception as exc:
        status_cb(f"Could not launch h5web: {exc}")


def next_keep_both_suffix(
    db_path: Path,
    output_dir: Path,
    animal_id: str,
    session_id: str,
    trial: str,
) -> str:
    """Return the next available Keep both suffix shared by H5 and video outputs."""
    n = 2
    while True:
        suffix = f"({n})"
        h5_key = f"/{animal_id}/{session_id}/{trial}{suffix}"
        video_path = output_dir / f"{animal_id}_{session_id}_{trial}{suffix}.mp4"
        h5_exists = False
        if db_path.exists():
            try:
                with open_db(db_path, "r") as h5:
                    h5_exists = h5_key in h5
            except Exception:
                pass
        if not h5_exists and not video_path.exists():
            return suffix
        n += 1


def ask_trial_overwrite_merged(
    parent: QWidget,
    h5_key: Optional[str],
    video_path: Optional[Path],
    new_h5_key_with_suffix: Optional[str],
    new_video_path_with_suffix: Optional[Path],
    keep_both_suffix: str = "(2)",
) -> Union[Literal["overwrite"], Literal["discard"], Tuple[Literal["keep_both"], str]]:
    """Prompt once when either the H5 group, video file, or both already exist."""
    if not HAS_QT:
        return "discard"
    has_h5 = h5_key is not None
    has_video = video_path is not None
    only_one = has_h5 != has_video

    parts = []
    if has_h5:
        parts.append(f"Trial data (H5) already exists at:\n  {h5_key}")
    if has_video:
        parts.append(f"Video file already exists at:\n  {video_path}")
    parts.append("")
    if only_one:
        parts.append("Note: Only one of trial data or video file already exists. This is unusual.")
        parts.append("")
    parts.append("If you choose Keep both, the new trial will use:")
    if new_h5_key_with_suffix:
        parts.append(f"  H5 group: {new_h5_key_with_suffix}")
    if new_video_path_with_suffix:
        parts.append(f"  Video file: {new_video_path_with_suffix}")
    parts.append("")
    parts.append("Overwrite existing, discard this trial, or keep both?")

    box = QMessageBox(parent)
    box.setWindowTitle("Trial / video already exists")
    box.setText("\n".join(parts))
    overwrite_btn = box.addButton("Overwrite", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Discard", QMessageBox.ButtonRole.RejectRole)
    keep_btn = box.addButton("Keep both", QMessageBox.ButtonRole.ActionRole)
    box.exec()
    clicked = box.clickedButton()
    if clicked == overwrite_btn:
        return "overwrite"
    if clicked == keep_btn:
        return ("keep_both", keep_both_suffix)
    return "discard"
