"""Locked choices for impress n-gram descriptives + condition ladders (2026-08-12).

Mining
------
- max_n = 5 (mine 1..5; n=1 = syllables)
- optional post-mine knobs (do not require re-mine):
  - use_n / pattern_len: analyze a single order ≤ max_n
  - max_span_frames: drop occurrences whose span (sum of bout frames) exceeds cap

Ladder alphabet
---------------
- top-M + OTHER (M configurable; OTHER id = -1)
- frequency ranked within model × cleanup × pattern_len on the occurrence table

Stimulus for an n-gram occurrence
---------------------------------
- mean distance over the span = bout-frame-weighted mean of bout_mean_dist_*
  (equivalent to frame mean when bout means are frame means)

Cleanup
-------
- optional absorb short bouts < min_bout_frames (default 3 when --clean)
- no frames discarded (see syllable_cleanup.py / cleanup_rule.txt)

Cohorts / paths
---------------
- kpMS: sack/datas/impress/moseq_251017/paramscan_*/
- NOR: sack/datas/impress/my_NOR_results.h5
- artifacts: …/moseq_251017/_ngram_*/ and _nor_object_mi/…/condition_ladder*_ngram*
"""

from __future__ import annotations

MAX_N_MINE = 5
OTHER_PATTERN_ID = -1
DEFAULT_TOP_M = 50
DEFAULT_MIN_BOUT_FRAMES_CLEAN = 3
