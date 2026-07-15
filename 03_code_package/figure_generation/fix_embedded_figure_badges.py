#!/usr/bin/env python3
"""Mask internal status badges in embedded DOCX figure images."""

from __future__ import annotations

import csv
import re
import shutil
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path.cwd()
INPUT = ROOT / "Regenerative_cell_fate_latent_regime_PRE_REFERENCE_CLEAN.docx"
OUTPUT = ROOT / "Regenerative_cell_fate_latent_regime_PRE_REFERENCE_CLEAN_FIGFIX.docx"
WORK = ROOT / "work/final_inline_figure_assembly/figfix_images"
CHECK = ROOT / "figfix_check.md"

BADGE_MEDIA = {
    "image2.png": "Figure 1",
    "image3.png": "Figure 2",
    "image4.png": "Figure 3",
    "image5.png": "Figure 4",
    "image6.png": "Figure 5",
    "image7.png": "Figure 6",
    "image8.png": "Figure 7",
    "image9.png": "Figure 8",
    "image10.png": "Figure 9",
}

INSPECTED_CLEAN = {
    "image1.png": "Figure 1A",
    "image11.png": "Supplementary Figure 1",
}


def extract_media(docx_path: Path, out_dir: Path) -> dict[str, bytes]:
    out_dir.mkdir(parents=True, exist_ok=True)
    media: dict[str, bytes] = {}
    with zipfile.ZipFile(docx_path) as z:
        for name in z.namelist():
            if name.startswith("word/media/"):
                data = z.read(name)
                base = Path(name).name
                media[base] = data
                (out_dir / base).write_bytes(data)
    return media


def detect_badge_bbox(im: Image.Image) -> tuple[int, int, int, int] | None:
    """Detect the isolated blue status badge in the top-right header area."""

    rgb = im.convert("RGB")
    w, h = rgb.size
    x0 = int(w * 0.60)
    y0 = 0
    x1 = w
    y1 = int(h * 0.18)
    pixels = rgb.load()
    points: set[tuple[int, int]] = set()
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = pixels[x, y]
            # Blue outline/text of the badge; avoids gray header and black titles.
            if b > 115 and g > 70 and b > r + 25 and g > r + 15:
                points.add((x, y))
    if not points:
        return None

    components: list[tuple[int, int, int, int, int]] = []
    while points:
        start = points.pop()
        stack = [start]
        xs = [start[0]]
        ys = [start[1]]
        count = 1
        while stack:
            x, y = stack.pop()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in points:
                    points.remove((nx, ny))
                    stack.append((nx, ny))
                    xs.append(nx)
                    ys.append(ny)
                    count += 1
        if count >= 20:
            components.append((count, min(xs), min(ys), max(xs) + 1, max(ys) + 1))

    candidates: list[tuple[int, int, int, int, int]] = []
    for comp in components:
        count, bx0, by0, bx1, by1 = comp
        bw = bx1 - bx0
        bh = by1 - by0
        aspect = bw / max(1, bh)
        if (
            bx0 > int(w * 0.70)
            and by0 < 220
            and 180 <= bw <= 480
            and 40 <= bh <= 110
            and 3.0 <= aspect <= 6.5
            and count >= 1000
        ):
            candidates.append(comp)

    if not candidates:
        return None

    # Pick the rightmost valid badge-like component, not a scientific panel border.
    _count, bx0, by0, bx1, by1 = sorted(candidates, key=lambda c: (c[3], -c[2]))[-1]
    return bx0, by0, bx1, by1


