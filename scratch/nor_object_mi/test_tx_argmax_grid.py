"""Litmus for TX argmax grid video path mapping."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRATCH = Path(__file__).resolve().parents[1]
if str(_SCRATCH) not in sys.path:
    sys.path.insert(0, str(_SCRATCH))

from nor_object_mi.tx_argmax_grid import dummy_coordinates, kpms_key_to_mp4  # noqa: E402

import numpy as np


def test_kpms_key_to_mp4() -> None:
    key = (
        "D:-nor vids-standard format-exp1-3115-"
        "NOR1 ID OBJ Arena 5 07-03-25 3115 06-07.h5"
    )
    root = Path(r"C:\Users\admin\Documents\work\sack\datas\impress")
    got = kpms_key_to_mp4(key, root)
    expect = (
        root
        / "standard format"
        / "exp1"
        / "3115"
        / "NOR1 ID OBJ Arena 5 07-03-25 3115 06-07.mp4"
    )
    assert got == expect


def test_dummy_coordinates_tiles_centroid() -> None:
    c = np.array([[1.0, 2.0], [3.0, 4.0]])
    d = dummy_coordinates(c)
    assert d.shape == (2, 8, 2)
    np.testing.assert_array_equal(d[:, 0, :], c)
    np.testing.assert_array_equal(d[:, 7, :], c)
