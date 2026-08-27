# PROTOTYPE bout HMM — notes

**Question:** Does a bout-sequence sticky HMM produce behavior epochs that feel more coherent than mapping each raw syllable through prototype HDBSCAN clusters?

**Default trial:** `3394/S02/T07` (anatomical / seed 042, 137 bouts, 14 syllables, ITI + run)

**Run:**
```powershell
uv run python scratch/kpms_ensemble_compare/prototype_bout_hmm_tui.py
```

Override trial:
```powershell
uv run python scratch/kpms_ensemble_compare/prototype_bout_hmm_tui.py --trial-key 3243/S01/T01
```

## Verdict (provisional — sweep on default trial, 2026-06-24)

**Short answer:** Yes, bout-level sticky HMM is plausible as the primary behavior-token generator. Prototype clustering looks like a useful **alignment / compression** layer, not the ethogram itself.

### What the numbers showed (`3394/S02/T07`, 137 bouts)

| Layer | Boundaries | Notes |
|-------|------------|-------|
| Raw syllable | 132 | Almost every bout flips — too chatty for behavior |
| Prototype cluster | 53 | 3 clusters on 14 syllables — already a coarse pass |
| Bout HMM (kin only, K=3–4, κ≈8–20) | 32–64 | Speed-separated states; κ controls smoothness |

HMM state mean speeds sorted ~**0.03 / 0.08 / 0.17 / 0.27–0.35 m/s** — maps cleanly to still / slow / fast without naming syllables.

- **κ↑** → fewer HMM boundaries (stickier epochs); at κ=20, K=3 → 32 boundaries vs cluster 53.
- **K↑** → more boundaries, approaches syllable chatter at low κ.
- **+ syllable feature** → HMM boundaries align *more* with cluster boundaries (38 vs 30 coincide) — confirms clusters encode syllable identity, not pure kinematics.

### Qualitative (needs TUI pass)

- [ ] Drive TUI — does the hmm row *look* like locomotion epochs when scrubbing bouts?
- [ ] Try a long-ITI outlier trial from `bout_manifest_export_meta.json`
- [ ] Compare to Phase II YAML tiers on decoded state centroids

### Design implication

| Role | Grain | Tool |
|------|-------|------|
| Syllable dictionary (cross-seed) | prototype | HDBSCAN / DTW — keep |
| **Behavior token** | bout sequence | sticky bout HMM / HSMM — promote |
| Locomotion tier | HMM state centroids | YAML rules (Phase II unchanged in spirit) |
| Named behavior | HMM state | Phase III QC |

**Next prototype slice (if pursuing):** categorical emission HMM — state emits *distribution* over syllable ids, formalizing “syllable 12 appears in walk and groom.”

## Files (throwaway)

| File | Keep? |
|------|-------|
| `bout_hmm_logic.py` | Lift if validated |
| `prototype_bout_hmm_tui.py` | Delete |
| `PROTOTYPE_BOUT_HMM_NOTES.md` | Fold into ADR, then delete |
