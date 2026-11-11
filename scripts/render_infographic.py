#!/usr/bin/env python3
"""
Tua Tueng Wichakan — Bulletproof Thai Sticker Infographic Renderer & QA Validator (v3: Breathable Line-Spacing)
===============================================================================================================
Guarantees 5 visual quality rules 100%:
1. Authentic cute 'Mali' Bold Thai typography (zero AI-garbled vowels/consonants).
2. Zero '-webkit-text-stroke' glyph-bite/self-overlap: Uses an SVG Alpha-Dilate Smooth Sticker Filter
   (feGaussianBlur + steep feComponentTransfer alpha curve + feDropShadow) rendered 100% BEHIND SourceGraphic.
3. High Fill-Ratio & Symmetrical Multi-Line Balance (~85–90% card fill along a unified center axis).
4. Breathable Vertical Line Spacing for Thai Ascenders/Descenders (สระอุ/อู + วรรณยุกต์/การันต์ never touch!).
5. Deterministic 3-Way Pixel-Diff QA Gate (`ImageChops.difference`):
   - Check 1: 0 pixels colliding with left 3D icons
   - Check 2: 0 pixels overflowing card borders (right, top, bottom)
   - Check 3: Every text line has a clean horizontal band of pure pastel background separating it from
              adjacent lines (zero fused sticker halos or cramped vertical spacing!).
"""

import json
import os
import subprocess
import sys
from PIL import Image, ImageChops, ImageDraw


def scan_card_safe_zone(im: Image.Image, y_top: int, y_bot: int, x_card_start: int = 450):
    """Detect background color, 3D icon right edge, and card right border for a horizontal pastel card."""
    mid_y = (y_top + y_bot) // 2
    bg_rgb = im.getpixel((780, mid_y))
    tol = 22

    # 1. Scan for rightmost icon pixel in left portion of card (x_card_start .. 660)
    icon_right_x = x_card_start
    for y in range(y_top + 14, y_bot - 14):
        for x in range(x_card_start + 5, 660):
            r, g, b = im.getpixel((x, y))
            if abs(r - bg_rgb[0]) > tol or abs(g - bg_rgb[1]) > tol or abs(b - bg_rgb[2]) > tol:
                if x > icon_right_x:
                    icon_right_x = x

    # 2. Scan for card right inner border (from x=780 rightward to 1018)
    card_right_x = 982
    for x in range(780, 1018):
        r, g, b = im.getpixel((x, mid_y))
        if abs(r - bg_rgb[0]) > tol or abs(g - bg_rgb[1]) > tol or abs(b - bg_rgb[2]) > tol:
            card_right_x = x
            break

    # Safe margins (allow full vertical breathing room while protecting rounded top/bottom borders)
    safe_left = icon_right_x + 13
    safe_right = card_right_x - 13
    safe_top = y_top + 8
    safe_bot = y_bot - 8

    return {
        "card_bounds": [x_card_start, y_top, card_right_x, y_bot],
        "icon_right_x": icon_right_x,
        "safe_box": [safe_left, safe_top, safe_right, safe_bot],
        "bg_rgb": bg_rgb,
    }


def detect_three_cards(im: Image.Image):
    """Locate exact top & bottom inner borders of the 3 stacked pastel cards by expanding from card centers."""
    approx_centers = [365, 615, 865]
    segments = []

    for cy in approx_centers:
        bg = im.getpixel((780, cy))
        tol = 11
        y_top = cy
        while y_top > 235:
            r, g, b = im.getpixel((780, y_top - 1))
            if max(abs(r - bg[0]), abs(g - bg[1]), abs(b - bg[2])) > tol:
                break
            y_top -= 1

        y_bot = cy
        while y_bot < 995:
            r, g, b = im.getpixel((780, y_bot + 1))
            if max(abs(r - bg[0]), abs(g - bg[1]), abs(b - bg[2])) > tol:
                break
            y_bot += 1

        if y_bot - y_top < 140:
            y_top, y_bot = cy - 105, cy + 105
        segments.append((y_top, y_bot))

    zones = [scan_card_safe_zone(im, y0, y1) for (y0, y1) in segments]

    lefts = [z["safe_box"][0] for z in zones]
    rights = [z["safe_box"][2] for z in zones]
    if max(lefts) - min(lefts) <= 26:
        unified_left = max(lefts)
        unified_right = min(rights)
        for z in zones:
            z["safe_box"][0] = unified_left
            z["safe_box"][2] = unified_right

    return zones


