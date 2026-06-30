# Upstream B-SOiD integration is gated by a uv resolver spike

Option B runs the genuine upstream tool (B-SOiD first, MotionMapper later). Before wiring it into the main `uv` environment as an extra, a throwaway **resolver spike** must prove `uv` can solve a `bsoid` extra against the current lock *without downgrading* `jax` (hard-pinned `<0.7` for keypoint-moseq + tensorflow-probability), `numpy` (1.26.4), or `keypoint-moseq`. B-SOiD pulls TensorFlow — a third DL framework alongside the existing jax (kpMS) and torch (SLEAP) — so the conflict risk is real.

If the spike fails (the strong prior), Option B falls back to an **isolated environment behind a file-based boundary**: a pose-export adapter feeds the tool in its own env, and we ingest its per-frame label CSV back into the harness. Either way, the upstream tool stays off the kpMS critical path. This protects the brittle jax pin that the whole ethogram fit depends on.
