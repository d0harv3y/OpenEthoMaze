## Task

Investigate why SLEAP predictions in ORM acquisition controller differ from SLEAP GUI predictions for the same data.

## Background

- User suspects frame preprocessing / overlays may be contaminating model input.
- Similar issue was previously fixed in VAST path, but prediction pipeline should now be generic.
- Need to trace frame path from camera read to predictor input and compare with displayed overlays.

## Checklist

- [x] Trace full frame flow in ORM acquisition: camera -> preprocessing -> predictor -> overlay.
- [x] Verify whether predictor receives raw frame or display/overlay-modified frame.
- [x] Verify task-specific branches (VAST vs RAM) share the same predictor input path.
- [x] Identify other divergence sources vs SLEAP GUI (resize, color order, normalization, crop/mask, frame timing).
- [x] Summarize likely root cause(s) and concrete validation steps.

## Findings (current)

1. **Overlays are not fed to SLEAP.**
   - In `main_window._on_camera_tick`, display overlays are applied to `img_display`.
   - Predictor input is `to_track`, derived from `img_raw`, then sent via `TrackingController.submit_frame(to_track, now)`.
2. **Predictor input *is* modified before SLEAP in ORM** (likely major discrepancy source):
   - Optional **horizontal flip** (`Flip image`) mutates `img_raw` before tracking.
   - Optional **tracking crop + circular mask** (VAST/common path) applies `bitwise_and` to `to_track`.
   - Optional **RAM walkable mask crop** applies task mask to `to_track`.
   - This means SLEAP often sees masked/cropped frames in ORM, unlike full-frame SLEAP GUI runs.
3. **Potential channel-order mismatch risk:**
   - ORM camera frames are OpenCV BGR.
   - ORM’s custom SLEAP call directly builds tensors from numpy and does not convert BGR->RGB.
   - `sleap_nn` preprocessing names/ops assume RGB semantics for color transforms (e.g., `rgb_to_grayscale`), so this can shift predictions depending on training preprocessing.
4. **Inference path in ORM is custom**:
   - ORM bypasses `predictor.predict(...)` and calls `pred.inference_model(...)` directly after manual preprocessing.
   - Any drift from canonical predictor preprocessing can cause GUI-vs-ORM differences.

## Suggested validation steps

1. In ORM, set conditions closest to SLEAP GUI:
   - `Flip image` off.
   - Tracking mask radius disabled if possible (or set to full frame).
   - In RAM, temporarily bypass walkable mask crop to compare.
2. Log/save exact `to_track` frames and run the same model on those frames in standalone `sleap-nn` predictor path.
3. A/B test BGR vs RGB conversion before `_numpy_to_tensor_batch` and compare node coordinates/confidence.
