"""Floor quadrilateral from the wall-floor creases on a top-view open-field frame.

The floor is a diamond. Opposite creases are nearly parallel, so the seed is four
Hough lines: two orientations about 90 degrees apart, and on each orientation the
line closest to the image center. Both lines of a pair are then locked to that
pair's angle, which makes a parallelogram. The mask moves outward by one shared
shift (the median dark-crease trough), so the corner-to-corner ruler stays the
seed diagonal.

Tuned for the 640×480 cohort where the image center lies on the floor and the
floor apothem is about 110–150 px. A fit that misses those bounds is returned
and then flagged for review; it is not silently replaced by a shared polygon.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# Dark-crease fits are larger than the inset Hough seed (~63k px). The upper
# bound still rejects a quadrilateral that has walked onto the outer box.
AREA_MIN_PX = 55_000.0
AREA_MAX_PX = 90_000.0
# Longest edge in the pose's floor plane may be at most 3% longer than the shortest.
SIDE_MAX_MIN_RATIO = 1.03
# Seed diagonal (corner to corner) may sit at most 5% from the cohort median.
CORNER_REL_TOL = 0.05
POSE_BIN_PX = 15.0
POSE_MIN_VIDEOS = 4


@dataclass(frozen=True)
class FloorQuadParams:
    canny_low: int = 20
    canny_high: int = 75
    edge_radius_min_px: float = 90.0
    edge_radius_max_px: float = 260.0
    offset_min_px: float = 90.0
    offset_max_px: float = 175.0
    hough_threshold: int = 35
    orientation_bin_deg: float = 2.0
    mode_window_deg: float = 10.0
    member_window_deg: float = 5.0
    min_mode_separation_deg: float = 80.0


@dataclass(frozen=True)
class FloorQuad:
    """Cyclic vertices in image pixels, angle-sorted around their centroid.

    ``seed_diagonal_px`` is the corner-to-corner ruler: the mean of the two
    diagonals after the angle lock and before the shared outward shift.
    ``outward_px`` is that shift, the median dark-crease trough.
    """

    vertices_xy: np.ndarray
    area_px: float
    seed_diagonal_px: float
    outward_px: float


def _ang_dist(a: float, b: float) -> float:
    d = abs(a - b) % np.pi
    return float(min(d, np.pi - d))


def _image_center(gray: np.ndarray) -> tuple[float, float]:
    height, width = gray.shape[:2]
    return (width - 1) / 2.0, (height - 1) / 2.0


# One wall on Test 96 / Test 135 is nearly as bright as the floor, so the default
# Canny misses that crease. The faint pass is used only to fill a missing side,
# and only a line whose distance from center matches its partner is kept. The
# far side of that bright wall sits ~40 px farther out and is rejected.
_FAINT_CANNY_LOW = 12
_FAINT_CANNY_HIGH = 40
_FAINT_HOUGH_THRESHOLD = 18
_PARTNER_OFFSET_TOL_PX = 32.0


def fit_floor_quad(
    gray: np.ndarray,
    params: FloorQuadParams | None = None,
    *,
    lock_modes: tuple[float, float] | None = None,
) -> FloorQuad | None:
    """Return the floor quadrilateral, or None when four creases cannot be chosen.

    ``lock_modes`` replaces this frame's two line angles with a pose template's
    angles (radians). Offsets still come from this frame.
    """
    if gray.ndim != 2:
        raise ValueError(f"gray image must be 2D, got shape {gray.shape}")
    cfg = params or FloorQuadParams()
    selected = _select_floor_lines(gray, cfg, cfg.canny_low, cfg.canny_high, cfg.hough_threshold)
    chosen = None if selected is None else _four_inner_lines(selected, cfg)
    if chosen is None and selected is not None:
        faint = _select_floor_lines(gray, cfg, _FAINT_CANNY_LOW, _FAINT_CANNY_HIGH, _FAINT_HOUGH_THRESHOLD)
        chosen = None if faint is None else _four_inner_lines(selected, cfg, fill_from=faint)
    if chosen is None:
        return None
    lines, modes = chosen
    center = _image_center(gray)
    vertices = _intersect_line_pairs(_relock_lines(lines, modes, center, lock_modes))
    if vertices is None:
        return None
    seed_diagonal = mean_diagonal_px(vertices)
    shifted, outward = shift_quad_together(gray, vertices)
    if shifted is not None:
        vertices = shifted
    area = float(cv2.contourArea(vertices.astype(np.float32)))
    return FloorQuad(
        vertices_xy=vertices,
        area_px=area,
        seed_diagonal_px=seed_diagonal,
        outward_px=outward,
    )


def _select_floor_lines(
    gray: np.ndarray,
    cfg: FloorQuadParams,
    canny_low: int,
    canny_high: int,
    hough_threshold: int,
) -> list[tuple[float, float, float]] | None:
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, canny_low, canny_high)
    cx, cy = _image_center(gray)
    ys, xs = np.nonzero(edges)
    if len(xs) == 0:
        return None
    radius = np.hypot(xs - cx, ys - cy)
    band = np.zeros_like(edges)
    keep = (radius >= cfg.edge_radius_min_px) & (radius <= cfg.edge_radius_max_px)
    band[ys[keep], xs[keep]] = 255
    lines = cv2.HoughLines(band, 1, np.pi / 180, hough_threshold)
    if lines is None:
        return None
    selected: list[tuple[float, float, float]] = []
    for rho, theta in lines[:, 0]:
        offset = float(rho - (cx * np.cos(theta) + cy * np.sin(theta)))
        if cfg.offset_min_px <= abs(offset) <= cfg.offset_max_px:
            selected.append((float(theta), float(rho), offset))
    if len(selected) < 4:
        return None
    return selected


def _four_inner_lines(
    selected: list[tuple[float, float, float]],
    cfg: FloorQuadParams,
    fill_from: list[tuple[float, float, float]] | None = None,
) -> tuple[list[tuple[float, float, float]], tuple[float, float]] | None:
    thetas = np.array([theta for theta, _, _ in selected])
    bin_width = np.deg2rad(cfg.orientation_bin_deg)
    n_bins = int(round(np.pi / bin_width))
    bins = np.linspace(0, np.pi, n_bins, endpoint=False)
    hist, _ = np.histogram(thetas, bins=np.r_[bins, np.pi])
    first = int(np.argmax(hist))
    target = (bins[first] + np.pi / 2) % np.pi
    window = np.deg2rad(cfg.mode_window_deg)
    mask = np.array([_ang_dist(float(b), float(target)) < window for b in bins])
    if not mask.any() or int(hist[mask].max()) == 0:
        return None
    second = int(np.flatnonzero(mask)[int(np.argmax(hist[mask]))])
    modes = (float(bins[first]), float(bins[second]))
    if _ang_dist(modes[0], modes[1]) < np.deg2rad(cfg.min_mode_separation_deg):
        return None

    member = np.deg2rad(cfg.member_window_deg)
    chosen: list[tuple[float, float, float]] = []
    for mode in modes:
        members = [line for line in selected if _ang_dist(line[0], mode) < member]
        found: dict[float, tuple[float, float, float]] = {}
        for sign in (1.0, -1.0):
            group = [line for line in members if np.sign(line[2]) == sign]
            if group:
                found[sign] = min(group, key=lambda line: abs(line[2]))
        if len(found) == 1 and fill_from:
            known_sign = next(iter(found))
            missing_sign = -known_sign
            target = abs(found[known_sign][2])
            pool = [line for line in fill_from if _ang_dist(line[0], mode) < member and np.sign(line[2]) == missing_sign and abs(abs(line[2]) - target) <= _PARTNER_OFFSET_TOL_PX]
            if pool:
                found[missing_sign] = min(pool, key=lambda line: abs(abs(line[2]) - target))
        if len(found) < 2:
            return None
        chosen.append(found[1.0])
        chosen.append(found[-1.0])
    return chosen, modes


def _match_modes(video_modes: tuple[float, float], lock_modes: tuple[float, float]) -> tuple[float, float]:
    direct = _ang_dist(video_modes[0], lock_modes[0]) + _ang_dist(video_modes[1], lock_modes[1])
    swapped = _ang_dist(video_modes[0], lock_modes[1]) + _ang_dist(video_modes[1], lock_modes[0])
    if direct <= swapped:
        return lock_modes
    return (lock_modes[1], lock_modes[0])


def _relock_lines(
    lines4: list[tuple[float, float, float]],
    modes: tuple[float, float],
    center: tuple[float, float],
    lock_modes: tuple[float, float] | None = None,
) -> list[tuple[float, float, float]]:
    """Put both lines of a pair on one angle, anchored where the chosen line is closest to center."""
    paired = modes if lock_modes is None else _match_modes(modes, lock_modes)
    cx, cy = center
    origin = np.array([cx, cy], dtype=np.float64)
    locked: list[tuple[float, float, float]] = []
    for index, line in enumerate(lines4):
        theta, _rho, offset = line
        old_normal = np.array([np.cos(theta), np.sin(theta)], dtype=np.float64)
        anchor = origin + float(offset) * old_normal
        mode = paired[index // 2]
        normal = np.array([np.cos(mode), np.sin(mode)], dtype=np.float64)
        if float(np.dot(normal, old_normal)) < 0.0:
            normal = -normal
        stored = float(np.arctan2(normal[1], normal[0]))
        if stored < 0.0:
            stored += np.pi
        normal = np.array([np.cos(stored), np.sin(stored)], dtype=np.float64)
        rho = float(np.dot(anchor, normal))
        new_offset = float(rho - np.dot(origin, normal))
        locked.append((stored, rho, new_offset))
    return locked


def mean_diagonal_px(vertices_xy: np.ndarray) -> float:
    """Mean of the two corner-to-corner lengths."""
    vertices = np.asarray(vertices_xy, dtype=np.float64)
    first = float(np.hypot(vertices[2, 0] - vertices[0, 0], vertices[2, 1] - vertices[0, 1]))
    second = float(np.hypot(vertices[3, 0] - vertices[1, 0], vertices[3, 1] - vertices[1, 1]))
    return 0.5 * (first + second)


def _apothem_px(vertices: np.ndarray) -> float:
    centroid = vertices.mean(axis=0)
    distances: list[float] = []
    for index in range(4):
        start = vertices[index]
        end = vertices[(index + 1) % 4]
        edge = end - start
        length = float(np.linalg.norm(edge))
        if length < 1.0:
            continue
        normal = np.array([-edge[1], edge[0]], dtype=np.float64) / length
        if float(np.dot(normal, start - centroid)) < 0.0:
            normal = -normal
        distances.append(float(np.dot(normal, start - centroid)))
    if not distances:
        return 0.0
    return float(np.mean(distances))


def shift_quad_together(
    gray: np.ndarray,
    vertices_xy: np.ndarray,
    *,
    max_px: int = 22,
    edge_margin: float = 0.28,
    min_drop: float = 5.0,
) -> tuple[np.ndarray | None, float]:
    """Expand about the centroid by the median dark-crease trough.

    One shift keeps the side-length ratios of the angle-locked seed. The return
    is the shifted vertices and the shift in pixels (0 when no trough is found).
    """
    offsets = _trough_offsets(gray, vertices_xy, max_px=max_px, edge_margin=edge_margin, min_drop=min_drop)
    if offsets is None:
        return None, 0.0
    delta = float(np.median(offsets))
    vertices = np.asarray(vertices_xy, dtype=np.float64)
    if delta == 0.0:
        return vertices, 0.0
    apothem = _apothem_px(vertices)
    if apothem < 1.0:
        return vertices, 0.0
    centroid = vertices.mean(axis=0)
    scale = (apothem + delta) / apothem
    return centroid + scale * (vertices - centroid), delta


def _intersect_line_pairs(lines4: list[tuple[float, float, float]]) -> np.ndarray | None:
    pair_a = lines4[:2]
    pair_b = lines4[2:]
    points: list[np.ndarray] = []
    for left in pair_a:
        for right in pair_b:
            matrix = np.array(
                [
                    [np.cos(left[0]), np.sin(left[0])],
                    [np.cos(right[0]), np.sin(right[0])],
                ],
                dtype=float,
            )
            if abs(np.linalg.det(matrix)) < 1e-6:
                return None
            points.append(np.linalg.solve(matrix, [left[1], right[1]]))
    vertices = np.stack(points, axis=0)
    centroid = vertices.mean(axis=0)
    order = np.argsort(np.arctan2(vertices[:, 1] - centroid[1], vertices[:, 0] - centroid[0]))
    return vertices[order]


def _trough_offsets(
    gray: np.ndarray,
    vertices_xy: np.ndarray,
    *,
    max_px: int,
    edge_margin: float,
    min_drop: float,
) -> list[float] | None:
    """Outward pixels to the first dark trough on each side. None if a side is degenerate."""
    if max_px < 1:
        raise ValueError(f"max_px must be positive, got {max_px}")
    blur = cv2.GaussianBlur(gray, (5, 5), 0).astype(np.float32)
    vertices = np.asarray(vertices_xy, dtype=np.float64)
    centroid = vertices.mean(axis=0)
    offsets: list[float] = []
    for index in range(4):
        start = vertices[index]
        end = vertices[(index + 1) % 4]
        edge = end - start
        length = float(np.linalg.norm(edge))
        if length < 1.0:
            return None
        normal = np.array([-edge[1], edge[0]], dtype=np.float64) / length
        if float(np.dot(normal, 0.5 * (start + end) - centroid)) < 0.0:
            normal = -normal
        offsets.append(_dark_edge_offset(blur, start, edge, normal, max_px=max_px, edge_margin=edge_margin, min_drop=min_drop))
    return offsets


def snap_quad_to_dark_edge(
    gray: np.ndarray,
    vertices_xy: np.ndarray,
    *,
    max_px: int = 22,
    edge_margin: float = 0.28,
    min_drop: float = 5.0,
) -> np.ndarray | None:
    """Move each side outward onto the dark floor-wall crease.

    Samples the middle of the side (``edge_margin`` at each end is ignored) so the
    corner posts do not vote. The offset is the first trough in that profile, where
    the side stops getting darker. A side with no trough inside ``max_px`` stays put.
    """
    offsets = _trough_offsets(gray, vertices_xy, max_px=max_px, edge_margin=edge_margin, min_drop=min_drop)
    if offsets is None:
        return None
    vertices = np.asarray(vertices_xy, dtype=np.float64)
    centroid = vertices.mean(axis=0)
    lines: list[tuple[float, float]] = []
    for index, offset in enumerate(offsets):
        start = vertices[index]
        end = vertices[(index + 1) % 4]
        edge = end - start
        length = float(np.linalg.norm(edge))
        normal = np.array([-edge[1], edge[0]], dtype=np.float64) / length
        midpoint = 0.5 * (start + end)
        if float(np.dot(normal, midpoint - centroid)) < 0.0:
            normal = -normal
        lines.append(_line_rho_theta(midpoint + offset * normal, normal))

    points: list[np.ndarray] = []
    for index in range(4):
        theta_a, rho_a = lines[index]
        theta_b, rho_b = lines[(index + 1) % 4]
        matrix = np.array(
            [[np.cos(theta_a), np.sin(theta_a)], [np.cos(theta_b), np.sin(theta_b)]],
            dtype=np.float64,
        )
        if abs(float(np.linalg.det(matrix))) < 1e-6:
            return None
        points.append(np.linalg.solve(matrix, [rho_a, rho_b]))
    snapped = np.stack(points, axis=0)
    center = snapped.mean(axis=0)
    order = np.argsort(np.arctan2(snapped[:, 1] - center[1], snapped[:, 0] - center[0]))
    return snapped[order]


def _line_rho_theta(point: np.ndarray, normal: np.ndarray) -> tuple[float, float]:
    theta = float(np.arctan2(normal[1], normal[0]))
    if theta < 0.0:
        theta += np.pi
    rho = float(point[0] * np.cos(theta) + point[1] * np.sin(theta))
    return theta, rho


def _sample_bilinear(image: np.ndarray, x: float, y: float) -> float:
    height, width = image.shape
    if x < 0.0 or y < 0.0 or x > width - 1 or y > height - 1:
        return float("nan")
    x0 = int(np.floor(x))
    y0 = int(np.floor(y))
    x1 = min(x0 + 1, width - 1)
    y1 = min(y0 + 1, height - 1)
    fx = x - x0
    fy = y - y0
    value = image[y0, x0] * (1.0 - fx) * (1.0 - fy) + image[y0, x1] * fx * (1.0 - fy) + image[y1, x0] * (1.0 - fx) * fy + image[y1, x1] * fx * fy
    return float(value)


def _dark_edge_offset(
    blur: np.ndarray,
    start: np.ndarray,
    edge: np.ndarray,
    normal: np.ndarray,
    *,
    max_px: int,
    edge_margin: float,
    min_drop: float,
) -> float:
    profile = np.empty(max_px + 1, dtype=np.float64)
    for dist in range(max_px + 1):
        samples = []
        for fraction in np.linspace(edge_margin, 1.0 - edge_margin, 13):
            point = start + fraction * edge + dist * normal
            samples.append(_sample_bilinear(blur, float(point[0]), float(point[1])))
        profile[dist] = np.nanmean(np.asarray(samples, dtype=np.float64))
    smoothed = profile.copy()
    smoothed[1:-1] = (profile[:-2] + profile[1:-1] + profile[2:]) / 3.0
    slope = np.diff(smoothed)
    for index in range(2, len(slope)):
        drop = smoothed[0] - smoothed[index]
        if drop >= min_drop and slope[index - 1] < -0.35 and slope[index] >= -0.25:
            return float(index)
    return 0.0


def _match_vertex_order(vertices: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Return ``vertices`` rolled into the same cyclic order as ``reference``."""
    verts = np.asarray(vertices, dtype=np.float64)
    ref = np.asarray(reference, dtype=np.float64)
    vc = verts.mean(axis=0)
    rc = ref.mean(axis=0)
    vang = np.arctan2(verts[:, 1] - vc[1], verts[:, 0] - vc[0])
    rang = np.arctan2(ref[:, 1] - rc[1], ref[:, 0] - rc[0])
    order: list[int] = []
    used: set[int] = set()
    for angle in rang:
        delta = np.abs((vang - angle + np.pi) % (2.0 * np.pi) - np.pi)
        for index in np.argsort(delta):
            index = int(index)
            if index not in used:
                used.add(index)
                order.append(index)
                break
    return verts[np.array(order)]


