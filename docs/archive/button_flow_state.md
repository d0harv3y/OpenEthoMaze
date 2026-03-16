# Run button flow by state [*deprecated]*

**States** (from `trial_logic.TrialState`): `IDLE` | `ITI` | `WAIT_NOT_CENTER` | `TRIAL_RUNNING` | `TRIAL_SUCCESS` | `TRIAL_TIMEOUT`.

**Run active** = run timer is active (session started; state is not IDLE unless just stopped). When the controller has no state machine (`get_state_machine()` is None), run is not active.

**When is there no state machine?** The state machine is created at startup in `_apply_startup_profile()` (main_window.py): either when no "reload last profile" path is set, or after loading a profile (controller is reset then `ensure_created(...)`). So after the window is ready, we always have a state machine and the program is effectively **starting in IDLE**. The "(no state machine)" case in the table below only exists briefly during window init, or if code ever cleared the state machine without recreating it; the UI is designed so the user always sees a real state (Idle, ITI, Trial, etc.).

---

## Intent: Next and Previous never start a trial

- **Next** and **Previous** only change **which trial** (index) is current. That updates which **exit** and which **animal** are assigned to the current trial (e.g. via Latin square). They do **not** start the run timer and do **not** cause a transition into `TRIAL_RUNNING`.
- **Starting a trial** (run timer on, state moving ITI → WAIT_NOT_CENTER → TRIAL_RUNNING) happens only when the user presses **Start trial** (from IDLE) and then the run loop advances automatically when the rodent leaves center (or when you explicitly drive the state machine). So: Next/Previous = "change the index and the assigned exit/animal"; Start + run loop = "actually run a trial".

Edit the tables below to change which buttons are enabled and what they do. Implementation lives in `gui/main_window.py`: enable logic in `_update_run_button_states()`, actions in `_on_start_trial`, `_on_previous_trial`, `_on_next_trial`, `_on_end_trial`, `_on_stop_run`.

---

## 1. When is each button enabled?

*(After startup we always have a state machine in IDLE until the user starts a run. The first row covers the edge case before that or if SM were ever cleared.)*


| State              | Start trial | Previous trial | Next trial | Manual Success | Stop |
| ------------------ | ----------- | -------------- | ---------- | -------------- | ---- |
| (no state machine) | ✓           | ✓              | ✓          | —              | —    |
| IDLE               | ✓           | ✓              | ✓          | —              | —    |
| ITI                | —           | —              | —          | ✓              | ✓    |
| WAIT_NOT_CENTER    | —           | —              | —          | ✓              | ✓    |
| TRIAL_RUNNING      | —           | —              | —          | ✓              | ✓    |
| TRIAL_SUCCESS      | ✓           | ✓              | ✓          | —              | ✓    |
| TRIAL_TIMEOUT      | ✓           | ✓              | ✓          | —              | ✓    |


- **Stop** is enabled only when **run is active** (same as “not IDLE” when a session has been started).
- **Manual Success** is enabled only in **TRIAL_RUNNING**.

---

## 2. What happens when the user clicks each button?

(Only states where the button is enabled are listed.)

### Start trial


| State         | Action                                                                                                                 |
| ------------- | ---------------------------------------------------------------------------------------------------------------------- |
| IDLE          | Ensure state machine; call `start_iti()`; start run timer. Status: "Trial session started. Use Next trial when ready." |
| TRIAL_SUCCESS | Call `_on_stop_run()` (stop timer, state → IDLE). Status: "Returned to idle."                                          |
| TRIAL_TIMEOUT | Same as TRIAL_SUCCESS.                                                                                                 |


### Previous trial

**Rule:** Only changes trial index (and thus exit # / animal for that trial). Never starts the run timer or a trial.


| State          | Action                                                                                                                     |
| -------------- | -------------------------------------------------------------------------------------------------------------------------- |
| (no SM) / IDLE | Ensure SM; `go_back_one_trial()` (decrement trial index or stay at 0). Status: "Moved to {session} {trial}."               |
| TRIAL_SUCCESS  | `go_back_one_trial()` (index only; state may go to IDLE or stay). Status: "Went back one trial; now in ITI." (if not IDLE) |
| TRIAL_TIMEOUT  | Same as TRIAL_SUCCESS.                                                                                                     |


### Next trial

**Rule:** Only changes trial index (and thus exit # / animal for that trial). Never starts the run timer or a trial.


| State         | Action                                                                                                                     |
| ------------- | -------------------------------------------------------------------------------------------------------------------------- |
| IDLE          | `advance_to_next_trial()` (index only). If more: "Moved to {session} {trial}."; else "Session complete (end of sessions)." |
| TRIAL_SUCCESS | `advance_to_next_trial()` (index only). "Next trial." or "Session complete."                                               |
| TRIAL_TIMEOUT | Same as TRIAL_SUCCESS.                                                                                                     |


*(When Next is disabled — ITI, WAIT_NOT_CENTER, TRIAL_RUNNING — handler still runs if called: WAIT_NOT_CENTER shows "Trial starts when rodent leaves center."; others "Wait for ITI or trial end.")*

### Manual Success (End trial)


| State         | Action                                                                                  |
| ------------- | --------------------------------------------------------------------------------------- |
| TRIAL_RUNNING | `manual_trial_success()` → state TRIAL_SUCCESS. Status: "Trial ended (manual success)." |


### Stop


| When             | Action                                             |
| ---------------- | -------------------------------------------------- |
| Run active (any) | Stop run timer; set state to IDLE; refresh labels. |


---

## 3. Code locations


| Concern                      | Where                                      |
| ---------------------------- | ------------------------------------------ |
| Enable/disable all 5 buttons | `_update_run_button_states()` (~line 1257) |
| Start clicked                | `_on_start_trial()` (~1366)                |
| Previous clicked             | `_on_previous_trial()` (~1384)             |
| Next clicked                 | `_on_next_trial()` (~1395)                 |
| Manual Success clicked       | `_on_end_trial()` (~810)                   |
| Stop clicked                 | `_on_stop_run()` (~1357)                   |


After editing this doc, update `_update_run_button_states()` for enable rules and the corresponding `_on_`* handlers for actions.