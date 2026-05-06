
You don’t need deep Gibbs/Kalman theory to reason about this; the failure mode is mostly **linear algebra in low precision**, and the model has several places where that bites.

### What Gibbs is doing here (one pass)

Each iteration **re-samples one piece of the model while holding the rest fixed**. In keypoint-SLDS that includes things like:

- **Discrete states** `z` (which AR regime you’re in)
- **Continuous latents** `x` (low-dim trajectory that explains keypoints after pose/location)
- **Centroids** `v` (another Gaussian / Kalman-style smoothing step on top of aligned keypoints)
- **Per-keypoint noise scales** `s`, global scales, headings, etc.

Many of those steps are **“Gaussian conditionals”**: build a covariance, do something equivalent to a **solve / Cholesky / Kalman smoother**. That’s all standard Kalman pain: if a covariance is **almost singular** (or becomes so after rounding), you get **negative eigenvalues in theory-PSD matrices**, bad Cholesky, huge samples, then **NaNs** that infect the next Gibbs step.

Float32 has ~7 decimal digits of precision. Your model has **long chains of matmuls**, **ratios of variances**, and **products like `s * sigmasq`** in headings/locations. When something is weakly identified, variances can get **tiny**; in f32 that becomes **division by something that underflows or is rounded to zero** → exactly the “Kalman pain” you’re sensing, just manifested inside the sampler.

So: **yes, there are levers**, but they’re “improve conditioning / add regularization / reduce problem size,” not a single magic flag that guarantees stability.

### Knobs that actually target the math

1. **`jitter` in kpMS**
   Upstream documents it as **inflating the diagonal of dynamics covariance during backward sampling of the continuous states** (`x`). That helps **one** fragile linear-Gaussian step. It does **not** magically stabilize every block.

2. **Parallel vs sequential Kalman on GPU**
   In `jax_moseq.utils.kalman`, when `parallel=True`, the code calls Dynamax’s **parallel** posterior sampler, which **does not take `jitter`**. When `parallel=False`, it uses the **serial** sampler, which **does** add `jitter` to smoothed covariances before sampling. So for **`x`**, “turn off parallel message passing” can change numerics partly because **`jitter` actually applies** there.

3. **Where your NaNs were (`s`, `v`)**
   **`v` is updated with `kalman_sample` in `resample_location`, and that call path uses the default `jitter=0`** — the `jitter` argument from `fit_model` is **not** wired into that Kalman smoother in the copy of `jax_moseq` in your env. So cranking `--jitter` may do **little for `v` NaNs** until someone extends upstream to pass the same jitter (and ideally adds a similar stabilization to the **parallel** smoother if you stay on GPU).

4. **Priors / hyperparameters (often more important than jitter for `s`)**
   **`s` comes from squared errors** and inverse-Gamma–style updates. If the model can explain data **too tightly**, scales can collapse → tiny `variance = s * sigmasq` → blow-ups in heading/location updates. **Stronger priors** (e.g. things like larger effective prior mass on observation noise / scales — the `nu_*`, `sigmasq_*` style hyperparameters you pass into `init_model`) **forbid** absurdly small variances and are the standard statistical fix. That’s not superstition; it’s **preventing ill-conditioned Gaussians**.

5. **Smaller discrete/continuous state**
   Fewer `num_states`, smaller `latent_dim` / `nlags` → **smaller matrices, better conditioning**, fewer opportunities for f32 to round a PSD matrix into something nasty.

6. **GPU tensor cores**
   JAX on NVIDIA often uses **TF32** for matmuls. Setting `JAX_DEFAULT_MATMUL_PRECISION` to `float32` or `highest` can sometimes change behavior (either help or hurt). It’s worth **one** A/B on your failing config; it’s not a guaranteed win.

### Honest bottom line

- **There is no theorem** that says “keypoint-SLDS Gibbs in float32 always converges.”
- **There is a real engineering gap**: stabilization (`jitter`) is **not uniformly applied** across all Kalman steps in the stack (notably **`v`**), and the **GPU parallel** smoother **ignores `jitter`** today. Fixing that upstream is a legitimate path toward **more reliable f32**.
- Until then, the reliable options are: **stronger priors + smaller model + serial Kalman for `x` + sweeps**, or **float64** for the full chain.

If you want to pursue “make f32 work” as a project, the highest-yield code change (upstream `jax_moseq`) is: **thread `jitter` into `resample_location`’s `kalman_sample`**, and longer-term **add diagonal padding (or equivalent) to the parallel LGSSM sampler** in Dynamax so GPU runs get the same regularization as the serial path.