def _edge_modes(vertices: np.ndarray) -> tuple[float, float]:
    modes: list[float] = []
    for index in range(2):
        delta = vertices[(index + 1) % 4] - vertices[index]
        theta = float(np.arctan2(delta[1], delta[0]))
        if theta < 0.0:
            theta += np.pi
        modes.append(theta)
    return modes[0], modes[1]


def rectified_side_ratio(vertices: np.ndarray, template: np.ndarray) -> float:
    """Longest/shortest edge after mapping ``template`` to a square.

    The template's edges become equal. A video that is the same shape, up to the
    homography of that pose, lands near 1.
    """
    ordered = _match_vertex_order(vertices, template)
    source = np.asarray(template, dtype=np.float32)
    dest = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], dtype=np.float32)
    homography = cv2.getPerspectiveTransform(source, dest)
    warped = cv2.perspectiveTransform(ordered.astype(np.float32).reshape(1, 4, 2), homography).reshape(4, 2)
    edge = np.roll(warped, -1, axis=0) - warped
    lengths = np.hypot(edge[:, 0], edge[:, 1])
    shortest = float(lengths.min())
    if shortest < 1e-6:
        return float("inf")
    return float(lengths.max() / shortest)


def _pose_templates(
    vertices: np.ndarray,
    finite: np.ndarray,
    pose_bin_px: float,
    pose_min_videos: int,
) -> list[np.ndarray | None]:
    centroids = np.nanmean(vertices, axis=1)
    groups: dict[tuple[int, int], list[int]] = {}
    for index in np.flatnonzero(finite):
        key = (
            int(np.round(centroids[index, 0] / pose_bin_px)),
            int(np.round(centroids[index, 1] / pose_bin_px)),
        )
        groups.setdefault(key, []).append(int(index))
    templates: list[np.ndarray | None] = [None] * len(vertices)
    for members in groups.values():
        if len(members) < pose_min_videos:
            continue
        reference = vertices[members[0]]
        stacked = np.stack([_match_vertex_order(vertices[index], reference) for index in members])
        template = np.median(stacked, axis=0)
        for index in members:
            templates[index] = template
    return templates