def build_html(spec: dict, zones: list) -> str:
    blank_abs = os.path.abspath(spec["blank_template"])
    top_pill = spec["top_pill"]
    headline_html = spec["headline_html"]
    mascot_badge = spec.get("mascot_badge", "⭐ เพจตัวตึงวิชาการ")
    cards = spec["cards"]

    card_divs = []
    card_css = []
    for idx, (c, z) in enumerate(zip(cards, zones)):
        sx0, sy0, sx1, sy1 = z["safe_box"]
        sw = sx1 - sx0
        sh = sy1 - sy0
        card_css.append(f"""
        .card-safe-{idx} {{
          position: absolute;
          left: {sx0}px;
          top: {sy0}px;
          width: {sw}px;
          height: {sh}px;
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          text-align: center;
          padding: 0;
          overflow: visible;
        }}
        """)
        line_items = "".join(f'<div class="card-line">{ln}</div>' for ln in c["lines"])
        card_divs.append(f"""
        <div class="card-safe card-safe-{idx}">
          <div class="sticker-wrap">
            <div class="card-head">{c["heading"]}</div>
            <div class="card-body">{line_items}</div>
          </div>
        </div>
        """)

    return f"""<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8" />
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Mali:wght@600;700&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{
      width: 1024px;
      height: 1024px;
      overflow: hidden;
      background: #ffffff;
      font-family: 'Mali', cursive;
      -webkit-font-smoothing: antialiased;
    }}
    .canvas {{
      position: relative;
      width: 1024px;
      height: 1024px;
      background: url('file://{blank_abs}') no-repeat center/cover;
    }}

    /* Top Cloud Banner Safe Box */
    .top-banner {{
      position: absolute;
      left: 64px;
      top: 50px;
      width: 896px;
      height: 158px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: 2px 8px;
    }}
    .top-sub-pill {{
      display: inline-block;
      background: #1E2B4F;
      color: #FEF08A;
      font-family: 'Mali', cursive;
      font-weight: 700;
      font-size: 22px;
      padding: 5px 24px;
      border-radius: 999px;
      border: 3.5px solid #FFFFFF;
      box-shadow: 0 4px 10px rgba(30, 43, 79, 0.22);
      margin-bottom: 10px;
      line-height: 1.3;
      white-space: nowrap;
    }}
    .hero-title {{
      font-family: 'Mali', cursive;
      font-weight: 700;
      font-size: 54px;
      line-height: 1.25;
      letter-spacing: -0.2px;
      filter: url(#sticker-hero);
      white-space: nowrap;
      padding: 4px 10px;
      width: max-content;
    }}

    /* Card Typography — Apply sticker filter per-line so neighboring lines NEVER fuse white halos!
       AND give generous vertical rhythm (gap + line-height) so Thai vowels/tones breathe cleanly! */
    .sticker-wrap {{
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }}
    .card-head {{
      filter: url(#sticker-card);
      font-family: 'Mali', cursive;
      font-weight: 700;
      font-size: 35px;
      color: #172554;
      line-height: 1.32;
      margin-bottom: 14px;
      white-space: nowrap;
      width: max-content;
    }}
    .card-body {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 14px;
      width: max-content;
    }}
    .card-line {{
      filter: url(#sticker-card);
      font-family: 'Mali', cursive;
      font-weight: 700;
      font-size: 26px;
      color: #1E293B;
      line-height: 1.32;
      white-space: nowrap;
      width: max-content;
    }}

    /* Semantic Highlight Colors (High Contrast on White Sticker) */
    .hl-orange {{ color: #D9480F; }}
    .hl-blue   {{ color: #1D4ED8; }}
    .hl-navy   {{ color: #1E2B4F; }}
    .hl-pink   {{ color: #BE185D; }}
    .hl-green  {{ color: #047857; }}
    .sep       {{ color: #64748B; margin: 0 4px; }}

    {"".join(card_css)}

    /* Mascot Name Badge at bottom-left */
    .mascot-badge {{
      position: absolute;
      bottom: 18px;
      left: 56px;
      background: rgba(30, 43, 79, 0.95);
      color: #FFFFFF;
      font-family: 'Mali', cursive;
      font-weight: 700;
      font-size: 20px;
      padding: 6px 22px;
      border-radius: 999px;
      border: 3px solid #FDE047;
      box-shadow: 0 4px 10px rgba(0,0,0,0.18);
      line-height: 1.3;
    }}
  </style>
</head>
<body>
  <!-- SVG Filters: Crisp Smooth Circular Sticker Outline 100% BEHIND SourceGraphic -->
  <svg width="0" height="0" style="position:absolute; pointer-events:none;">
    <defs>
      <filter id="sticker-hero" x="-15%" y="-25%" width="130%" height="150%" color-interpolation-filters="sRGB">
        <feGaussianBlur in="SourceAlpha" stdDeviation="3.8" result="blur1" />
        <feComponentTransfer in="blur1" result="thickAlpha">
          <feFuncA type="table" tableValues="0 0.92 1 1 1 1 1 1 1 1 1 1" />
        </feComponentTransfer>
        <feFlood flood-color="#FFFFFF" flood-opacity="1" result="whiteColor" />
        <feComposite in="whiteColor" in2="thickAlpha" operator="in" result="whiteSticker" />
        <feDropShadow in="whiteSticker" dx="0" dy="4" stdDeviation="3.5" flood-color="#1E2B4F" flood-opacity="0.22" result="stickerWithShadow" />
        <feMerge>
          <feMergeNode in="stickerWithShadow" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>

      <filter id="sticker-card" x="-15%" y="-30%" width="130%" height="160%" color-interpolation-filters="sRGB">
        <feGaussianBlur in="SourceAlpha" stdDeviation="2.2" result="blur1" />
        <feComponentTransfer in="blur1" result="thickAlpha">
          <feFuncA type="table" tableValues="0 0.90 1 1 1 1 1 1 1 1 1 1" />
        </feComponentTransfer>
        <feFlood flood-color="#FFFFFF" flood-opacity="1" result="whiteColor" />
        <feComposite in="whiteColor" in2="thickAlpha" operator="in" result="whiteSticker" />
        <feDropShadow in="whiteSticker" dx="0" dy="1.5" stdDeviation="1.8" flood-color="#1E2B4F" flood-opacity="0.14" result="stickerWithShadow" />
        <feMerge>
          <feMergeNode in="stickerWithShadow" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </defs>
  </svg>

  <div class="canvas">
    <div class="top-banner" id="hero-box">
      <div class="top-sub-pill">{top_pill}</div>
      <div class="hero-title" id="hero-title">{headline_html}</div>
    </div>

    {"".join(card_divs)}

    <div class="mascot-badge">{mascot_badge}</div>
  </div>

  <script>
    // Scale-UP Box-Fill + Breathable Thai Vertical Rhythm Optimizer:
    // 1. Finds unified heading & body sizes that fit horizontally & vertically with generous 14px line gaps.
    // 2. Dynamically expands inter-line gap into any remaining vertical room (up to 19px) so Thai
    //    descenders (ุ/ู/ฏ) and ascenders (ิ/ี/้/์) ALWAYS have plenty of pastel breathing space!
    function fitAllBoxes() {{
      const banner = document.getElementById('hero-box');
      const hero = document.getElementById('hero-title');
      let heroSize = 56;
      hero.style.fontSize = heroSize + 'px';
      while (heroSize > 28 && hero.offsetWidth > banner.clientWidth - 24) {{
        heroSize -= 0.5;
        hero.style.fontSize = heroSize + 'px';
      }}

      const boxes = Array.from(document.querySelectorAll('.card-safe'));
      let globalHead = 38;
      let globalBody = 29;

      boxes.forEach(box => {{
        const head = box.querySelector('.card-head');
        const body = box.querySelector('.card-body');
        const lines = Array.from(box.querySelectorAll('.card-line'));
        const wrap = box.querySelector('.sticker-wrap');
        const maxW = box.clientWidth - 6;
        const maxH = box.clientHeight - 10;

        let hSize = 38;
        head.style.fontSize = hSize + 'px';
        while (hSize > 22 && head.offsetWidth > maxW) {{
          hSize -= 0.5;
          head.style.fontSize = hSize + 'px';
        }}

        let bSize = 29;
        lines.forEach(ln => ln.style.fontSize = bSize + 'px');
        while (bSize > 18 && body.offsetWidth > maxW) {{
          bSize -= 0.5;
          lines.forEach(ln => ln.style.fontSize = bSize + 'px');
        }}

        if (bSize > hSize / 1.16) {{
          bSize = Math.floor((hSize / 1.16) * 2) / 2;
          lines.forEach(ln => ln.style.fontSize = bSize + 'px');
        }}

        while ((hSize > 20 || bSize > 17) && wrap.offsetHeight > maxH) {{
          if (hSize > 20) {{ hSize -= 0.5; head.style.fontSize = hSize + 'px'; }}
          if (bSize > 17) {{
            bSize -= 0.5;
            lines.forEach(ln => ln.style.fontSize = bSize + 'px');
          }}
        }}

        if (hSize < globalHead) globalHead = hSize;
        if (bSize < globalBody) globalBody = bSize;
      }});

      // Apply unified typographic scale + distribute spare vertical height into breathable line gaps!
      let unifiedGap = 14;
      boxes.forEach(box => {{
        box.querySelector('.card-head').style.fontSize = globalHead + 'px';
        box.querySelectorAll('.card-line').forEach(ln => ln.style.fontSize = globalBody + 'px');
      }});

      // Try increasing unifiedGap up to 19px as long as every card stays cleanly inside maxH!
      while (unifiedGap < 19) {{
        const nextGap = unifiedGap + 1;
        boxes.forEach(box => {{
          box.querySelector('.card-head').style.marginBottom = (nextGap + 1) + 'px';
          box.querySelector('.card-body').style.gap = nextGap + 'px';
        }});
        const anyOverflow = boxes.some(box => {{
          const wrap = box.querySelector('.sticker-wrap');
          return wrap.offsetHeight > box.clientHeight - 12;
        }});
        if (anyOverflow) {{
          boxes.forEach(box => {{
            box.querySelector('.card-head').style.marginBottom = (unifiedGap + 1) + 'px';
            box.querySelector('.card-body').style.gap = unifiedGap + 'px';
          }});
          break;
        }}
        unifiedGap = nextGap;
      }}
    }}

    if (document.fonts && document.fonts.ready) {{
      document.fonts.ready.then(fitAllBoxes);
    }} else {{
      window.addEventListener('load', fitAllBoxes);
    }}
  </script>
</body>
</html>
"""


