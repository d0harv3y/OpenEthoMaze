"""Goal A: Sturman OFT leave-one-video-out rearing MLP (all annotators)."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from of_rear_classifier.bout import avgbool, bout_count, bout_time_s
from of_rear_classifier.labels import intervals_to_frame_labels, load_sturman_oft_labels
from of_rear_classifier.sturman_dlc import (
    DEFAULT_CUT_END,
    DEFAULT_CUT_START,
    DEFAULT_FPS,
    DEFAULT_LIKELIHOOD_CUTOFF,
    load_sturman_video_features,
)
from of_rear_classifier.train_torch import features_to_window_xy, predict_classes, train_mlp
from of_rear_classifier.window import DEFAULT_INTEGRATION_WINDOW

BEH_TYPES = ("Supported", "Unsupported", "Grooming")
EXPERIMENTERS = ("Jin", "Furkan", "Oliver")


@dataclass
class FoldMetrics:
    experimenter: str
    video_id: str
    dlc_file: str
    n_test: int
    frame_acc: float
    supported_time_pred_s: float
    supported_time_exp_s: float
    unsupported_time_pred_s: float
    unsupported_time_exp_s: float
    grooming_time_pred_s: float
    grooming_time_exp_s: float
    supported_count_pred: int
    supported_count_exp: int
    unsupported_count_pred: int
    unsupported_count_exp: int
    train_acc: float
    train_n: int
    seconds: float


def _id_to_dlc(labels: pd.DataFrame) -> dict[str, str]:
    return labels.groupby("ID")["DLCFile"].first().astype(str).to_dict()


def run_sturman_loocv(
    *,
    oft_root: Path,
    out_dir: Path,
    experimenters: tuple[str, ...] = EXPERIMENTERS,
    fps: float = DEFAULT_FPS,
    integration_window: int = DEFAULT_INTEGRATION_WINDOW,
    epochs: int = 10,
    batch_size: int = 32,
    likelihood_cutoff: float = DEFAULT_LIKELIHOOD_CUTOFF,
    cut_start: int = DEFAULT_CUT_START,
    cut_end: int = DEFAULT_CUT_END,
    avgbool_window: int = 10,
    seed: int = 0,
    device: str | None = None,
) -> pd.DataFrame:
    oft_root = Path(oft_root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    labels_path = oft_root / "Labels" / "AllLabDataOFT_final.csv"
    csv_dir = oft_root / "Output_DLC"
    labels = load_sturman_oft_labels(labels_path)
    id_dlc = _id_to_dlc(labels)
    video_ids = sorted(id_dlc.keys())

    # Cache z-scored features per video (shared across annotators)
    feat_cache: dict[str, np.ndarray] = {}
    meta_cache: dict[str, dict] = {}
    t_cache0 = time.perf_counter()
    print(f"loading {len(video_ids)} Sturman DLC CSVs…", flush=True)
    for i, vid in enumerate(video_ids, start=1):
        dlc_name = id_dlc[vid]
        path = csv_dir / dlc_name
        if not path.is_file():
            raise FileNotFoundError(path)
        feat_z, meta = load_sturman_video_features(
            path,
            likelihood_cutoff=likelihood_cutoff,
            cut_start=cut_start,
            cut_end=cut_end,
        )
        feat_cache[vid] = feat_z
        meta_cache[vid] = meta
        print(f"  [{i}/{len(video_ids)}] {vid} T={feat_z.shape[0]} file={dlc_name}", flush=True)
    print(f"feature cache done in {time.perf_counter() - t_cache0:.1f}s", flush=True)

    # Precompute windowed (X, y) per experimenter × video
    win_cache: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}
    t_win0 = time.perf_counter()
    print("windowing labeled streams…", flush=True)
    for exp in experimenters:
        for vid in video_ids:
            feat = feat_cache[vid]
            lab = labels[(labels["Experimenter"] == exp) & (labels["ID"] == vid)]
            y_frames = _labels_on_cut(
                lab,
                n_frames=feat.shape[0],
                fps=fps,
                cut_start=cut_start,
                keep_types=BEH_TYPES,
            )
            win_cache[(exp, vid)] = features_to_window_xy(
                feat, y_frames, integration_window=integration_window
            )
    print(f"window cache done in {time.perf_counter() - t_win0:.1f}s", flush=True)

    rows: list[FoldMetrics] = []
    n_folds = len(experimenters) * len(video_ids)
    fold_i = 0
    t0 = time.perf_counter()

    for exp in experimenters:
        for test_id in video_ids:
            fold_i += 1
            fold_t0 = time.perf_counter()
            train_ids = [v for v in video_ids if v != test_id]

            x_train = np.concatenate([win_cache[(exp, vid)][0] for vid in train_ids], axis=0)
            y_train = np.concatenate([win_cache[(exp, vid)][1] for vid in train_ids], axis=0)

            result = train_mlp(
                x_train,
                y_train,
                epochs=epochs,
                batch_size=batch_size,
                seed=seed + fold_i,
                device=device,
            )

            x_te, y_te = win_cache[(exp, test_id)]
            pred = predict_classes(result.model, x_te, device=device)
            frame_acc = float(np.mean(pred == y_te))

            metrics = _bout_metrics(pred, y_te, fps=fps, avgbool_window=avgbool_window)
            fold = FoldMetrics(
                experimenter=exp,
                video_id=test_id,
                dlc_file=id_dlc[test_id],
                n_test=int(len(y_te)),
                frame_acc=frame_acc,
                train_acc=result.train_acc,
                train_n=result.n_train,
                seconds=time.perf_counter() - fold_t0,
                **metrics,
            )
            rows.append(fold)
            elapsed = time.perf_counter() - t0
            rate = fold_i / elapsed
            eta = (n_folds - fold_i) / rate if rate > 0 else float("nan")
            print(
                f"[{fold_i}/{n_folds}] {exp} holdout={test_id} "
                f"acc={frame_acc:.3f} train_acc={result.train_acc:.3f} "
                f"fold={fold.seconds:.1f}s eta={eta:.0f}s",
                flush=True,
            )

    df = pd.DataFrame([asdict(r) for r in rows])
    folds_path = out_dir / "fold_metrics.csv"
    df.to_csv(folds_path, index=False)

    summary = _summarize(df)
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print(f"wrote {folds_path}", flush=True)
    print(f"wrote {summary_path}", flush=True)
    return df


def _labels_on_cut(
    lab: pd.DataFrame,
    *,
    n_frames: int,
    fps: float,
    cut_start: int,
    keep_types: tuple[str, ...],
) -> np.ndarray:
    """Map absolute-second intervals onto the cut feature timeline."""
    if lab.empty:
        return intervals_to_frame_labels(lab, n_frames=n_frames, fps=fps, keep_types=keep_types)
    shifted = lab.copy()
    offset_s = cut_start / fps
    shifted["from"] = shifted["from"].astype(float) - offset_s
    shifted["to"] = shifted["to"].astype(float) - offset_s
    return intervals_to_frame_labels(shifted, n_frames=n_frames, fps=fps, keep_types=keep_types)


def _bout_metrics(
    pred: np.ndarray,
    y_true: np.ndarray,
    *,
    fps: float,
    avgbool_window: int,
) -> dict:
    out: dict = {}
    for name, key in (
        ("Supported", "supported"),
        ("Unsupported", "unsupported"),
        ("Grooming", "grooming"),
    ):
        p_s = avgbool(pred == name, avgbool_window)
        e_s = avgbool(y_true == name, avgbool_window)
        out[f"{key}_time_pred_s"] = bout_time_s(p_s, fps)
        out[f"{key}_time_exp_s"] = bout_time_s(e_s, fps)
        if name != "Grooming":
            out[f"{key}_count_pred"] = bout_count(p_s)
            out[f"{key}_count_exp"] = bout_count(e_s)
    return out


def _summarize(df: pd.DataFrame) -> dict:
    summary: dict = {
        "n_folds": int(len(df)),
        "mean_frame_acc": float(df["frame_acc"].mean()),
        "by_experimenter": {},
        "correlations": {},
    }
    for exp, g in df.groupby("experimenter"):
        summary["by_experimenter"][str(exp)] = {
            "mean_frame_acc": float(g["frame_acc"].mean()),
            "n_folds": int(len(g)),
            "supported_time_spearman": _spearman(g["supported_time_pred_s"], g["supported_time_exp_s"]),
            "unsupported_time_spearman": _spearman(g["unsupported_time_pred_s"], g["unsupported_time_exp_s"]),
            "supported_count_spearman": _spearman(g["supported_count_pred"], g["supported_count_exp"]),
            "unsupported_count_spearman": _spearman(g["unsupported_count_pred"], g["unsupported_count_exp"]),
        }
    summary["correlations"]["supported_time_spearman_all"] = _spearman(
        df["supported_time_pred_s"], df["supported_time_exp_s"]
    )
    summary["correlations"]["unsupported_time_spearman_all"] = _spearman(
        df["unsupported_time_pred_s"], df["unsupported_time_exp_s"]
    )
    return summary


def _spearman(a, b) -> float | None:
    from scipy.stats import spearmanr

    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if len(a) < 3 or np.std(a) == 0 or np.std(b) == 0:
        return None
    r, _ = spearmanr(a, b)
    return float(r) if np.isfinite(r) else None
