from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

try:
    from PySide6.QtCore import QThread, Signal

    HAS_QT = True
except ImportError:
    HAS_QT = False


if HAS_QT:

    class AnalysisWorker(QThread):
        """Run the offline pipeline for one recorded trial in the background."""

        finished = Signal(bool, str)

        def __init__(
            self,
            db_path: Path,
            animal_id: str,
            session_id: str,
            trial: str,
            video_path: Optional[Path],
            run_phase: str,
            analysis_profile: Optional[tuple[Any, Any]] = None,
        ) -> None:
            super().__init__()
            self._db_path = db_path
            self._animal_id = animal_id
            self._session_id = session_id
            self._trial = trial
            self._video_path = video_path
            self._run_phase = run_phase
            self._analysis_profile = analysis_profile

        def run(self) -> None:
            from ..post_trial_analysis import run_analysis_for_trial

            success, message = run_analysis_for_trial(
                db_path=self._db_path,
                animal_id=self._animal_id,
                session_id=self._session_id,
                trial=self._trial,
                video_path=self._video_path,
                run_phase=self._run_phase,
                analysis_profile=self._analysis_profile,
            )
            self.finished.emit(success, message)

else:
    AnalysisWorker = None  # type: ignore[misc, assignment]
