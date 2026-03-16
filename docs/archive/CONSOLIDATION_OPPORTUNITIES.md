# Consolidation opportunities (logic / abstraction collapse)

Scanned for: duplicated logic, thin wrappers, config doing too much, “ask then act” that could be “tell,” and repeated defaults/parsing.

---

## Done

- **Phase/mode parsing**: `main_window._apply_config_to_ui` no longer re-implements phase/mode parsing. It uses `parse_phase_mode_from_config(self._config)` from `trial_logic` (single source of truth).

---

## Recommended next

### 1. **run_phase / run_mode effective string**

**Where**: `main_window` (e.g. recording, analysis), `recording.py`, `profile.py`.

**What**: The pattern `getattr(config, "run_phase", "habituation") or "habituation"` (and same for `run_mode` with `"continuous"`) appears in several places. Recording and H5 need the *string* (e.g. `"habituation"`), not the enum.

**Consolidate**: On `ControllerConfig`, add:

- `effective_run_phase(self) -> str`: `(getattr(self, "run_phase", None) or "habituation").strip() or "habituation"`
- `effective_run_mode(self) -> str`: same for `run_mode` / `"continuous"`

Then in `recording.py`, `main_window` (where only the string is needed), use `config.effective_run_phase` / `config.effective_run_mode`. Keeps defaults and normalization in one place.

**Profile**: When *loading* from dict, profile still needs its own defaults in `_run_phase_from_dict` / `_run_mode_from_dict` (no config object yet). Optionally have those call a shared helper that normalizes a string + default (e.g. in `config` or `trial_logic`).

---

### 2. **h5_filename effective value**

**Where**: `main_window` (recording block, `_apply_config_to_ui`), `profile.config_from_dict`.

**What**: `(getattr(self._config, "h5_filename", None) or "trials.h5").strip() or "trials.h5"` and profile’s `str(d.get("h5_filename", "trials.h5") or "trials.h5").strip() or "trials.h5"`.

**Consolidate**: Add `ControllerConfig.effective_h5_filename(self) -> str`. Use it everywhere the “never empty, default trials.h5” value is needed. Profile’s `config_from_dict` can keep building the string from `d` but could use the same default constant.

---

### 3. **Tracking/SLEAP config access in main_window**

**Where**: `main_window` uses many `getattr(self._config, "track_show", True)`, `getattr(self._config, "sleap_model_path", "")`, `getattr(self._config, "track_backup_only", False)`, etc.

**What**: Defensive defaults are repeated. `ControllerConfig` already defines these fields with defaults.

**Consolidate**: Prefer direct `self._config.track_show`, `self._config.sleap_model_path`, etc. If some code paths can see an older or partial config, either (a) ensure config is always a full `ControllerConfig` with defaults, or (b) add a small helper that returns a “view” with safe defaults (e.g. `config.tracking_view()` with `.show`, `.sleap_path`, `.backup_only`). Option (a) is simpler if feasible.

---

## Lower priority

### 4. **Session ID from UI**

**Where**: Many places do `self._session_id_edit.text().strip()` or `sid = self._session_id_edit.text().strip()`.

**What**: Repeated UI read + strip.

**Consolidate**: One helper on the window, e.g. `_session_id(self) -> str`, so call sites use `self._session_id()` and the “strip empty to something” rule lives in one place if you add it later.

---

### 5. **Profile run_phase / run_mode normalization**

**Where**: `profile._run_phase_from_dict` and `_run_mode_from_dict` duplicate validation/defaults that match `trial_logic._parse_phase_mode` (valid values, default when missing/invalid).

**What**: Two places define “what is a valid phase/mode string and what’s the default.”

**Consolidate**: Either (a) have profile call into trial_logic for normalization (e.g. a function that takes raw string + default and returns normalized string), or (b) keep profile’s dict-only helpers but document that they must stay in sync with `_parse_phase_mode`. (a) gives a single source of truth.

---

### 6. **ensure_created(session_id, 0) call sites**

**Where**: Several places call `self._trial_controller.ensure_created(self._session_id_edit.text().strip(), 0)` with the same two arguments.

**What**: Repeated “current session ID from UI” + `0`.

**Consolidate**: After introducing `_session_id()`, a helper like `_ensure_trial_created(self)` that calls `ensure_created(self._session_id(), 0)` would collapse the repeated pattern (optional; only a few call sites).

---

## Summary

| Opportunity              | Benefit                         | Effort |
|--------------------------|---------------------------------|--------|
| effective_run_phase/mode | Single default + normalization  | Low    |
| effective_h5_filename    | Single default + normalization  | Low    |
| Tracking config access   | Fewer getattr, clearer defaults| Low    |
| _session_id()            | One place for UI session ID     | Low    |
| Profile phase/mode       | Single source of valid strings  | Medium |
| _ensure_trial_created()  | Less repetition at call sites  | Low    |
