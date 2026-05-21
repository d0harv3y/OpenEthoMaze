"""Decode NOR native keypoint-moSeq HDF5 group names into filesystem paths."""

from __future__ import annotations

from pathlib import Path


def nor_native_group_to_h5_and_sleap(
    group_name: str,
    *,
    base_dir: Path | str,
    prefix_encoded: str = "D:-nor vids-",
    path_hyphens: int = 3,
) -> tuple[Path, Path]:
    """
    Map a top-level ``results.h5`` / ``checkpoint`` recording key to input H5 and SLEAP paths.

    Encoding (NOR param-scan fits): ``D:-nor vids-`` stands for ``base_dir``, then the next
    ``path_hyphens`` hyphen-separated tokens are relative directory components; the remainder
    (after those hyphens) is the filename, which may itself contain hyphens (e.g. dates).

    Returns:
        ``(input_h5_path, sleap_path)`` where ``sleap_path`` is ``str(h5) + ".slp"``
        (e.g. ``...file.h5.slp``).
    """
    if not group_name.startswith(prefix_encoded):
        raise ValueError(
            f"Group name must start with {prefix_encoded!r}, got {group_name[:120]!r}..."
        )
    rest = group_name[len(prefix_encoded) :]
    parts = rest.split("-", path_hyphens)
    if len(parts) != path_hyphens + 1:
        raise ValueError(
            f"Expected {path_hyphens + 1} segments after splitting {path_hyphens} hyphens in "
            f"{group_name[:120]!r}..., got {len(parts)}"
        )
    base = Path(base_dir)
    h5_path = base.joinpath(*parts)
    sleap_path = Path(str(h5_path) + ".slp")
    return h5_path, sleap_path
