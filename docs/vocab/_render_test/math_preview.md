# Markdown math preview test (KaTeX / VS Code, not TeX Live)

Open this file, then **Markdown: Open Preview** (Ctrl+Shift+V).
TeX Live is **not** used here. Cursor **agent chat** also does **not** use this renderer.

Canonical formulas live in [`../FORMULAS.md`](../FORMULAS.md).

## Inline

Shannon: $H(p) = -\sum_{k:p_k>0} p_k \log_2 p_k$

## Display

$$
T = \min(T^{+}, T^{-}), \qquad
\mu = \frac{n(n+1)}{4}, \qquad
z = \frac{T^{+} - \mu}{\sigma}
$$

## If you see raw `$` and backslashes

Preview math is off or broken. In settings, `markdown.math.enabled` should be `true` (VS Code / Cursor default). That still will not make **agent chat** render LaTeX.