def cohort_qc_flags(
    vertices_xy: np.ndarray,
    seed_diagonal_px: np.ndarray,
    *,
    shape_source: np.ndarray | None = None,
    corner_tol: float = CORNER_REL_TOL,
    side_ratio_max: float = SIDE_MAX_MIN_RATIO,
    pose_bin_px: float = POSE_BIN_PX,
    pose_min_videos: int = POSE_MIN_VIDEOS,
) -> list[tuple[str, ...]]:
    """Per-video cohort flags.

    ``corner_span``: seed diagonal is more than ``corner_tol`` (default 5%) away
    from the cohort median. ``side_mismatch``: in the floor plane of this pose's
    median quadrilateral, the longest edge is more than 3% longer than the shortest.
    A pose needs ``pose_min_videos`` videos in a ``pose_bin_px`` centroid bin.

    ``shape_source`` is the quadrilateral the pose median is built from. Pass the
    pre-refit vertices so a video pulled onto that median is not scored against a
    median that already includes the pull.
    """
    vertices = np.asarray(vertices_xy, dtype=np.float64)
    diagonals = np.asarray(seed_diagonal_px, dtype=np.float64)
    if vertices.ndim != 3 or vertices.shape[1:] != (4, 2):
        raise ValueError(f"vertices_xy must have shape (N, 4, 2), got {vertices.shape}")
    if len(diagonals) != len(vertices):
        raise ValueError(f"seed_diagonal_px length {len(diagonals)} != {len(vertices)} videos")
    source = vertices if shape_source is None else np.asarray(shape_source, dtype=np.float64)
    if source.shape != vertices.shape:
        raise ValueError(f"shape_source shape {source.shape} != vertices {vertices.shape}")
    finite = np.isfinite(diagonals) & np.isfinite(vertices).all(axis=(1, 2))
    source_finite = np.isfinite(source).all(axis=(1, 2))
    flags: list[list[str]] = [[] for _ in range(len(vertices))]
    if finite.any():
        median = float(np.median(diagonals[finite]))
        if median > 0.0:
            for index in np.flatnonzero(finite):
                if abs(float(diagonals[index]) - median) / median > corner_tol:
                    flags[int(index)].append("corner_span")
    for index, template in enumerate(_pose_templates(source, source_finite, pose_bin_px, pose_min_videos)):
        if template is None or not finite[index]:
            continue
        if rectified_side_ratio(vertices[index], template) > side_ratio_max:
            flags[index].append("side_mismatch")
    return [tuple(item) for item in flags]


