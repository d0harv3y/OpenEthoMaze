# Build 5-slide DR-framed motion-seq PPTX via PowerPoint COM (no python-pptx).
# Target shell: Windows PowerShell 5.1+
# UTF-8 no BOM. ASCII punctuation only in this script.
# Ticket: .scratch/dr-framed-motion-seq-deck/issues/08-ship-pptx-and-vault.md

$ErrorActionPreference = "Stop"

$outDir = "C:\Users\admin\Documents\work\davis lab"
$outName = "Motion sequencing NOR - DR framed.pptx"
$outPath = Join-Path $outDir $outName
$root = "D:\sack\datas\impress\moseq_251017\_nor_object_mi"
$deck = Join-Path $root "simpler_first_dr_framed_deck_exemplar"
$classicFigs = Join-Path $root "simpler_first_classic_dr\figures"
$sessFigs = Join-Path $root "simpler_first_session_paired\figures"
$objFigs = Join-Path $root "simpler_first_object_prox_0p10\figures"

# Prefer SVG so PowerPoint "Convert to Shape" / Convert to Object keeps editable paths.
$figA = Join-Path $deck "figures\fig_classic_vs_dr_time_prox_NOR_TX.svg"
$figB = Join-Path $classicFigs "fig_classic_vs_object_prox.svg"
$figC = Join-Path $deck "figures\fig_frac_still_vs_syll5_share.svg"
$figDRich = Join-Path $deck "figures\fig_classic_vs_dr_richness_prox_NOR_TX.svg"
$figDShan = Join-Path $deck "figures\fig_classic_vs_dr_shannon_prox_NOR_TX.svg"
$figDHill = Join-Path $deck "figures\fig_classic_vs_dr_hill2_prox_NOR_TX.svg"
$figEShan = Join-Path $deck "comp_level\figures\fig_exemplar_prox_shannon_violins.svg"
$figERich = Join-Path $deck "comp_level\figures\fig_exemplar_prox_richness_violins.svg"
$figEHill = Join-Path $deck "comp_level\figures\fig_exemplar_prox_hill2_violins.svg"
$figFShan = Join-Path $deck "session_step\figures\fig_exemplar_prox_shannon_session_step_violins.svg"
$figFRich = Join-Path $deck "session_step\figures\fig_exemplar_prox_richness_session_step_violins.svg"
$figFHill = Join-Path $deck "session_step\figures\fig_exemplar_prox_hill2_session_step_violins.svg"
# Session-paired frac_near twin kept on disk (ticket 06 G) but not on slide 3 — slide matches composition ladder.
$figG = Join-Path $sessFigs "fig_session_paired_violin_frac_near.svg"
$figAssay = Join-Path $classicFigs "fig_classic_dr_violin.svg"
$figObjDr = Join-Path $objFigs "fig_object_prox_violin_dr.svg"

function Add-PictureSafe($slide, $path, $left, $top, $width, $height) {
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Host "MISSING figure: $path"
        return $null
    }
    try {
        return $slide.Shapes.AddPicture($path, $false, $true, $left, $top, $width, $height)
    } catch {
        Write-Host ("AddPicture failed for {0}: {1}" -f $path, $_.Exception.Message)
        return $null
    }
}

function Add-Text($slide, $left, $top, $width, $height, $text, $size, $bold = $false) {
    $tb = $slide.Shapes.AddTextbox(1, $left, $top, $width, $height)
    $tr = $tb.TextFrame.TextRange
    $tr.Text = $text
    $tr.Font.Size = $size
    $tr.Font.Name = "Calibri"
    $tr.Font.Bold = $bold
    $tb.TextFrame.WordWrap = $true
    return $tb
}

function New-BlankSlide($pres) {
    return $pres.Slides.Add($pres.Slides.Count + 1, 12)
}

$pp = New-Object -ComObject PowerPoint.Application
$pp.Visible = 1
$pres = $pp.Presentations.Add()
$pres.PageSetup.SlideWidth = 13.333 * 72
$pres.PageSetup.SlideHeight = 7.5 * 72

if ($pres.Slides.Count -eq 1) {
    $t = ""
    try { $t = $pres.Slides.Item(1).Shapes.Title.TextFrame.TextRange.Text } catch { $t = "" }
    if ([string]::IsNullOrWhiteSpace($t)) {
        $pres.Slides.Item(1).Delete()
    }
}