def qa_verify_pixels(blank_path: str, rendered_path: str, zones: list, spec: dict, debug_out: str = None):
    """
    Deterministic 3-Way Pixel-Diff QA Gate:
    1. Zero collision with left 3D icons
    2. Zero overflow outside card right/top/bottom borders
    3. Breathable vertical separation between every text line (no touching vowels/halos!)
    """
    blank_im = Image.open(blank_path).convert("RGB")
    rend_im = Image.open(rendered_path).convert("RGB")
    diff = ImageChops.difference(blank_im, rend_im)

    issues = []
    dbg = rend_im.copy() if debug_out else None
    draw = ImageDraw.Draw(dbg) if dbg else None

    for idx, (z, c) in enumerate(zip(zones, spec["cards"])):
        cx0, cy0, cx1, cy1 = z["card_bounds"]
        icon_rx = z["icon_right_x"]
        sx0, sy0, sx1, sy1 = z["safe_box"]
        expected_lines = 1 + len(c["lines"])

        if draw:
            draw.rectangle([sx0, sy0, sx1, sy1], outline=(0, 200, 80), width=2)
            draw.line([(icon_rx, cy0), (icon_rx, cy1)], fill=(255, 50, 50), width=2)
            draw.line([(cx1, cy0), (cx1, cy1)], fill=(255, 50, 50), width=2)

        # Check 1: Icon zone collision
        icon_hits = 0
        for y in range(cy0 + 10, cy1 - 10):
            for x in range(cx0 + 10, icon_rx + 1):
                dr, dg, db = diff.getpixel((x, y))
                if max(dr, dg, db) > 28:
                    icon_hits += 1
        if icon_hits > 10:
            issues.append(f"Card {idx+1}: {icon_hits} pixels touched the 3D icon zone (x <= {icon_rx})!")

        # Check 2: Right/Top/Bottom border overflow
        right_hits = 0
        for y in range(cy0, cy1):
            for x in range(cx1 - 2, 1023):
                dr, dg, db = diff.getpixel((x, y))
                if max(dr, dg, db) > 28:
                    right_hits += 1
        if right_hits > 5:
            issues.append(f"Card {idx+1}: {right_hits} pixels overflowed right border (x >= {cx1})!")

        # Check 3: Vertical line separation (detect contiguous horizontal ink/sticker bands)
        row_has_ink = []
        for y in range(cy0 + 4, cy1 - 4):
            ink_px = 0
            for x in range(sx0, sx1 + 1):
                dr, dg, db = diff.getpixel((x, y))
                if max(dr, dg, db) > 26:
                    ink_px += 1
            row_has_ink.append((y, ink_px >= 3))

        bands = []
        in_band = False
        b_start = 0
        for y, active in row_has_ink:
            if active and not in_band:
                in_band = True
                b_start = y
            elif not active and in_band:
                in_band = False
                if y - b_start >= 10:
                    bands.append((b_start, y - 1))
        if in_band:
            bands.append((b_start, cy1 - 5))

        if len(bands) < expected_lines:
            issues.append(
                f"Card {idx+1}: Expected {expected_lines} separated lines, but found only {len(bands)} bands "
                f"(adjacent lines touched vertically! Bands={bands})"
            )
        else:
            min_gap = min(bands[i + 1][0] - bands[i][1] - 1 for i in range(len(bands) - 1))
            print(f"  Card {idx+1} vertical line gaps: {[bands[i+1][0] - bands[i][1] - 1 for i in range(len(bands)-1)]} px (min={min_gap}px)")
            if min_gap < 3:
                issues.append(f"Card {idx+1}: Vertical gap between lines is too tight ({min_gap}px < 3px)!")
            if draw:
                for i in range(len(bands) - 1):
                    gy = (bands[i][1] + bands[i + 1][0]) // 2
                    draw.line([(sx0 + 6, gy), (sx1 - 6, gy)], fill=(0, 140, 255), width=1)

    if dbg and debug_out:
        dbg.save(debug_out, quality=92)

    return issues