def _place_on_pose(quad: FloorQuad, template: np.ndarray) -> FloorQuad:
    """Put the pose's median shape at this video's centroid and mask diagonal.

    The seed diagonal is left alone, so the corner-to-corner ruler stays this video's.
    """
    ordered = _match_vertex_order(quad.vertices_xy, template)
    video_center = ordered.mean(axis=0)
    template_center = template.mean(axis=0)
    template_diagonal = mean_diagonal_px(template)
    scale = 1.0 if template_diagonal < 1.0 else mean_diagonal_px(ordered) / template_diagonal
    placed = (template - template_center) * scale + video_center
    centroid = placed.mean(axis=0)
    order = np.argsort(np.arctan2(placed[:, 1] - centroid[1], placed[:, 0] - centroid[0]))
    vertices = placed[order]
    area = float(cv2.contourArea(vertices.astype(np.float32)))
    return FloorQuad(
        vertices_xy=vertices,
        area_px=area,
        seed_diagonal_px=quad.seed_diagonal_px,
        outward_px=quad.outward_px,
    )


def refit_side_outliers(
    grays: list[np.ndarray | None],
    quads: list[FloorQuad | None],
    params: FloorQuadParams | None = None,
) -> list[FloorQuad | None]:
    """Pull ``side_mismatch`` videos onto their pose.

    First retry with the pose's side angles. If the floor-plane edges are still
    more than 3% apart, use the pose's median shape at this video's own size.
    """
    if len(grays) != len(quads):
        raise ValueError(f"grays ({len(grays)}) and quads ({len(quads)}) differ in length")
    cfg = params or FloorQuadParams()
    vertices = np.full((len(quads), 4, 2), np.nan, dtype=np.float64)
    diagonals = np.full(len(quads), np.nan, dtype=np.float64)
    for index, quad in enumerate(quads):
        if quad is None:
            continue
        vertices[index] = quad.vertices_xy
        diagonals[index] = quad.seed_diagonal_px
    finite = np.isfinite(diagonals) & np.isfinite(vertices).all(axis=(1, 2))
    templates = _pose_templates(vertices, finite, POSE_BIN_PX, POSE_MIN_VIDEOS)
    extras = cohort_qc_flags(vertices, diagonals)
    refit = list(quads)
    for index, extra in enumerate(extras):
        template = templates[index]
        current = quads[index]
        if "side_mismatch" not in extra or template is None or current is None:
            continue
        gray = grays[index]
        if gray is not None:
            updated = fit_floor_quad(gray, cfg, lock_modes=_edge_modes(template))
            if updated is not None and rectified_side_ratio(updated.vertices_xy, template) < rectified_side_ratio(current.vertices_xy, template):
                current = updated
        if rectified_side_ratio(current.vertices_xy, template) > SIDE_MAX_MIN_RATIO:
            current = _place_on_pose(current, template)
        refit[index] = current
    return refit


