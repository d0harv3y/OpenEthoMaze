"""Litmus checks for open-field session time bins."""

from __future__ import annotations

import pytest

from maze.pipeline.open_field.time_bins import (
    BIN_WIDTH_10MIN_S,
    BIN_WIDTH_5MIN_S,
    endpoint_bins,
    equal_width_bins,
)


def test_twenty_minute_file_is_first_and_last_10() -> None:
    bins = equal_width_bins(1200.05, BIN_WIDTH_10MIN_S)
    assert [(b.bin_index, b.t0_s, b.t1_s) for b in bins] == [
        (0, 0.0, 600.0),
        (1, 600.0, 1200.05),
    ]
    pair = endpoint_bins(bins)
    assert pair is not None
    assert pair[0].bin_index == 0
    assert pair[1].t0_s == 600.0
    assert pair[1].t1_s == 1200.05


def test_ten_minute_file_is_one_bin_and_has_no_endpoint_pair() -> None:
    bins = equal_width_bins(600.02, BIN_WIDTH_10MIN_S)
    assert len(bins) == 1
    assert bins[0].t0_s == 0.0
    assert bins[0].t1_s == 600.02
    assert endpoint_bins(bins) is None


def test_twelve_second_file_has_no_full_bin() -> None:
    assert equal_width_bins(12.0, BIN_WIDTH_10MIN_S) == []
    assert endpoint_bins([]) is None


def test_five_minute_bins_on_twenty_minutes_are_four_rows() -> None:
    bins = equal_width_bins(1200.0, BIN_WIDTH_5MIN_S)
    assert [b.t0_s for b in bins] == [0.0, 300.0, 600.0, 900.0]
    assert [b.t1_s for b in bins] == [300.0, 600.0, 900.0, 1200.0]
    pair = endpoint_bins(bins)
    assert pair is not None
    assert (pair[0].bin_index, pair[1].bin_index) == (0, 3)


def test_partial_tail_longer_than_slop_is_omitted() -> None:
    bins = equal_width_bins(1190.0, BIN_WIDTH_10MIN_S)
    assert len(bins) == 1
    assert bins[0].t1_s == 600.0


def test_nonpositive_width_raises() -> None:
    with pytest.raises(ValueError):
        equal_width_bins(1200.0, 0.0)