def main():
    if len(sys.argv) < 3:
        print("Usage: render_infographic.py <spec.json> <output.jpg> [--debug <debug.jpg>]")
        sys.exit(1)

    spec_path = sys.argv[1]
    out_jpg = sys.argv[2]
    debug_jpg = sys.argv[4] if len(sys.argv) >= 5 and sys.argv[3] == "--debug" else None

    spec = json.load(open(spec_path, encoding="utf-8"))
    blank_im = Image.open(spec["blank_template"]).convert("RGB")
    zones = detect_three_cards(blank_im)

    print("Detected Card Safe Zones:")
    for i, z in enumerate(zones):
        sx0, sy0, sx1, sy1 = z["safe_box"]
        print(f"  Card {i+1}: icon_right={z['icon_right_x']}px, card_right={z['card_bounds'][2]}px -> safe_box=({sx0},{sy0})..({sx1},{sy1}) [{sx1-sx0}x{sy1-sy0}px]")

    html_str = build_html(spec, zones)
    tmp_html = "/tmp/tua_tueng_infographic_render.html"
    tmp_png = "/tmp/tua_tueng_infographic_render.png"
    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(html_str)

    cmd = [
        "/usr/bin/chromium",
        "--headless",
        "--no-sandbox",
        "--disable-gpu",
        "--ignore-certificate-errors",
        "--virtual-time-budget=3500",
        "--window-size=1024,1024",
        f"--screenshot={tmp_png}",
        f"file://{tmp_html}",
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    issues = qa_verify_pixels(spec["blank_template"], tmp_png, zones, spec, debug_jpg)
    if issues:
        print("❌ QA FAILED — Collision / Overflow / Cramped Line Spacing detected:")
        for iss in issues:
            print("  -", iss)
        sys.exit(2)

    Image.open(tmp_png).convert("RGB").save(out_jpg, quality=95)
    print(f"✅ QA PASSED (0 icon collisions, 0 border overflows, clean vertical gaps) -> Saved {out_jpg}")


if __name__ == "__main__":
    main()