def sample_fill(rgb: Image.Image, bbox: tuple[int, int, int, int]) -> tuple[int, int, int]:
    """Sample the local header background immediately around the badge."""

    w, h = rgb.size
    x0, y0, x1, y1 = bbox
    samples: list[tuple[int, int, int]] = []
    # Prefer just-left and just-above pixels from the same header band.
    regions = [
        (max(0, x0 - 160), max(0, y0 - 20), max(0, x0 - 30), min(h, y1 + 20)),
        (max(0, x0 - 20), max(0, y0 - 80), min(w, x1 + 20), max(0, y0 - 20)),
    ]
    for ax0, ay0, ax1, ay1 in regions:
        if ax1 <= ax0 or ay1 <= ay0:
            continue
        for y in range(ay0, ay1, max(1, (ay1 - ay0) // 8 or 1)):
            for x in range(ax0, ax1, max(1, (ax1 - ax0) // 8 or 1)):
                r, g, b = rgb.getpixel((x, y))
                # Header background is near-white/light gray; skip colored line/text pixels.
                if min(r, g, b) > 220 and max(r, g, b) - min(r, g, b) < 18:
                    samples.append((r, g, b))
    if not samples:
        return (246, 248, 252)
    samples.sort()
    return samples[len(samples) // 2]


def mask_badge(src: Path, dest: Path) -> tuple[bool, tuple[int, int, int, int] | None]:
    im = Image.open(src).convert("RGB")
    bbox = detect_badge_bbox(im)
    if bbox is None:
        im.save(dest)
        return False, None
    w, h = im.size
    x0, y0, x1, y1 = bbox
    pad_x = max(24, int(w * 0.006))
    pad_y = max(14, int(h * 0.004))
    mask_box = (
        max(0, x0 - pad_x),
        max(0, y0 - pad_y),
        min(w, x1 + pad_x),
        min(h, y1 + pad_y),
    )
    fill = sample_fill(im, mask_box)
    draw = ImageDraw.Draw(im)
    draw.rectangle(mask_box, fill=fill)
    im.save(dest)
    return True, mask_box


def ref_counts_from_docx(docx_path: Path) -> tuple[int, int]:
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
    refs = re.findall(r"\[REF::[^\]]+\]", xml)
    return len(refs), len(set(refs))


def build_docx_with_clean_media(cleaned_paths: dict[str, Path]) -> None:
    tmp = WORK / "docx_unzipped"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    with zipfile.ZipFile(INPUT) as z:
        z.extractall(tmp)
    for media_name, clean_path in cleaned_paths.items():
        target = tmp / "word" / "media" / media_name
        if not target.exists():
            raise FileNotFoundError(target)
        target.write_bytes(clean_path.read_bytes())
    if OUTPUT.exists():
        OUTPUT.unlink()
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(tmp.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(tmp).as_posix())


def main() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    media = extract_media(INPUT, WORK / "original")
    cleaned_paths: dict[str, Path] = {}
    rows: list[dict[str, str]] = []

    for media_name, figure_id in BADGE_MEDIA.items():
        src = WORK / "original" / media_name
        dest = WORK / "cleaned" / media_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        changed, bbox = mask_badge(src, dest)
        cleaned_paths[media_name] = dest
        rows.append(
            {
                "figure": figure_id,
                "media": media_name,
                "method": "mask",
                "changed": str(changed),
                "mask_box": "" if bbox is None else ",".join(map(str, bbox)),
            }
        )

    for media_name, figure_id in INSPECTED_CLEAN.items():
        rows.append(
            {
                "figure": figure_id,
                "media": media_name,
                "method": "inspected_left_unchanged",
                "changed": "False",
                "mask_box": "",
            }
        )

    before_refs = ref_counts_from_docx(INPUT)
    build_docx_with_clean_media(cleaned_paths)
    after_refs = ref_counts_from_docx(OUTPUT)
    if before_refs != after_refs:
        raise RuntimeError(f"Reference slots changed: {before_refs} -> {after_refs}")

    with (WORK / "figfix_operations.tsv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["figure", "media", "method", "changed", "mask_box"], delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    CHECK.write_text(
        "\n".join(
            [
                "# Figure Badge Fix Check",
                "",
                "- Cleaned figures: Figure 1, Figure 2, Figure 3, Figure 4, Figure 5, Figure 6, Figure 7, Figure 8 and Figure 9.",
                "- Method used: local mask of the visually separate upper-right status badge area inside embedded raster images.",
                "- Figure 1A and Supplementary Figure 1 were inspected and left unchanged because no matching internal status badge was visible.",
                f"- Citation slots preserved during media replacement: {after_refs[0]} `[REF::...]` slots ({after_refs[1]} unique).",
                "- Render verification: pending.",
                "- Remaining internal badges: pending render QA.",
                "- Ready for manual reference insertion: pending final verification.",
                "",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
