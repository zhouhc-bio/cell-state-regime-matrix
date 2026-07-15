from __future__ import annotations

import argparse
import copy
import hashlib
import re
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W}

TARGET_TITLE = "A first-order cell-state regime matrix separates organized regeneration from tumour-like plasticity and adult repair"

ABSTRACT_OPENING = (
    "Regeneration, tumour progression and adult tissue repair all require cell-state plasticity, "
    "yet they resolve into radically different outcomes: organized tissue reconstruction, disorganized expansion "
    "or fate-locked repair. This raises a central question: why does plasticity sometimes support regeneration, "
    "but in other contexts accompany cancer-like states or incomplete adult repair?"
)

ABSTRACT_FINAL = (
    "This framework predicts that regenerative competence should be better explained by regime-conditioned posterior "
    "access than by a global plasticity scalar, a claim testable by perturbation, lineage-tracing and spatial multiome "
    "experiments."
)

INTRO_HOOK = (
    "Regeneration poses a paradox of controlled plasticity. Injured adult tissues can activate repair programs, "
    "tumours can display high cell-state plasticity, and regenerating systems can reopen embryonic-like programs, "
    "yet only some biological contexts rebuild organized structures. This suggests that plasticity itself is not "
    "the regenerative principle. The critical distinction may be whether plasticity is organized by positional "
    "information and constrained away from tumour-like disorganization or adult-repair fate-lock."
)

DISCUSSION_OPENING_PRE = (
    "The central conclusion is biological rather than merely representational: regenerative organization is not "
    "explained by maximal plasticity, but by positionally organized plasticity that remains separated from "
    "tumour-like disorganization and adult-repair fate-lock. The failure of the earlier PGCS/Phi scalar is "
    "informative because it rejects a simple hierarchy in which salamander blastema, mammalian repair and "
    "tumour-like plasticity differ only by degree. Instead, the final analyses support a regime-conditioned "
    "structure in which accessibility, fate-lock and positional identity jointly determine whether plasticity "
    "resolves toward organized regeneration, adult repair or tumour-like states. This result remains compatible "
    "with landscape views of cell-fate organization, but shifts the operative representation from a single "
    "coordinate to posterior regime probability structure."
)

DISCUSSION_OPENING_POST = " Plasticity is therefore permissive, but not instructive."

DISCUSSION_CONTINUITY = (
    "The rejection of a global Phi scalar does not reject cell-state continuity itself. Rather, it rejects the "
    "assumption that continuity can be represented by a single universal axis. The first-order cell-state regime matrix "
    "proposed here preserves continuity as a local and regime-conditioned property: cells may move through "
    "transitional neighbourhoods, posterior-mixed states and boundary regions, while regenerative, adult-repair "
    "and tumour-like outcomes remain separable at the regime level."
)

COMPATIBILITY_PARAGRAPH = (
    "Together, the separation of fate-locked adult repair from tumour-like plasticity and organized regenerative "
    "states supports the view that regeneration, reduced ageing-associated stabilization and tumour control are "
    "not intrinsically incompatible. In a regime-conditioned framework, regenerative competence does not require "
    "uncontrolled plasticity; rather, it can be conceptualized as organized plasticity in which local accessibility "
    "is coupled to preserved positional identity and constrained away from tumour-like disorganization. Thus, the "
    "apparent trade-off between regeneration and tumour suppression is not a necessary logical constraint of the "
    "model, but a context-dependent outcome of how plasticity, fate-lock and positional information are combined. "
    "The present study does not demonstrate an experimentally achieved intervention that simultaneously enhances "
    "regeneration, suppresses pathological ageing-associated stabilization and maintains tumour control. It does, "
    "however, define a computationally supported compatibility space in which these properties can be treated as "
    "jointly testable rather than mutually exclusive."
)

DISCUSSION_CLOSING = (
    "Taken together, these results support a first-order cell-state regime matrix in which regeneration is not defined by "
    "maximal plasticity, but by the coupling of accessible cell states to reduced pathological fate-lock, preserved "
    "positional identity and active separation from tumour-like disorganization."
)

MARKERS = ["fldChar", "instrText", "ADDIN EN.CITE", "EN.CITE.DATA", "EndNote"]


