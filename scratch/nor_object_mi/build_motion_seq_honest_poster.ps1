# Build mini-poster PPTX via PowerPoint COM (no python-pptx).
# Target shell: Windows PowerShell 5.1+
# UTF-8 no BOM. ASCII punctuation only in this script.

$ErrorActionPreference = "Stop"

$outDir = "C:\Users\admin\Documents\work\davis lab"
$outName = "Motion sequencing in NOR - honest report.pptx"
$outPath = Join-Path $outDir $outName
$root = "D:\sack\datas\impress\moseq_251017\_nor_object_mi"

$figDr = Join-Path $root "simpler_first_object_prox_0p10\figures\fig_object_prox_violin_dr.png"
$figClock = Join-Path $root "simpler_first_ambulation_clocks\figures\fig_clock_association.png"
$figC13 = Join-Path $root "simpler_first_da\fig_cluster13_condition_delta.png"
$figStill = Join-Path $root "slides_pack\frac_still\figures\fig_frac_still_by_sex.svg"
$figC13Share = Join-Path $root "slides_pack\cluster13\figures\fig_cluster13_frame_share_by_sex.svg"
$figShannon = Join-Path $root "slides_pack\shannon\figures\fig_shannon_level_by_sex.svg"

function Add-TitleSlide($pres, $title, $subtitle) {
    $slide = $pres.Slides.Add($pres.Slides.Count + 1, 1)
    $slide.Shapes.Title.TextFrame.TextRange.Text = $title
    if ($slide.Shapes.Count -ge 2) {
        $slide.Shapes.Item(2).TextFrame.TextRange.Text = $subtitle
    }
    return $slide
}

function Add-BulletSlide($pres, $title, [string[]]$bullets) {
    $slide = $pres.Slides.Add($pres.Slides.Count + 1, 2)
    $slide.Shapes.Title.TextFrame.TextRange.Text = $title
    $body = $slide.Shapes.Placeholders.Item(2)
    $body.TextFrame.TextRange.Text = ($bullets -join "`r")
    $body.TextFrame.TextRange.ParagraphFormat.Bullet.Visible = $true
    $body.TextFrame.TextRange.Font.Size = 20
    $slide.Shapes.Title.TextFrame.TextRange.Font.Size = 30
    return $slide
}

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

$pp = New-Object -ComObject PowerPoint.Application
$pp.Visible = 1
$pres = $pp.Presentations.Add()
$pres.PageSetup.SlideWidth = 13.333 * 72
$pres.PageSetup.SlideHeight = 7.5 * 72

# Delete default empty slide if present (some PPT versions start with one)
if ($pres.Slides.Count -eq 1) {
    $t = ""
    try { $t = $pres.Slides.Item(1).Shapes.Title.TextFrame.TextRange.Text } catch { $t = "" }
    if ([string]::IsNullOrWhiteSpace($t)) {
        $pres.Slides.Item(1).Delete()
    }
}

Add-TitleSlide $pres `
    "Motion sequencing in NOR (IMPRESS)" `
    ("What we can honestly say about keypoint-MoSeq (kpMS)`r" +
     "Pilot synthesis - 2026-10-05`r" +
     "NOR = novel object recognition; SD = sleep deprivation; DR = discrimination ratio") | Out-Null

Add-BulletSlide $pres "Two clocks - different questions" @(
    "Classic: threshold + debounce / object-prox gates answer where and how much the animal moves (and near objects).",
    "kpMS syllables: which reusable pose motifs, and in what order.",
    "Thin context: assay works at NOR_TX; classic DR x condition is null; male engagement Delta is occupancy - not a MoSeq insight.",
    "Full claim map: Obsidian NOR IMPRESS Index. This deck is motion sequencing only."
) | Out-Null

$s3 = Add-BulletSlide $pres "Layer A - expected concordance (V and V, not insight)" @(
    "Object-prox DR vs syllable-prox DR: preference / near-object clocks agree across segmenters.",
    "Time still / frac_still vs pause cluster (fit-local cluster_id 13 on the 251017 pack).",
    "Why expected: MoSeq as a fancier occupancy machine rediscovers the engagement clock (collinearity).",
    "Useful instrument check. Does not answer memory or physio."
)
Add-PictureSafe $s3 $figDr 20 360 280 150 | Out-Null
Add-PictureSafe $s3 $figClock 320 360 280 150 | Out-Null
Add-PictureSafe $s3 $figC13 620 360 280 150 | Out-Null

$s4 = $pres.Slides.Add($pres.Slides.Count + 1, 12)
$tb = $s4.Shapes.AddTextbox(1, 20, 15, 920, 45)
$tb.TextFrame.TextRange.Text = "Stillness clock vs pause cluster (same story, two segmenters)"
$tb.TextFrame.TextRange.Font.Size = 26
$tb.TextFrame.TextRange.Font.Bold = $true
Add-PictureSafe $s4 $figStill 30 70 430 360 | Out-Null
Add-PictureSafe $s4 $figC13Share 500 70 430 360 | Out-Null
$cap = $s4.Shapes.AddTextbox(1, 20, 450, 920, 60)
$cap.TextFrame.TextRange.Text = "Left: frac_still (ambulation clock). Right: cluster13 frame-share. Cluster ids are fit-local (ADR-0005)."
$cap.TextFrame.TextRange.Font.Size = 14

$s5 = Add-BulletSlide $pres "Composition / inventory - rediscovery, no recognition lock" @(
    "Shannon / richness / Bray-Curtis / DA / cluster frame-share chart protocol dynamics (BL to TX to REC; object steps).",
    "They do not lock a recognition-linked SD separator.",
    "Sell carefully: session shifts are easy to oversell as memory. Layer B - not preference."
)
Add-PictureSafe $s5 $figShannon 500 150 400 280 | Out-Null

Add-BulletSlide $pres "Sequence structure - fairly tested, clean null" @(
    "Syllables can ask what debounce cannot: P(next|current), H(next|current), n-gram MI / richness.",
    "TransStruct-A at NOR_TX x nvl_obj: 0/4 FDR, 0/4 uncorrected (TV + conditional entropy).",
    "NGramSeq-A (fixed-budget pair MI + bigram richness): 0/4 FDR; cross-campaign exploratory empty.",
    "TV hits that vanish under fixed transition budgets = bout-count confound (snake), not grammar.",
    "No Family B without a new contract. Locked negatives stay lava."
) | Out-Null

Add-BulletSlide $pres "Conclusions - what we can / cannot claim" @(
    "CAN: Instrument check passed - kpMS reproduces movement / proximity / stillness clocks.",
    "CAN: Composition decks support protocol-story slides; not a MoSeq preference claim.",
    "CAN: Sequence bet lost so far under declared families.",
    "CANNOT: That latent sequencing found recognition-linked SD effects DR missed.",
    "CANNOT: That raw syllable / cluster ids are portable across models."
) | Out-Null

Add-BulletSlide $pres "Future directions" @(
    "Residual litmus: after regressing speed / immobile / frac_near, do syllable scores still separate arms?",
    "New sequence definitions only under contract - no Family B on TransStruct / NGramSeq without user OK.",
    "Define investigation quality before more alphabet or per-animal accent fishing.",
    "Stop occupancy fishing as a career - the negative result is a product.",
    "Vault source of truth: Motion Sequencing Honest Report (openethomaze vault)."
) | Out-Null

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
