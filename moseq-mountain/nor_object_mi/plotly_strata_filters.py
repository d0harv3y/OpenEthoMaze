"""Shared HTML checkbox filters for Plotly 3D syllable clouds (scratch).

Each trace must carry ``meta``::

    {"tag": feature_set, "sex": ..., "condition": ..., "session": ..., "trial": ...}

Empty string means that stratum is absent on the row. Checkboxes gate visibility
together with the feature-set dropdown (``data-tag``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import plotly.graph_objects as go

SESSION_ORDER: tuple[str, ...] = ("NOR_BL", "NOR_TX", "NOR_REC3hr", "NOR_REC11hr")
TRIAL_ORDER: tuple[str, ...] = ("nvl_obj", "id_obj", "no_obj")
SEX_ORDER: tuple[str, ...] = ("F", "M")


def _checkbox_group(title: str, name: str, values: Sequence[str]) -> str:
    if not values:
        return (
            f'<div class="filt-group"><div class="filt-title">{title}</div>'
            f'<div class="filt-muted">not on this table</div></div>'
        )
    boxes = []
    for v in values:
        vid = f"{name}_{v}".replace(" ", "_")
        boxes.append(
            f'<label><input type="checkbox" class="filt" data-dim="{name}" '
            f'data-val="{v}" id="{vid}" checked> {v}</label>'
        )
    return (
        f'<div class="filt-group"><div class="filt-title">{title}</div>'
        + "".join(boxes)
        + "</div>"
    )


def write_html_with_strata_filters(
    fig: go.Figure,
    out_html: Path,
    *,
    tags: Sequence[str],
    tag_labels: Sequence[str] | None = None,
    sexes: Sequence[str],
    conditions: Sequence[str],
    sessions: Sequence[str],
    trials: Sequence[str],
    title_html: str,
    subtitle_html: str,
    color_note: str,
) -> None:
    """Write full HTML: feature-set select + strata checkboxes + Plotly div."""
    out_html.parent.mkdir(parents=True, exist_ok=True)
    plot_div = fig.to_html(
        include_plotlyjs="cdn",
        full_html=False,
        div_id="strata3d",
        config={"displayModeBar": True, "responsive": True},
    )
    labels = list(tag_labels) if tag_labels is not None else list(tags)
    options = "".join(
        f'<option value="{t}">{lab}</option>' for t, lab in zip(tags, labels, strict=True)
    )
    meta_payload = {
        "tags": list(tags),
        "n_traces": len(fig.data),
    }
    css = """
    body { font-family: DejaVu Sans, Segoe UI, sans-serif; margin: 0; background: #fafafa; color: #222; }
    #bar { display: flex; flex-wrap: wrap; gap: 1rem; padding: 0.6rem 1rem;
           border-bottom: 1px solid #ddd; background: #fff; align-items: flex-start; }
    .filt-group { font-size: 12px; }
    .filt-title { font-weight: 600; margin-bottom: 0.25rem; }
    .filt-muted { color: #888; font-style: italic; }
    .filt-group label { display: block; margin: 0.1rem 0; cursor: pointer; }
    #titleblock { padding: 0.5rem 1rem 0; }
    #titleblock h1 { font-size: 16px; margin: 0 0 0.2rem; font-weight: 600; }
    #titleblock .sub { font-size: 12px; color: #555; margin: 0; }
    #strata3d { width: 100%; height: calc(100vh - 140px); }
    select#tagSelect { font-size: 13px; min-width: 16rem; }
    """
    js = f"""
    const META = {json.dumps(meta_payload)};
    function checked(dim) {{
      const boxes = document.querySelectorAll('input.filt[data-dim="'+dim+'"]');
      if (!boxes.length) return null;  // stratum absent → do not gate
      return new Set([...boxes].filter(b => b.checked).map(b => b.dataset.val));
    }}
    function applyFilters() {{
      const gd = document.getElementById('strata3d');
      if (!gd || !gd.data) return;
      const tag = document.getElementById('tagSelect').value;
      const sex = checked('sex');
      const cond = checked('condition');
      const sess = checked('session');
      const trial = checked('trial');
      const vis = gd.data.map(tr => {{
        const m = tr.meta || {{}};
        if (m.tag !== tag) return false;
        if (sex && m.sex && !sex.has(String(m.sex))) return false;
        if (cond && m.condition && !cond.has(String(m.condition))) return false;
        if (sess && m.session && !sess.has(String(m.session))) return false;
        if (trial && m.trial && !trial.has(String(m.trial))) return false;
        return true;
      }});
      Plotly.restyle(gd, {{visible: vis}});
    }}
    document.addEventListener('DOMContentLoaded', () => {{
      document.getElementById('tagSelect').addEventListener('change', applyFilters);
      document.querySelectorAll('input.filt').forEach(b => b.addEventListener('change', applyFilters));
      // wait a tick for Plotly to attach
      setTimeout(applyFilters, 50);
    }});
    """
    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"/>
<title>PCA 3D strata filters</title>
<style>{css}</style>
</head><body>
<div id="titleblock">
  <h1>{title_html}</h1>
  <p class="sub">{subtitle_html}<br/>{color_note}</p>
</div>
<div id="bar">
  <div class="filt-group">
    <div class="filt-title">feature set</div>
    <select id="tagSelect">{options}</select>
  </div>
  {_checkbox_group("sex", "sex", sexes)}
  {_checkbox_group("condition (tx)", "condition", conditions)}
  {_checkbox_group("session", "session", sessions)}
  {_checkbox_group("trial (object step)", "trial", trials)}
</div>
{plot_div}
<script>{js}</script>
</body></html>
"""
    out_html.write_text(html, encoding="utf-8")
    print(f"wrote {out_html}", flush=True)


def ordered_present(values: Sequence[Any], preferred: Sequence[str]) -> list[str]:
    have = {str(v) for v in values if v is not None and str(v) not in ("", "nan")}
    out = [p for p in preferred if p in have]
    for v in sorted(have):
        if v not in out:
            out.append(v)
    return out