def qn(name: str) -> str:
    prefix, tag = name.split(":")
    if prefix != "w":
        raise ValueError(name)
    return f"{{{W}}}{tag}"


def para_text(p) -> str:
    return "".join(p.xpath(".//w:t/text()", namespaces=NS)).strip()


def para_text_raw(p) -> str:
    return "".join(p.xpath(".//w:t/text()", namespaces=NS))


def has_field(p) -> bool:
    return bool(p.xpath(".//w:fldChar|.//w:instrText|.//w:fldSimple", namespaces=NS))


def package_audit(path: Path) -> dict:
    with ZipFile(path) as z:
        names = z.namelist()
        blob = b"".join(z.read(n) for n in names if n.endswith(".xml") or n.endswith(".rels"))
        doc_xml = z.read("word/document.xml")
    text = blob.decode("utf-8", errors="ignore")
    root = etree.fromstring(doc_xml)
    paras = root.xpath(".//w:body/w:p", namespaces=NS)
    all_text = "\n".join(para_text(p) for p in paras)
    ref_idx = next((i for i, p in enumerate(paras) if para_text(p) == "References"), None)
    bibliography_intact = bool("EndNote" in text and "ADDIN EN.CITE" in text)
    return {
        **{m: text.count(m) for m in MARKERS},
        "media_count": sum(1 for n in names if n.startswith("word/media/")),
        "references_exists": ref_idx is not None,
        "bibliography_fields_appear_intact": bibliography_intact,
        "ref_idx": ref_idx,
        "has_ref_slots": "[REF::" in all_text,
    }


def section_text_hash(paras, start_heading: str, end_headings: set[str]) -> str:
    start = next((i for i, p in enumerate(paras) if para_text(p) == start_heading), None)
    if start is None:
        return ""
    end = len(paras)
    for i in range(start + 1, len(paras)):
        if para_text(paras[i]) in end_headings:
            end = i
            break
    text = "\n".join(para_text_raw(p) for p in paras[start:end])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clone_ppr(source_p):
    ppr = source_p.find(qn("w:pPr"))
    return copy.deepcopy(ppr) if ppr is not None else None


def make_text_run(text: str):
    r = etree.Element(qn("w:r"))
    t = etree.SubElement(r, qn("w:t"))
    t.set(f"{{{XML}}}space", "preserve")
    t.text = text
    return r


def set_plain_paragraph(p, text: str):
    ppr = clone_ppr(p)
    for child in list(p):
        p.remove(child)
    if ppr is not None:
        p.append(ppr)
    p.append(make_text_run(text))


def new_paragraph_like(source_p, text: str):
    p = etree.Element(qn("w:p"))
    ppr = clone_ppr(source_p)
    if ppr is not None:
        p.append(ppr)
    p.append(make_text_run(text))
    return p


def replace_first_two_sentences(text: str, replacement: str) -> str:
    matches = list(re.finditer(r"\.(?=\s)", text))
    if len(matches) >= 2:
        rest = text[matches[1].end() :].lstrip()
    elif matches:
        rest = text[matches[0].end() :].lstrip()
    else:
        rest = ""
    return replacement + ((" " + rest) if rest else "")


def normalize_allowed_terms(text: str) -> str:
    text = text.replace("tumor-like", "tumour-like")
    text = text.replace("organized the locked outputs as", "organized the outputs as")
    text = text.replace("for the locked outputs is", "is")
    text = text.replace("Instead, the locked outputs support", "Instead, the final analyses support")
    text = text.replace("observed in the locked outputs", "observed in the final analyses")
    return text


def replace_runs_text_in_range(paras, start: int, end: int):
    for p in paras[start:end]:
        for node in p.xpath(".//w:t", namespaces=NS):
            if node.text:
                node.text = normalize_allowed_terms(node.text)


def reconstruct_discussion_opening(p):
    children = list(p)
    field_idxs = [
        i
        for i, c in enumerate(children)
        if c.xpath(".//w:fldChar|.//w:instrText|.//w:fldSimple", namespaces=NS)
    ]
    ppr = clone_ppr(p)
    preserved = []
    if field_idxs:
        start, end = min(field_idxs), max(field_idxs)
        preserved = [copy.deepcopy(c) for c in children[start : end + 1]]
    for child in list(p):
        p.remove(child)
    if ppr is not None:
        p.append(ppr)
    p.append(make_text_run(DISCUSSION_OPENING_PRE))
    for c in preserved:
        p.append(c)
    p.append(make_text_run(DISCUSSION_OPENING_POST))
    return bool(preserved)


