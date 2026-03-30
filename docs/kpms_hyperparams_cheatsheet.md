# keypoint-MoSeq (kpMS) hyperparameters — condensed cheatsheet

This doc maps the `FitConfig` fields in `vast/kpms/fit.py` to model behavior, gives practical tuning hints, and ties them to **numerical precision** (float32 vs float64) and **Stage 2 Gibbs** failures.

**References:** [Keypoint-MoSeq FAQ — syllable duration / κ](https://keypoint-moseq.readthedocs.io/en/latest/FAQs.html#choosing-the-target-syllable-duration), [Nature Methods 2024](https://doi.org/10.1038/s41592-024-02318-2).

---

## Precision: why Stage 2 is sensitive

| Setting | Effect |
|--------|--------|
| **JAX `jax_enable_x64=True`** | Default when you `import keypoint_moseq` — uses float64 where JAX promotes arrays. **Keep this on** for fitting unless you have a strong reason. |
| **`convert_data_precision(..., x64=True)`** | Your pipeline sets input data to double — aligns with the above. |
| **Pure float32 fitting** | Stage 1 (AR-HMM only on fixed latents) is easier; **Stage 2** runs Kalman backward sampling on `x`, centroid smoothing on `v`, optional heading `h`, and local scales `s`. Covariance propagation in Kalman steps loses margin fast in float32 → **NaNs, invalid Cholesky, or Inf** after many Gibbs iterations. |

**Rule of thumb:** Treat float32 as *visualization / I/O* friendly; treat **float64 as required for stable Stage 2 Gibbs** on long runs.

---

## Two-stage fit (your script)

1. **Stage 1 — `ar_only=True`**  
   Resamples HDP transitions (`π`, sticky transitions), AR parameters (`A`, `b`, `Q`), and discrete states `z`, using the **current** continuous latent trajectory `x` (from initialization / PCA). No full pose SLDS update.

2. **Stage 2 — `ar_only=False`**  
   Same AR-HMM block **plus** pose SLDS blocks: resample `x` (Kalman), `v` (location), optionally `h` (heading), local noise `s`, etc. This is the **blocked Gibbs** loop that stresses numerics.

After Stage 1 you **`update_hypparams(..., kappa=stage2_kappa)`** — stickiness changes before the full model runs.

---

## Hyperparameters (aligned with `FitConfig`)

### Randomization & inputs

| Parameter | Role | Tuning |
|-----------|------|--------|
| **`seed`** | RNG for init and Gibbs | Fix for reproducibility. |
| **`pca_num_frames`** | # frames used to fit PCA / whitening | More frames → stabler PCA; very large values are usually fine if memory allows. |
| **`conf_threshold`** | Masks low-confidence keypoints | **Too aggressive masking** → sparse/noisy observations → harder Kalman steps. **Raise threshold slightly** (stricter mask) only if outliers dominate; **lower** if you throw away too much signal. |

### Transition model (sticky HDP)

| Parameter | Role | Tuning |
|-----------|------|--------|
| **`num_states`** | Max discrete syllable states `K` | Larger `K` → finer segmentation, **more transition mass to estimate**, heavier message passing. **Reduce** if the model fragments behavior or feels unstable. |
| **`alpha`** | HDP / transition concentration (row variability) | Higher → **more uniform** transitions, less peaked dynamics. If discrete paths oscillate wildly between few states, increasing smoothing can calm sampling (at the cost of blurring preferences). |
| **`gamma`** | HDP new-state / global mass | Affects how often **unused / rare** states appear. Very extreme values interact with `num_states` and data size. |
| **`stage1_kappa` / `stage2_kappa`** | **Stickiness** (self-transition boost) | **Primary dial for bout length.** Literature often targets ~**400 ms median syllable duration** for mice (adjust for framerate and species). **Higher κ → longer bouts.** Stage 1 often uses **very large κ** so AR+HMM settles with long segments; Stage 2 uses **moderate κ** for biologically plausible durations. |

### Autoregressive emissions (latent dynamics)

| Parameter | Role | Tuning |
|-----------|------|--------|
| **`latent_dim`** | Dimension of continuous latent per frame | Too **low** → underfitting; too **high** → stiff, ill-conditioned AR blocks and Kalman. **Start near paper defaults; increase slowly.** |
| **`nlags`** | AR order (`p` lags) | **Higher order → larger state space in AR** → more matrix multiplies and covariances in float32 danger zone. If unstable, try **`nlags=3–4`** before shrinking dimension. |
| **`s0_scale` / `k0_scale`** | Scales on `S_0` / `K_0` AR priors (`ar_hypparams`) | Control prior strength on dynamics **S** and **lag stack K**. **Very tight priors** can help stability; **very loose** priors let dynamics explode (large `Q`, Kalman pain). |

### Observation / centroid (in `fit.py`, not `FitConfig`)

These are in `init_model` today:

- **`obs_hypparams`**: `sigmasq_0`, `sigmasq_C`, `nu_sigma`, `nu_s` — global and local observation noise structure. **`nu_sigma` huge** (e.g. `1e5`) pushes toward data-determined scales; if you see noise collapse or blow-up, review these with the jax_moseq docs.
- **`cen_hypparams`**: `sigmasq_loc` — centroid / location smoothness.

### Training control

| Parameter | Role | Tuning |
|-----------|------|--------|
| **`stage1_ar_only_iters`** | Gibbs iterations Stage 1 | If Stage 2 fails immediately, check Stage 1 actually converged to sane `z` and AR params (plots / diagnostics). |
| **`stage2_full_iters`** | Extra iterations in full SLDS | **More iterations → more accumulation of numerical error in float32.** In float64, long runs are normal. |
| **`save_every`** | Checkpoint cadence | Does not affect math; use for recovery. |
| **`reindex_syllables`** | Renumbers syllables after fit | Bookkeeping only; mismatched checkpoint `data` shapes break this (your script already guards stale checkpoints). |

---

## Stage 2 Gibbs failures — what to try (order of effort)

1. **Confirm float64 end-to-end**  
   `jax.config.jax_enable_x64` must be **True** before JAX builds arrays. Import order: **`import keypoint_moseq` first** (it sets x64), or set explicitly. Avoid forcing float32 arrays into the model dict.

2. **Increase `jitter` in `kpms.fit_model`**  
   Default `jitter=0.001` adds diagonal inflation for pose resampling. **Try `0.01` → `0.05`** if you see NaNs mid Stage 2 (documented in `keypoint_moseq.fitting.fit_model`).

3. **Toggle `parallel_message_passing`**  
   Auto-**True** on GPU. The parallel Kalman path can differ numerically. **Set `parallel_message_passing=False`** to test a more sequential (often stabler) path.

4. **Soften dynamics / dimension**  
   Slightly **lower `latent_dim`** or **`nlags`**, or **tighten** `S_0_scale` / `K_0_scale` toward smaller dynamics variance.

5. **Sticky κ**  
   Absurd κ mismatch with data can produce odd message-passing edge cases; tune κ toward a **realistic median duration** rather than extremes.

6. **Hardware / XLA**  
   Rare: OOM manifests as opaque failures; **shorter trials in the manifest** or **smaller `num_states`** reduce per-iteration work.

---

## Connection to your other notes

- **Shannon entropy on syllable proportions** measures diversity of usage; **not** a hyperparameter — but if entropy is trivially low, you may have **κ too high** or **`num_states` mis-specified**.
- **~400 ms bout target** is the standard biological anchor for **κ** tuning in mice (FAQ / NM paper).

---

## One-line “float32” summary

> Use **float64 + default x64** for Stage 2; if you must experiment with float32, expect to **shorten Stage 2**, **raise `jitter`**, and **reduce `latent_dim` / `nlags`**, and still treat success as lucky.