# ----- Slide 1: Assay + clocks -----
$s1 = New-BlankSlide $pres
Add-Text $s1 18 8 920 36 "Assay prefers novel - clocks agree" 28 $true | Out-Null
Add-Text $s1 18 44 920 28 "NOR = novel object recognition; SD = sleep deprivation; kpMS = keypoint-MoSeq; DR = discrimination ratio" 11 $false | Out-Null
$t1 = @(
    "At recognition (NOR_TX), animals prefer novel on classic / object-prox time DR; SD arms do not separate.",
    "",
    "Collinearities (classic <-> object-prox; still <-> pause syll5) validate the assay clocks - not a MoSeq miracle.",
    "",
    "0.10 m exclusive prox. Exemplar model 1e7/3e4/ss100 (raw ids); cross-model consensus mentioned lightly."
) -join "`r"
Add-Text $s1 18 72 300 150 $t1 13 $false | Out-Null
Add-PictureSafe $s1 $figAssay 18 230 300 250 | Out-Null
Add-PictureSafe $s1 $figB 330 230 300 250 | Out-Null
Add-PictureSafe $s1 $figC 640 120 300 300 | Out-Null
Add-Text $s1 18 490 920 40 "Left: classic DR. Mid: classic <-> object-prox. Right: frac_still <-> pause syll5 (color=condition, shape=sex)." 11 $false | Out-Null

# ----- Slide 1b: Composition formula cheat (COUNT / UNCERTAINTY; no conditional entropy) -----
$s1b = New-BlankSlide $pres
Add-Text $s1b 18 8 920 32 "Composition ladder - COUNT / UNCERTAINTY" 26 $true | Out-Null
Add-Text $s1b 18 44 920 40 ("p = composition (shares sum to 1). Pose frame-share: p_k = (frames labeled k) / (window frames). Logs = bits (base 2). " +
    "These are descriptive (D) scalars on one alphabet - not investigation time / DR.") 12 $false | Out-Null
# rows x cols: header + 3 metrics; 4 columns
$tbl = $s1b.Shapes.AddTable(4, 4, 18, 100, 920, 320).Table
$headers = @("Metric", "Token", "Formula", "Read")
$r1 = @("Category count", "richness", "S = # { k : p_k > 0 }", "How many labels appear in the window")
$r2 = @("Abundance uncertainty (entropy)", "shannon_bits", "H(p) = - sum p_k log2(p_k)   |   Hill-1: 1D = 2^H", "Bits of uncertainty about which label under this one p (not variance; not MI)")
$r3 = @("Dominance / Hill q=2", "hill2_eff", "lambda = sum p_k^2   |   2D = 1 / lambda", "Effective # of abundant labels (dominance-weighted); charted as hill2")
$rows = @($headers, $r1, $r2, $r3)
for ($i = 0; $i -lt 4; $i++) {
    for ($j = 0; $j -lt 4; $j++) {
        $cell = $tbl.Cell($i + 1, $j + 1)
        $tr = $cell.Shape.TextFrame.TextRange
        $tr.Text = [string]$rows[$i][$j]
        $tr.Font.Name = "Calibri"
        $tr.Font.Size = if ($i -eq 0) { 14 } else { 12 }
        $tr.Font.Bold = ($i -eq 0)
    }
}
# column widths (points)
$tbl.Columns.Item(1).Width = 200
$tbl.Columns.Item(2).Width = 110
$tbl.Columns.Item(3).Width = 340
$tbl.Columns.Item(4).Width = 270
$t1b = @(
    "Deck uses DR cousins of these scalars in exclusive 0.10 m fam|nvl balls (next slides): dr_richness / dr_shannon / dr_hill2.",
    "Conditional entropy H(Y|X) / transitions are out of this deck - see vocab FORMULAS.md TRANSITION."
) -join "`r"
Add-Text $s1b 18 440 920 70 $t1b 12 $false | Out-Null

# ----- Slide 2: Composition DR -----
$s2 = New-BlankSlide $pres
Add-Text $s2 18 8 920 36 "Composition DR cousins (richness -> Shannon -> Hill q=2)" 26 $true | Out-Null
$t2 = @(
    "Near-object richness / Shannon / Hill q=2 (dominance) ask about repertoire / uncertainty / effective # motifs - not investigation time.",
    "Assay litmus passes in controls; condition FDR fails under sex-stratified per-scalar BH (and under sealed m=2 F+M bags) - exemplar raw alphabet."
) -join "`r"
Add-Text $s2 18 48 920 70 $t2 13 $false | Out-Null
Add-PictureSafe $s2 $figERich 18 130 300 280 | Out-Null
Add-PictureSafe $s2 $figEShan 330 130 300 280 | Out-Null
Add-PictureSafe $s2 $figEHill 640 130 300 280 | Out-Null
$t2b = @(
    "Delta Shannon ~ change in bits to describe syllable occupancy proportions in fam vs nvl balls - not 'memory quality' unless joined.",
    "vs classic DR @ NOR_TX: richness collinear (rho~0.73); Shannon and Hill2 are not (rho~0 / ~0)."
) -join "`r"
Add-Text $s2 18 420 920 90 $t2b 12 $false | Out-Null