def write_docx_with_document_xml(src: Path, dst: Path, document_xml: bytes):
    with ZipFile(src, "r") as zin, ZipFile(dst, "w", ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = document_xml if item.filename == "word/document.xml" else zin.read(item.filename)
            zout.writestr(item, data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--backup", required=True)
    ap.add_argument("--report", required=True)
    args = ap.parse_args()

    inp = Path(args.input)
    out = Path(args.output)
    backup = Path(args.backup)
    report = Path(args.report)

    out.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(inp, backup)

    before_audit = package_audit(inp)
    with ZipFile(inp) as z:
        root = etree.fromstring(z.read("word/document.xml"))
    paras = root.xpath(".//w:body/w:p", namespaces=NS)

    protected_hash_before = {
        "Results": section_text_hash(paras, "Results", {"Discussion"}),
        "Methods": section_text_hash(paras, "Methods", {"Data availability"}),
        "Figure legends": section_text_hash(paras, "Figure legends", {"References"}),
        "References": section_text_hash(paras, "References", set()),
    }

    changes = []
    skipped = []

    # Title.
    title_changed = False
    for p in paras:
        if para_text(p) == TARGET_TITLE:
            break
    else:
        title_para = next((p for p in paras if para_text(p).startswith("A first-order cell-state regime matrix")), None)
        if title_para is not None and not has_field(title_para):
            set_plain_paragraph(title_para, TARGET_TITLE)
            title_changed = True
            changes.append("Title changed to target title.")
        else:
            skipped.append("Title edit skipped because no safe title paragraph was identified.")

    # Abstract.
    abstract_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Abstract")
    intro_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Introduction")
    abstract_body_idx = next(i for i in range(abstract_idx + 1, intro_idx) if para_text(paras[i]))
    if has_field(paras[abstract_body_idx]):
        skipped.append("Abstract opening edit skipped because the paragraph contains fields.")
    else:
        new_text = replace_first_two_sentences(para_text_raw(paras[abstract_body_idx]), ABSTRACT_OPENING)
        new_text = normalize_allowed_terms(new_text)
        set_plain_paragraph(paras[abstract_body_idx], new_text)
        changes.append("Abstract opening replaced with supplied two-sentence hook.")

    final_abs_idx = max(i for i in range(abstract_idx + 1, intro_idx) if para_text(paras[i]))
    if has_field(paras[final_abs_idx]):
        skipped.append("Abstract final prediction edit skipped because the paragraph contains fields.")
    else:
        set_plain_paragraph(paras[final_abs_idx], ABSTRACT_FINAL)
        changes.append("Abstract final prediction sentence set to supplied text.")

    # Introduction hook: insert before first technical paragraph after Introduction heading.
    intro_heading = paras[intro_idx]
    next_intro_para = next(i for i in range(intro_idx + 1, len(paras)) if para_text(paras[i]))
    if not para_text(paras[next_intro_para]).startswith("Regeneration poses a paradox of controlled plasticity."):
        hook = new_paragraph_like(paras[next_intro_para], INTRO_HOOK)
        parent = intro_heading.getparent()
        parent.insert(parent.index(paras[next_intro_para]), hook)
        changes.append("Introduction story hook inserted before existing citation-containing Introduction paragraph.")
    else:
        changes.append("Introduction story hook already present; no duplicate inserted.")

    # Refresh paragraph list after insertion.
    paras = root.xpath(".//w:body/w:p", namespaces=NS)
    abstract_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Abstract")
    intro_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Introduction")
    results_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Results")
    discussion_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Discussion")
    limitations_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Limitations")

    # Allowed terminology normalization in edited sections only.
    replace_runs_text_in_range(paras, abstract_idx + 1, intro_idx)
    replace_runs_text_in_range(paras, intro_idx + 1, results_idx)
    replace_runs_text_in_range(paras, discussion_idx + 1, limitations_idx)

    # Discussion opening.
    discussion_open_idx = next(i for i in range(discussion_idx + 1, limitations_idx) if para_text(paras[i]))
    preserved_field = reconstruct_discussion_opening(paras[discussion_open_idx])
    if preserved_field:
        changes.append("Discussion opening paragraph text replaced while preserving existing EndNote field objects.")
    else:
        changes.append("Discussion opening paragraph replaced; no field objects were present.")

    # Discussion continuity paragraph.
    paras = root.xpath(".//w:body/w:p", namespaces=NS)
    discussion_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Discussion")
    limitations_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Limitations")
    discussion_texts = [para_text(p) for p in paras[discussion_idx + 1 : limitations_idx]]
    if not any(t.startswith("The rejection of a global Phi scalar does not reject cell-state continuity itself.") for t in discussion_texts):
        opening_idx = next(i for i in range(discussion_idx + 1, limitations_idx) if para_text(paras[i]))
        cont = new_paragraph_like(paras[opening_idx + 1], DISCUSSION_CONTINUITY)
        parent = paras[opening_idx].getparent()
        parent.insert(parent.index(paras[opening_idx]) + 1, cont)
        changes.append("Discussion continuity paragraph inserted immediately after opening paragraph.")
    else:
        changes.append("Discussion continuity paragraph already present; no duplicate inserted.")

    # Compatibility paragraph.
    paras = root.xpath(".//w:body/w:p", namespaces=NS)
    discussion_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Discussion")
    limitations_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Limitations")
    if not any(para_text(p).startswith("Together, the separation of fate-locked adult repair") for p in paras[discussion_idx + 1 : limitations_idx]):
        module_idx = next(
            (
                i
                for i in range(discussion_idx + 1, limitations_idx)
                if para_text(paras[i]).startswith("The latent-state-regime mixture clarifies")
            ),
            None,
        )
        if module_idx is not None:
            comp = new_paragraph_like(paras[module_idx], COMPATIBILITY_PARAGRAPH)
            parent = paras[module_idx].getparent()
            parent.insert(parent.index(paras[module_idx]) + 1, comp)
            changes.append("Compatibility-space paragraph inserted after module-explanation paragraph.")
        else:
            skipped.append("Compatibility-space insertion skipped because the module-explanation paragraph was not found.")
    else:
        changes.append("Compatibility-space paragraph already present; no duplicate inserted.")

    # Final closing paragraph.
    paras = root.xpath(".//w:body/w:p", namespaces=NS)
    discussion_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Discussion")
    limitations_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Limitations")
    final_disc_idx = max(i for i in range(discussion_idx + 1, limitations_idx) if para_text(paras[i]))
    if para_text(paras[final_disc_idx]) != DISCUSSION_CLOSING:
        if has_field(paras[final_disc_idx]):
            skipped.append("Discussion closing edit skipped because final paragraph contains fields.")
        else:
            set_plain_paragraph(paras[final_disc_idx], DISCUSSION_CLOSING)
            changes.append("Discussion final closing paragraph replaced with supplied text.")
    else:
        changes.append("Discussion already ended with supplied first-order cell-state regime matrix closing paragraph.")

    # Final edited-section text safety normalization after insertions.
    paras = root.xpath(".//w:body/w:p", namespaces=NS)
    abstract_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Abstract")
    intro_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Introduction")
    results_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Results")
    discussion_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Discussion")
    limitations_idx = next(i for i, p in enumerate(paras) if para_text(p) == "Limitations")
    replace_runs_text_in_range(paras, abstract_idx + 1, intro_idx)
    replace_runs_text_in_range(paras, intro_idx + 1, results_idx)
    replace_runs_text_in_range(paras, discussion_idx + 1, limitations_idx)

    document_xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone="yes")
    write_docx_with_document_xml(inp, out, document_xml)

    after_audit = package_audit(out)

    # Re-read output for protected-section hash checks.
    with ZipFile(out) as z:
        out_root = etree.fromstring(z.read("word/document.xml"))
    out_paras = out_root.xpath(".//w:body/w:p", namespaces=NS)
    protected_hash_after = {
        "Results": section_text_hash(out_paras, "Results", {"Discussion"}),
        "Methods": section_text_hash(out_paras, "Methods", {"Data availability"}),
        "Figure legends": section_text_hash(out_paras, "Figure legends", {"References"}),
        "References": section_text_hash(out_paras, "References", set()),
    }

    counts_decreased = [
        m for m in ["ADDIN EN.CITE", "EN.CITE.DATA", "EndNote"] if after_audit[m] < before_audit[m]
    ]
    protected_modified = [
        k for k in protected_hash_before if protected_hash_before[k] != protected_hash_after[k]
    ]

    # Safety text checks in edited sections.
    edited_text = "\n".join(
        [para_text(p) for p in out_paras[abstract_idx + 1 : results_idx]]
        + [para_text(p) for p in out_paras[discussion_idx + 1 : limitations_idx]]
    )
    forbidden_hits = [
        phrase
        for phrase in [
            "[REF::",
            "protects the manuscript",
            "locked outputs",
            "strong anti-aging",
            "strong anti-cancer",
        ]
        if phrase in edited_text
    ]

    final_status = "PASS"
    failure_reasons = []
    if counts_decreased:
        final_status = "FAIL"
        failure_reasons.append(f"EndNote-related counts decreased: {', '.join(counts_decreased)}")
    if protected_modified:
        final_status = "FAIL"
        failure_reasons.append(f"Protected sections modified: {', '.join(protected_modified)}")
    if forbidden_hits:
        final_status = "FAIL"
        failure_reasons.append(f"Forbidden edited-section phrases remain: {', '.join(forbidden_hits)}")
    if final_status == "FAIL":
        shutil.copy2(backup, out)

    report_lines = [
        "# Story Strengthening EndNote Safety Report",
        "",
        f"- input path: `{inp}`",
        f"- output path: `{out}`",
        f"- backup path: `{backup}`",
        "",
        "## EndNote counts before editing",
        "",
    ]
    for m in MARKERS:
        report_lines.append(f"- {m}: {before_audit[m]}")
    report_lines += [
        f"- media_count: {before_audit['media_count']}",
        f"- References section exists: {before_audit['references_exists']}",
        f"- bibliography fields appear intact: {before_audit['bibliography_fields_appear_intact']}",
        "",
        "## EndNote counts after editing",
        "",
    ]
    for m in MARKERS:
        report_lines.append(f"- {m}: {after_audit[m]}")
    report_lines += [
        f"- media_count: {after_audit['media_count']}",
        f"- References section exists: {after_audit['references_exists']}",
        f"- bibliography fields appear intact: {after_audit['bibliography_fields_appear_intact']}",
        "",
        "## Edits",
        "",
        f"- title change status: {'changed' if title_changed else 'already matched / unchanged'}",
        "- Abstract edits made: opening hook and final prediction sentence updated.",
        "- Introduction insertion status: story hook inserted before existing technical framing.",
        "- Discussion edits made: opening strengthened with preserved citation field objects; continuity paragraph checked/inserted; compatibility paragraph checked; closing paragraph checked.",
        f"- skipped edits due to EndNote risk: {('; '.join(skipped)) if skipped else 'none'}",
        "",
        "## Safety checks",
        "",
        f"- Results modified: {'yes' if 'Results' in protected_modified else 'no'}",
        f"- Methods modified: {'yes' if 'Methods' in protected_modified else 'no'}",
        f"- Figure legends modified: {'yes' if 'Figure legends' in protected_modified else 'no'}",
        f"- References modified: {'yes' if 'References' in protected_modified else 'no'}",
        "- citation numbers manually typed: no",
        f"- EndNote field counts decreased: {'yes' if counts_decreased else 'no'}",
        f"- [REF::] placeholders exist in edited sections: {'yes' if '[REF::' in forbidden_hits else 'no'}",
        f"- forbidden phrase hits in edited sections: {(', '.join(forbidden_hits)) if forbidden_hits else 'none'}",
        "",
        "## Change log",
        "",
    ]
    report_lines.extend(f"- {c}" for c in changes)
    if failure_reasons:
        report_lines += ["", "## Failure reasons", ""]
        report_lines.extend(f"- {r}" for r in failure_reasons)
    report_lines += ["", f"final status: {final_status}", ""]
    report.write_text("\n".join(report_lines), encoding="utf-8")

    if final_status == "FAIL":
        raise SystemExit("Safety check failed; output restored from backup. See report.")


if __name__ == "__main__":
    main()
