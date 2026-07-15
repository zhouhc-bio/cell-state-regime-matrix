#!/usr/bin/env python3
from __future__ import annotations

import json
import struct
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree


SCRIPT_DIR = Path(__file__).resolve().parent


def find_project_root() -> Path:
    for candidate in [SCRIPT_DIR.parents[3], SCRIPT_DIR.parents[2], SCRIPT_DIR.parents[1]]:
        if (candidate / "Figure_Redesign_Output").exists() or (candidate / "GitHub_Term_Revised_Package").exists():
            return candidate
    return SCRIPT_DIR.parents[3]


ROOT = find_project_root()
PNG_DIR = ROOT / "Figure_Redesign_Output" / "png"
OUT_DIR = ROOT / "Manuscript_New_Figures"
WIDTH_EMU = 5_715_000

DOCS = [
    ROOT / "A_first-order_cell-state_regime_matrix_MINIMAL_TERM_REVISED.docx",
    ROOT / "A_first-order_cell-state_regime_matrix_TERMINOLOGY_REVISED.docx",
    ROOT / "细胞状态-状态域矩阵_最小术语修订版.docx",
    ROOT / "细胞状态-状态域矩阵_术语重构版.docx",
]

IMAGE_REPLACEMENTS = {
    "media/image1.png": PNG_DIR / "Figure_1A_paradigm_shift_600dpi.png",
    "media/image2.png": PNG_DIR / "Figure_1_framework_icon_600dpi.png",
    "media/image7.png": PNG_DIR / "Figure_6_boundary_branch_600dpi.png",
    "media/image8.png": PNG_DIR / "Figure_7_phi_failure_dashboard_600dpi.png",
    "media/image9.png": PNG_DIR / "Figure_8_posterior_mixture_600dpi.png",
    "media/image10.png": PNG_DIR / "Figure_9_overlap_divergence_600dpi.png",
    "media/image11.png": PNG_DIR / "Supplementary_Figure_1_perturbation_consistency_600dpi.png",
}

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        sig = handle.read(24)
    if sig[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a PNG file: {path}")
    return struct.unpack(">II", sig[16:24])


def field_counts(zip_path: Path) -> dict[str, int]:
    counts = {"fldChar": 0, "instrText": 0, "endnote_cite": 0, "endnote_bib": 0}
    with ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.startswith("word/") or not name.endswith(".xml"):
                continue
            data = zf.read(name)
            counts["fldChar"] += data.count(b"w:fldChar") + data.count(b"<fldChar")
            counts["instrText"] += data.count(b"w:instrText") + data.count(b"<instrText")
            counts["endnote_cite"] += data.count(b"EN.CITE")
            counts["endnote_bib"] += data.count(b"EN.REFLIST") + data.count(b"EN.BIBL")
    return counts


def load_relationship_targets(zf: ZipFile) -> dict[str, str]:
    rel_root = etree.fromstring(zf.read("word/_rels/document.xml.rels"))
    targets: dict[str, str] = {}
    for rel in rel_root.findall(f"{{{REL_NS}}}Relationship"):
        rid = rel.get("Id")
        target = rel.get("Target")
        if rid and target:
            targets[rid] = target
    return targets


def replacement_extents() -> dict[str, tuple[int, int]]:
    extents = {}
    for target, path in IMAGE_REPLACEMENTS.items():
        width, height = png_size(path)
        extents[target] = (WIDTH_EMU, round(WIDTH_EMU * height / width))
    return extents


def update_document_xml(xml_bytes: bytes, rel_targets: dict[str, str], extents: dict[str, tuple[int, int]]) -> tuple[bytes, list[dict[str, object]]]:
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
    root = etree.fromstring(xml_bytes, parser)
    updates: list[dict[str, object]] = []

    for blip in root.xpath(".//a:blip[@r:embed]", namespaces=NS):
        rid = blip.get(f"{{{NS['r']}}}embed")
        target = rel_targets.get(rid or "")
        if target not in extents:
            continue
        cx, cy = extents[target]

        drawing = blip
        while drawing is not None and drawing.tag not in {f"{{{NS['wp']}}}inline", f"{{{NS['wp']}}}anchor"}:
            drawing = drawing.getparent()
        if drawing is not None:
            extent = drawing.find("wp:extent", NS)
            if extent is not None:
                extent.set("cx", str(cx))
                extent.set("cy", str(cy))

        pic = blip
        while pic is not None and pic.tag != f"{{{NS['pic']}}}pic":
            pic = pic.getparent()
        if pic is not None:
            for aext in pic.xpath(".//a:xfrm/a:ext", namespaces=NS):
                aext.set("cx", str(cx))
                aext.set("cy", str(cy))

        updates.append({"rid": rid, "target": target, "cx": cx, "cy": cy})

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=False), updates


def output_name(path: Path) -> Path:
    stem = path.stem
    if any(ord(ch) > 127 for ch in stem):
        return OUT_DIR / f"{stem}_新图版.docx"
    return OUT_DIR / f"{stem}_NEW_FIGURES.docx"


def rewrite_docx(src: Path) -> dict[str, object]:
    dst = output_name(src)
    before_counts = field_counts(src)
    extents = replacement_extents()

    with ZipFile(src, "r") as zin:
        rel_targets = load_relationship_targets(zin)
        doc_xml, updates = update_document_xml(zin.read("word/document.xml"), rel_targets, extents)
        with ZipFile(dst, "w", compression=ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                data = zin.read(info.filename)
                if info.filename == "word/document.xml":
                    data = doc_xml
                elif info.filename.startswith("word/"):
                    target = info.filename.removeprefix("word/")
                    if target in IMAGE_REPLACEMENTS:
                        data = IMAGE_REPLACEMENTS[target].read_bytes()
                zout.writestr(info, data)

    after_counts = field_counts(dst)
    if before_counts != after_counts:
        raise RuntimeError(f"Field count changed for {src.name}: {before_counts} -> {after_counts}")

    return {
        "source": str(src),
        "output": str(dst),
        "field_counts": after_counts,
        "replaced_targets": sorted(IMAGE_REPLACEMENTS),
        "drawing_updates": updates,
    }


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    results = []
    for doc in DOCS:
        if not doc.exists():
            raise FileNotFoundError(doc)
        results.append(rewrite_docx(doc))
    log_path = OUT_DIR / "MANUSCRIPT_FIGURE_REPLACEMENT_LOG.json"
    log_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(results)} manuscripts")
    print(log_path)


if __name__ == "__main__":
    main()