# ----- Slide 3: Session steps (L->R richness, Shannon/entropy, Hill2/dominance; match slide 2) -----
$s3 = New-BlankSlide $pres
Add-Text $s3 18 8 920 36 "Session steps - protocol Delta, not condition modulation" 26 $true | Out-Null
$t3 = @(
    "Same composition questions on BL -> TX -> REC paired Deltas (no trial-steps).",
    "Protocol dynamics move; condition modulation on these scalars is null/thin."
) -join "`r"
Add-Text $s3 18 48 920 55 $t3 13 $false | Out-Null
Add-PictureSafe $s3 $figFRich 18 120 300 300 | Out-Null
Add-PictureSafe $s3 $figFShan 330 120 300 300 | Out-Null
Add-PictureSafe $s3 $figFHill 640 120 300 300 | Out-Null
Add-Text $s3 18 440 920 50 "Exemplar prox session-step (raw alphabet): richness | Shannon (entropy) | Hill q=2 (dominance). Same ladder as slide 2." 11 $false | Out-Null

# ----- Slide 4: Can / cannot -----
$s4 = New-BlankSlide $pres
Add-Text $s4 18 8 920 36 "What we can / cannot claim" 28 $true | Out-Null
$t4 = @(
    "CAN: assay works at NOR_TX; clocks concord (classic / object-prox; still / pause syll5); composition preference in controls (assay litmus).",
    "CANNOT: recognition-linked SD lock from these scalars; clinical meaning of composition-DR unknown (show, don't sell).",
    "Gloss: when Shannon / richness / Hill2 rise near novel, repertoire is broader / less concentrated - interesting, not sold as impairment."
) -join "`r"
Add-Text $s4 18 48 920 70 $t4 13 $false | Out-Null
Add-PictureSafe $s4 $figDRich 18 130 300 280 | Out-Null
Add-PictureSafe $s4 $figDShan 330 130 300 280 | Out-Null
Add-PictureSafe $s4 $figDHill 640 130 300 280 | Out-Null
Add-Text $s4 18 420 920 50 "Classic DR vs composition cousins @ NOR_TX (L->R richness | Shannon/entropy | Hill2/dominance). Color=condition, shape=sex." 11 $false | Out-Null

# ----- Slide 5: Future -----
$s5 = New-BlankSlide $pres
Add-Text $s5 18 8 920 36 "Future directions" 28 $true | Out-Null
$t5 = @(
    "Not next: residual litmus. Regressing speed / immobile / frac_near off syllable scores and hunting leftover condition hits is a sealed null - and explaining it with formula walls is how you lose the room. Residual = leftover after declared covariates; it is not a new clock.",
    "",
    "Next bets:",
    "",
    "1. Different clocks - not more ProxComp cuts on the same near-object time mass.",
    "2. B-SOiD (behavioral segmentation of open-field in DeepLabCut) as an alternate segmenter.",
    "3. Self-supervised learning (SSL) on video - leJEPA, DINO, SimCLR (sandbox: C:\Users\admin\code\lightly).",
    "   Idea: skip pose estimation / keypoint-MoSeq as the middleman. Today the stack is",
    "   video -> keypoints -> syllable labels -> behavior. SSL can learn frame/clip embeddings",
    "   straight from pixels and segment behavior in that embedding space - fewer fragile",
    "   handoffs (tracking dropouts, alphabet fit choices) between the network and the ethogram.",
    "",
    "Lab-internal. Exemplar model paramscan_s1-1e7_s2-3e4_ss-100; consensus is a light cross-check only."
) -join "`r"
Add-Text $s5 18 48 620 430 $t5 13 $false | Out-Null
Add-PictureSafe $s5 $figObjDr 650 300 280 170 | Out-Null

if (Test-Path -LiteralPath $outPath) {
    Remove-Item -LiteralPath $outPath -Force
}
$pres.SaveAs($outPath)
$n = $pres.Slides.Count
$pres.Close()
$pp.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($pres) | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($pp) | Out-Null
[GC]::Collect()
[GC]::WaitForPendingFinalizers()

Write-Host ("Wrote {0} slides -> {1}" -f $n, $outPath)
Get-Item -LiteralPath $outPath | Format-List FullName, Length, LastWriteTime