def quad_review_flags(
    quad: FloorQuad,
    image_shape: tuple[int, int],
    *,
    area_min_px: float = AREA_MIN_PX,
    area_max_px: float = AREA_MAX_PX,
) -> tuple[str, ...]:
    """Quality-control flags. Empty means the quadrilateral is usable for a corner mask."""
    flags: list[str] = []
    if not (area_min_px <= quad.area_px <= area_max_px):
        flags.append("area_out_of_band")
    height, width = image_shape
    vertices = quad.vertices_xy
    if np.any(vertices[:, 0] < -1) or np.any(vertices[:, 0] > width) or np.any(vertices[:, 1] < -1) or np.any(vertices[:, 1] > height):
        flags.append("vertex_outside")
    center = ((width - 1) / 2.0, (height - 1) / 2.0)
    inside = cv2.pointPolygonTest(vertices.astype(np.float32), center, False)
    if inside < 0:
        flags.append("center_outside")
    return tuple(flags)


def mask_outside_quad(frame: np.ndarray, vertices_xy: np.ndarray) -> np.ndarray:
    """Zero pixels outside the floor quadrilateral. Width and height stay the same."""
    if frame.ndim not in (2, 3):
        raise ValueError(f"frame must be gray or color, got shape {frame.shape}")
    vertices = np.asarray(vertices_xy, dtype=np.float64)
    if vertices.shape != (4, 2):
        raise ValueError(f"vertices_xy must have shape (4, 2), got {vertices.shape}")
    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    pts = np.round(vertices).astype(np.int32).reshape(-1, 1, 2)
    cv2.fillPoly(mask, [pts], 255)
    masked = np.array(frame, copy=True)
    masked[mask == 0] = 0
    return masked


def render_quad_overlay(gray: np.ndarray, quad: FloorQuad | None, flags: tuple[str, ...]) -> np.ndarray:
    """BGR review image. Green polygon when ``flags`` is empty, red otherwise."""
    canvas = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    color = (0, 0, 255) if flags or quad is None else (0, 255, 0)
    if quad is not None:
        pts = np.round(quad.vertices_xy).astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(canvas, [pts], True, color, 2)
    label = "pass" if quad is not None and not flags else "review:" + ",".join(flags or ("fit_failed",))
    cv2.putText(canvas, label[:80], (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)
    return canvas
