from __future__ import annotations

import csv
import re
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
DOC1 = ROOT / "work" / "Doc1.docx"

OLD_FIG_ROOT = Path("/Volumes/T9/nature_reviewer_alignment_outputs/submission_reproducibility_package_FINAL/02_figures")
OLD_FIG_FINAL = Path("/Volumes/T9/nature_reviewer_alignment_outputs/final_figures")
OLD_SOURCE_V3 = Path("/Volumes/T9/PGCS/figure_reconstruction_v3/source_data")
OLD_SOURCE_ARCHIVE = Path("/Volumes/T9/PGCS/submission_archive_v1/03_figure_source_data")
EXTENDED_DPRI_ROOT = Path("/Users/hanchengdezhuanqiangongju/Documents/细胞命运通路研究/FINAL_NATURE_SUBMISSION_MASTER_ARCHIVE/02_FINAL_FIGURES")
EXTENDED_DPRI_SOURCE = Path("/Users/hanchengdezhuanqiangongju/Documents/细胞命运通路研究/FINAL_NATURE_SUBMISSION_MASTER_ARCHIVE/03_SOURCE_DATA/panel_level_tsv/Extended_Data_Fig_1_DPRI_source_data.tsv")

NEW_LOCK = OUT / "final_figures_locked"


def yes(path: Path) -> str:
    return "YES" if path.exists() else "NO"


def write_tsv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def parse_docx_figures() -> tuple[dict[str, dict[str, str]], int]:
    """Return caption text keyed by old figure id plus embedded image count."""
    ns = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    figures: dict[str, dict[str, str]] = {}
    embedded = 0
    with ZipFile(DOC1) as z:
        relroot = ET.fromstring(z.read("word/_rels/document.xml.rels"))
        rels = {rel.attrib["Id"]: rel.attrib["Target"] for rel in relroot}
        root = ET.fromstring(z.read("word/document.xml"))
        body = root.find("w:body", ns)
        paras: list[tuple[int, str, list[str]]] = []
        assert body is not None
        for i, p in enumerate(body.findall("w:p", ns)):
            txt = "".join(t.text or "" for t in p.findall(".//w:t", ns)).strip()
            rids = []
            for blip in p.findall(".//a:blip", ns):
                rid = blip.attrib.get(f"{{{ns['r']}}}embed") or blip.attrib.get(f"{{{ns['r']}}}link")
                if rid:
                    rids.append(rid)
            if rids:
                embedded += len(rids)
                target = ";".join(rels.get(r, "") for r in rids)
                figures[f"_image_para_{i}"] = {"doc1_paragraph_index": str(i), "doc1_media_target": target}
            if txt:
                paras.append((i, txt, rids))

    # Match captions to the preceding image paragraph. Caption paragraphs in this file directly follow images.
    image_positions = sorted(
        (int(k.split("_")[-1]), v["doc1_media_target"]) for k, v in figures.items() if k.startswith("_image_para_")
    )
    for i, txt, _ in paras:
        m = re.match(r"^(Figure\s+\d+|Extended Data Fig\.\s*1)\s*\|\s*(.*)", txt)
        if not m:
            continue
        fig_id = m.group(1)
        image_before = max((x for x in image_positions if x[0] < i), default=("", ""))
        figures[fig_id] = {
            "caption": txt,
            "doc1_paragraph_index": str(i),
            "doc1_media_target": str(image_before[1]),
        }
    return figures, embedded


def _glob_clean(base: Path, pattern: str) -> list[Path]:
    if not base.exists():
        return []
    return sorted(p for p in base.glob(pattern) if not p.name.startswith("._"))


def panel_sources(fig_num: int) -> str:
    files: list[Path] = []
    for base in [OLD_SOURCE_V3, OLD_SOURCE_ARCHIVE]:
        files.extend(_glob_clean(base, f"Figure_{fig_num}_panel_*_source_data.tsv"))
    return "; ".join(str(p) for p in files[:12])


def old_panel_sources(fig_num: int) -> str:
    """Map Doc1's nine-figure numbering to the older source-data numbering."""
    files: list[Path] = []
    if fig_num in {2, 3, 4}:
        for base in [OLD_SOURCE_V3, OLD_SOURCE_ARCHIVE]:
            files.extend(_glob_clean(base, f"Figure_{fig_num}_panel_*_source_data.tsv"))
    elif fig_num == 5:
        files.extend(_glob_clean(OLD_SOURCE_V3, "Figure_5_true_result4_fate_stabilization_lineage_restriction_panel_*_source_data.tsv"))
        if not files:
            for base in [OLD_SOURCE_V3, OLD_SOURCE_ARCHIVE]:
                files.extend(_glob_clean(base, "Figure_5_panel_*_source_data.tsv"))
    elif fig_num == 6:
        files.extend(_glob_clean(OLD_SOURCE_V3, "Figure_6_SAT_mammalian_repair_failure_panel_*_source_data.tsv"))
    elif fig_num == 7:
        # Axolotl was Figure 6 in the earlier 8-figure source-data package.
        for base in [OLD_SOURCE_V3, OLD_SOURCE_ARCHIVE]:
            files.extend(_glob_clean(base, "Figure_6_panel_*_source_data.tsv"))
    elif fig_num == 8:
        # Tumor-like plasticity was Figure 7 in the earlier source-data package.
        for base in [OLD_SOURCE_V3, OLD_SOURCE_ARCHIVE]:
            files.extend(_glob_clean(base, "Figure_7_panel_*_source_data*.tsv"))
    elif fig_num == 9:
        files.extend(_glob_clean(Path("/Volumes/T9/PGCS/figure_reconstruction_v3/Figure_9_integrated_fate_divergence_model/reports"), "Figure_9_generation_report.md"))
        files.extend(_glob_clean(Path("/Volumes/T9/PGCS/figure_reconstruction_v3/Figure_9_integrated_fate_divergence_model/audit"), "Figure_9_text_inventory.tsv"))
    return "; ".join(str(p) for p in files[:16])


def old_asset_paths(fig_num: int) -> tuple[str, str, str]:
    if fig_num == 9:
        stem = "Figure_9_final_short_title"
    else:
        stem = f"Figure_{fig_num}_final"
    png = OLD_FIG_ROOT / "png_600dpi" / f"{stem}_600dpi.png"
    pdf = OLD_FIG_ROOT / "pdf" / f"{stem}.pdf"
    svg = OLD_FIG_ROOT / "svg" / f"{stem}.svg"
    if not png.exists():
        png = OLD_FIG_FINAL / f"{stem}.png"
    if not pdf.exists():
        pdf = OLD_FIG_FINAL / f"{stem}.pdf"
    if not svg.exists():
        svg = OLD_FIG_FINAL / f"{stem}.svg"
    return str(png), str(pdf), str(svg)


def build_old_inventory(figures: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    specs = [
        (1, "Evidence architecture for divergent outcomes of injury-induced cell plasticity", "Introduction/Result 1", "conceptual + evidence map", "conceptual", "Plasticity is permissive and outcome depends on positional, fate-stabilization and tissue organization layers.", "VALID_WITH_REVISION", "NO", "NO", "MERGE_MAIN", "MEDIUM", "Merge into conceptual anchor; replace deterministic fate-divergence language with latent-state-regime mixture framing."),
        (2, "Shared high-plasticity state space and divergent inferred-retention properties", "Result 1", "scRNA/scVelo/CellRank/module scores", "empirical", "Regenerative, senescence-like and tumor-like groups occupy a connected high-plasticity accessibility space.", "VALID_WITH_REVISION", "YES", "YES", "KEEP_MAIN", "LOW", "State explicitly that connected state-space regions do not imply fate equivalence or direct lineage."),
        (3, "Stemness-associated programs increase accessibility but do not specify outcome", "Result 2", "perturbation/module-score/boundary analyses", "empirical", "Wnt/stemness programs increase accessibility but do not determine fate outcome.", "VALID", "YES", "YES", "KEEP_MAIN", "LOW", "Keep; avoid deterministic stemness-to-regeneration wording."),
        (4, "Developmental positional-program activity is associated with regenerative plasticity", "Result 3", "RA/RARG perturbation + axolotl positional proxies", "empirical", "RA/HOX/DPRI-like positional programs associate with regenerative plasticity.", "VALID_WITH_REVISION", "YES", "YES", "MERGE_MAIN", "MEDIUM", "Merge with axolotl/blastema figure; interpret as regime-conditioned developmental coordinate, not universal determinant."),
        (5, "Fate-stabilization and lineage-restriction programs restrict high-plasticity trajectories", "Result 4", "module scores + CellRank/velocity + perturbation-linked validation", "empirical", "Fate-stabilization and lineage-restriction restrict accessible trajectories.", "VALID_WITH_REVISION", "YES", "YES", "MERGE_MAIN", "MEDIUM", "Merge with SAT/adult repair figure; avoid direct BMP/p53 causal overstatement."),
        (6, "A proposed Senescence Amplification Trap branch captures mammalian repair-failure features", "Result 5", "senescence retention + cross-system score comparison", "empirical + conceptual", "SAT-like mammalian repair failure is supported as a branch, not a universal aging law.", "VALID_WITH_REVISION", "YES", "YES", "MERGE_MAIN", "MEDIUM", "Frame as adult-repair/fate-lock-biased latent-state-regime mixture; no universal aging law claim."),
        (7, "Axolotl regeneration shows that high plasticity can retain positional-program activity", "Result 6", "axolotl expression-layer proxies + pseudotime/module scores", "empirical", "Axolotl blastema retains positional-program activity during regenerative plasticity.", "VALID_WITH_REVISION", "YES", "YES", "MERGE_MAIN", "MEDIUM", "Do not call blastema simply high Phi or higher plasticity; use distinct latent regenerative regime wording."),
        (8, "Tumor-like plasticity is a distinct operational high-plasticity branch rather than embryonic reversion", "Result 7", "tumor-like proxy analyses + boundary comparisons", "empirical", "Tumor-like plasticity is distinct from embryonic regeneration and inflammatory repair equivalence.", "VALID", "YES", "YES", "KEEP_MAIN", "LOW", "Keep as separate branch; do not imply embryonic reversion."),
        (9, "Integrated developmental fate-divergence model of injury-induced plasticity", "Result 8", "conceptual synthesis", "conceptual", "Integrated model links plasticity, positional programs, fate stabilization, SAT and tumor-like branch.", "PARTLY_SUPERSEDED", "NO", "NO", "REBUILD_REQUIRED", "HIGH", "Use only after rebuilding around latent-state-regime mixture; remove any single-order-parameter or deterministic hierarchy interpretation."),
    ]
    rows: list[dict[str, object]] = []
    for fig_num, title, section, data_type, kind, claim, valid, data_bound, source_avail, status, risk, fix in specs:
        key = f"Figure {fig_num}"
        png, pdf, svg = old_asset_paths(fig_num)
        rows.append(
            {
                "old_figure_number": key,
                "caption": figures.get(key, {}).get("caption", title),
                "result_section": section,
                "data_type": data_type,
                "empirical_or_conceptual": kind,
                "current_claim": claim,
                "whether_the_claim_remains_valid_under_latent_regime_mixture_model": valid,
                "data_bound_yes_no": data_bound,
                "source_data_available_yes_no": source_avail,
                "recommended_status": status,
                "risk_level": risk,
                "required_fix": fix,
                "doc1_media_target": figures.get(key, {}).get("doc1_media_target", ""),
                "doc1_caption_paragraph_index": figures.get(key, {}).get("doc1_paragraph_index", ""),
                "old_png_asset": png,
                "old_pdf_asset": pdf,
                "old_svg_asset": svg,
                "panel_source_data_files": old_panel_sources(fig_num),
            }
        )
    rows.append(
        {
            "old_figure_number": "Extended Data Fig. 1",
            "caption": figures.get("Extended Data Fig. 1", {}).get("caption", "Frog compartment boundary analysis of developmental-program reactivation."),
            "result_section": "Extended Data / DPRI boundary",
            "data_type": "frog compartment DPRI source data",
            "empirical_or_conceptual": "empirical + boundary schematic",
            "current_claim": "Frog compartment DPRI is context- and compartment-dependent; it is not a cross-species regenerative capacity ranking.",
            "whether_the_claim_remains_valid_under_latent_regime_mixture_model": "VALID_WITH_REVISION",
            "data_bound_yes_no": "YES" if EXTENDED_DPRI_SOURCE.exists() else "NO",
            "source_data_available_yes_no": yes(EXTENDED_DPRI_SOURCE),
            "recommended_status": "MOVE_SUPPLEMENTARY",
            "risk_level": "LOW",
            "required_fix": "Keep as supplementary boundary evidence; do not use to rank species or define a global DPRI/Phi axis.",
            "doc1_media_target": figures.get("Extended Data Fig. 1", {}).get("doc1_media_target", ""),
            "doc1_caption_paragraph_index": figures.get("Extended Data Fig. 1", {}).get("doc1_paragraph_index", ""),
            "old_png_asset": str(EXTENDED_DPRI_ROOT / "PNG" / "Extended_Data_Fig_1_DPRI.png"),
            "old_pdf_asset": str(EXTENDED_DPRI_ROOT / "PDF" / "Extended_Data_Fig_1_DPRI.pdf"),
            "old_svg_asset": str(EXTENDED_DPRI_ROOT / "SVG" / "Extended_Data_Fig_1_DPRI.svg"),
            "panel_source_data_files": str(EXTENDED_DPRI_SOURCE),
        }
    )
    return rows


def build_new_inventory() -> list[dict[str, object]]:
    specs = [
        ("New Figure 1", "Single-Phi model rejection and data-closure evidence", "Phi_unified.tsv; roc_curve.tsv; permutation_test_results.tsv; bootstrap_confidence_intervals.tsv; ks_test_results.tsv", "YES", "YES", "MAIN", "none", "LOW", "KEEP_MAIN", "Figure1_single_phi_rejection"),
        ("New Figure 2", "Latent state regime mixture replaces a global Phi threshold", "mixture_density_decomposition_phi.tsv; regime_posterior_probabilities.tsv; latent_regime_mixture_model.md", "YES", "YES", "MAIN", "merge with posterior landscape if possible", "LOW", "MERGE_MAIN", "Figure2_latent_regime_mixture"),
        ("New Figure 3", "Regime posterior landscape shows overlap rather than scalar separability", "regime_posterior_probabilities.tsv; observed_regime_to_latent_regime_composition.tsv", "YES", "YES", "MAIN", "use cleaned Figure 3C labels; keep probabilistic wording", "LOW", "MERGE_MAIN", "Figure3_regime_posterior_landscape"),
        ("New Figure 4", "Regime overlap and symmetrized divergence quantify mixture structure", "regime_overlap_matrix.tsv; species_regime_overlap_matrix.tsv; regime_KL_divergence_matrix.tsv", "YES", "YES", "MAIN", "label matrix as symmetrized KL divergence", "LOW", "KEEP_MAIN", "Figure4_overlap_divergence"),
        ("New Figure 5", "Final latent-state-regime dynamical model replaces single-Phi interpretation", "single_phi_model_invalidation.md; latent_regime_mixture_model.md; latent_regime_mixture_fit_summary.tsv", "YES", "YES", "SUPPLEMENT_OR_MERGE", "merge into conceptual anchor or label as conceptual if standalone", "MEDIUM", "MERGE_MAIN", "Figure5_final_model_schematic"),
    ]
    rows = []
    for num, claim, src, bound, repro, role, fix, risk, status, stem in specs:
        rows.append(
            {
                "new_figure_number": num,
                "central_claim": claim,
                "source_data_file": src,
                "data_bound_yes_no": bound,
                "reproducible_yes_no": repro,
                "main_or_supplement_or_remove": role,
                "required_visual_fix": fix,
                "claim_risk": risk,
                "recommended_status": status,
                "png_file": str(NEW_LOCK / f"{stem}.png"),
                "pdf_file": str(NEW_LOCK / f"{stem}.pdf"),
                "png_available_yes_no": yes(NEW_LOCK / f"{stem}.png"),
                "pdf_available_yes_no": yes(NEW_LOCK / f"{stem}.pdf"),
            }
        )
    return rows


def build_merger_map() -> list[dict[str, object]]:
    return [
        {
            "final_figure_number": "Figure 1",
            "final_figure_title": "Conceptual upgrade from developmental fate-divergence to latent-state-regime mixture dynamics",
            "old_figures_used": "Old Fig 1; Old Fig 9",
            "new_figures_used": "New Fig 5",
            "panels_from_old": "Old evidence architecture and organized-plasticity conceptual skeleton, selectively retained",
            "panels_from_new": "Latent mixture equation and rejected single-Phi replacement schematic",
            "retained_claim": "Plasticity is permissive, not instructive.",
            "revised_claim": "Plasticity outcomes are represented by latent state regime mixtures rather than one global order parameter.",
            "main_message": "The manuscript is reframed around probabilistic latent state regimes while preserving the old biological evidence scaffold.",
            "source_data_files": "Doc1.docx captions; final_data_locking_report.md; latent_regime_mixture_model.md; old figure SVG assets",
            "figure_status": "REBUILD_REQUIRED",
            "reason_for_decision": "Old conceptual model is partly superseded; it should anchor the paper only after explicit mixture-model revision.",
        },
        {
            "final_figure_number": "Figure 2",
            "final_figure_title": "Shared high-plasticity accessibility state space",
            "old_figures_used": "Old Fig 2",
            "new_figures_used": "none",
            "panels_from_old": "State-space, entropy, CellRank/velocity comparator and tumor-like absorption panels",
            "panels_from_new": "none",
            "retained_claim": "High-plasticity states share accessibility structure.",
            "revised_claim": "Shared accessibility does not imply fate equivalence or direct lineage.",
            "main_message": "Old empirical foundation for accessibility is retained with stricter interpretation.",
            "source_data_files": old_panel_sources(2),
            "figure_status": "MAIN",
            "reason_for_decision": "Data-bound old figure remains necessary and not redundant with new mixture figures.",
        },
        {
            "final_figure_number": "Figure 3",
            "final_figure_title": "Stemness-associated programs increase accessibility but do not specify fate",
            "old_figures_used": "Old Fig 3",
            "new_figures_used": "none",
            "panels_from_old": "Wnt/CHIR/beta-catenin perturbation and BMP-Wnt boundary panels",
            "panels_from_new": "none",
            "retained_claim": "Stemness-associated programs generate accessibility.",
            "revised_claim": "Stemness is not a deterministic fate or regeneration classifier.",
            "main_message": "Stemness is a local accessibility component within latent state regimes.",
            "source_data_files": old_panel_sources(3),
            "figure_status": "MAIN",
            "reason_for_decision": "Empirical boundary result directly supports the revised non-deterministic model.",
        },
        {
            "final_figure_number": "Figure 4",
            "final_figure_title": "Regime-conditioned developmental positional information",
            "old_figures_used": "Old Fig 4; Old Fig 7; Extended Data Fig 1 as supplementary support",
            "new_figures_used": "none",
            "panels_from_old": "RA/RARG, RA/HOX, axolotl blastema and pseudotime positional-proxy panels",
            "panels_from_new": "none",
            "retained_claim": "Positional-program activity is associated with regenerative plasticity.",
            "revised_claim": "DPRI/positional information is regime-conditioned and not a universal determinant.",
            "main_message": "Salamander/axolotl blastema is treated as a distinct latent regenerative regime with positional-program activity.",
            "source_data_files": old_panel_sources(4) + "; " + old_panel_sources(7) + "; " + str(EXTENDED_DPRI_SOURCE),
            "figure_status": "REBUILD_REQUIRED",
            "reason_for_decision": "Old Fig 4 and 7 should be merged to avoid redundant regeneration/positional claims.",
        },
        {
            "final_figure_number": "Figure 5",
            "final_figure_title": "Fate-lock and mammalian adult repair-failure regime",
            "old_figures_used": "Old Fig 5; Old Fig 6",
            "new_figures_used": "none",
            "panels_from_old": "Fate-stabilization, senescence-like retention, SAT boundary and cross-system score panels",
            "panels_from_new": "none",
            "retained_claim": "Fate-stabilization and lineage restriction constrain high-plasticity trajectories.",
            "revised_claim": "Mammalian repair failure is an adult-repair/fate-lock-biased latent-state-regime mixture, not the same process as salamander regeneration.",
            "main_message": "Adult repair failure is retained as a mechanistic branch but constrained by mixture-model language.",
            "source_data_files": old_panel_sources(5) + "; " + old_panel_sources(6),
            "figure_status": "REBUILD_REQUIRED",
            "reason_for_decision": "Combining old Fig 5 and 6 reduces redundancy and keeps SAT as bounded evidence.",
        },
        {
            "final_figure_number": "Figure 6",
            "final_figure_title": "Tumor-like plasticity as a distinct high-plasticity branch",
            "old_figures_used": "Old Fig 8",
            "new_figures_used": "none",
            "panels_from_old": "Tumor-like proxy, boundary and cross-system comparison panels",
            "panels_from_new": "none",
            "retained_claim": "Tumor-like plasticity is distinct and operationally high-plasticity.",
            "revised_claim": "Tumor-like plasticity is not embryonic regeneration or inflammatory-repair equivalence.",
            "main_message": "The tumor-like branch remains separate from the regenerative latent state regime.",
            "source_data_files": old_panel_sources(8) + "; Source_Data_Main_Figures_FINAL_Result7_integrated.xlsx; old Figure_8_final assets",
            "figure_status": "MAIN",
            "reason_for_decision": "This prevents over-collapsing all plasticity outcomes into regeneration.",
        },
        {
            "final_figure_number": "Figure 7",
            "final_figure_title": "Single-Phi model rejection and data-closure evidence",
            "old_figures_used": "none",
            "new_figures_used": "New Fig 1",
            "panels_from_old": "none",
            "panels_from_new": "AUC, permutation, bootstrap and KS interpretation panels",
            "retained_claim": "none from old model",
            "revised_claim": "Phi has structure but fails as a global discriminative order parameter.",
            "main_message": "The old scalar model is formally invalidated.",
            "source_data_files": "Phi_unified.tsv; roc_curve.tsv; permutation_test_results.tsv; bootstrap_confidence_intervals.tsv; ks_test_results.tsv",
            "figure_status": "MAIN",
            "reason_for_decision": "Essential negative result; cannot be moved to supplement.",
        },
        {
            "final_figure_number": "Figure 8",
            "final_figure_title": "Latent-state-regime mixture and posterior landscape",
            "old_figures_used": "none",
            "new_figures_used": "New Fig 2; New Fig 3",
            "panels_from_old": "none",
            "panels_from_new": "Mixture density decomposition, per-regime Phi distributions, posterior state-space map and observed-group mixture bars",
            "retained_claim": "none",
            "revised_claim": "Regime identity is encoded by P(Z|S,W_GRN), not a Phi threshold.",
            "main_message": "The replacement model is a latent-state-regime mixture with overlapping posterior mass.",
            "source_data_files": "mixture_density_decomposition_phi.tsv; regime_posterior_probabilities.tsv; observed_regime_to_latent_regime_composition.tsv",
            "figure_status": "REBUILD_REQUIRED",
            "reason_for_decision": "New Fig 2 and 3 should be merged to stay under the 10-display-item limit.",
        },
        {
            "final_figure_number": "Figure 9",
            "final_figure_title": "Regime overlap and symmetrized distributional divergence",
            "old_figures_used": "none",
            "new_figures_used": "New Fig 4",
            "panels_from_old": "none",
            "panels_from_new": "Overlap matrices, symmetrized KL matrix and divergence ranking",
            "retained_claim": "none",
            "revised_claim": "Latent state regimes overlap but show distributional divergence.",
            "main_message": "Salamander blastema and adult repair are not separable by Phi alone but are distributionally different latent-state-regime mixtures.",
            "source_data_files": "regime_overlap_matrix.tsv; species_regime_overlap_matrix.tsv; regime_KL_divergence_matrix.tsv",
            "figure_status": "MAIN",
            "reason_for_decision": "Final quantitative support for mixture overlap/divergence; label KL as symmetrized.",
        },
    ]


def write_main_plan(path: Path) -> None:
    text = """# Final Main Figure Set Under 10 Display Items

Final main display count: **9**.

This plan does not append the new figures to the old manuscript. It restructures the old biological foundation around the new latent-state-regime mixture result and removes the single-Phi interpretation as a positive model.

## Figure 1: Conceptual Upgrade To Latent-Regime Mixture Dynamics

Source: old Fig 1, old Fig 9, and new Fig 5.  
Status: MAIN, rebuild required.  
Role: conceptual anchor. The figure should show that injury-induced plasticity is permissive, but final accessibility is represented by latent state regime mixtures rather than a single scalar Phi.

## Figure 2: Shared High-Plasticity Accessibility State Space

Source: old Fig 2.  
Status: MAIN, minor text revision.  
Role: old empirical foundation for shared accessibility. It must state that connected high-plasticity regions do not imply fate equivalence, direct lineage, or shared regeneration mechanism.

## Figure 3: Stemness-Associated Accessibility Without Fate Determinism

Source: old Fig 3.  
Status: MAIN, minor text revision.  
Role: shows that Wnt/stemness-associated programs increase accessibility but do not determine regeneration, SAT, or tumor-like fate.

## Figure 4: Regime-Conditioned Developmental Positional Information

Source: old Fig 4 and old Fig 7, with Extended Data Fig. 1 retained as supplementary boundary support.  
Status: MAIN, rebuild required.  
Role: merges RA/RARG/HOX positional evidence with axolotl/blastema positional-program evidence. The caption must avoid treating DPRI or high Phi as a universal determinant.

## Figure 5: Fate-Lock And Adult Repair-Failure Regime

Source: old Fig 5 and old Fig 6.  
Status: MAIN, rebuild required.  
Role: combines lineage restriction, senescence-like retention and SAT/adult-repair-failure evidence. It must not equate mammalian repair failure with salamander regeneration.

## Figure 6: Tumor-Like Plasticity As A Distinct Branch

Source: old Fig 8.  
Status: MAIN, minor text revision.  
Role: preserves tumor-like plasticity as a distinct high-plasticity branch, not embryonic regeneration or inflammatory-repair equivalence.

## Figure 7: Single-Phi Model Rejection

Source: new Figure1_single_phi_rejection.  
Status: MAIN.  
Role: formal negative result. It must show AUC approximately 0.480, non-significant permutation mean shift, bootstrap instability, and KS-as-shape-difference interpretation.

## Figure 8: Latent-Regime Mixture And Posterior Landscape

Source: merge new Figure2_latent_regime_mixture and new Figure3_regime_posterior_landscape.  
Status: MAIN, rebuild required as a combined figure.  
Role: replacement model. It must show P(Phi|S)=sum_Z P(Phi|S,Z)P(Z|S,W_GRN) and posterior overlap in state space.

## Figure 9: Regime Overlap And Symmetrized Divergence

Source: new Figure4_overlap_divergence.  
Status: MAIN.  
Role: quantifies overlap and distributional divergence. The KL matrix must be labeled as symmetrized KL divergence.

## Figure 10 Decision

No standalone Figure 10 is recommended. New Figure 5 should be absorbed into Figure 1. Keeping it as a separate main figure would be redundant and would weaken the display-item discipline.
"""
    path.write_text(text, encoding="utf-8")


def write_supp_plan(path: Path) -> None:
    rows = [
        ("Supplementary Fig. S1", "Old Extended Data Fig. 1", "Frog compartment DPRI boundary is useful but not central to main latent-mixture claim.", "YES", "NO", "Supported as compartment boundary; not a species ranking."),
        ("Supplementary Fig. S2", "Old Fig 9 original", "Original integrated model is partly superseded; keep only as historical conceptual precursor if needed.", "NO", "YES", "Only supported after latent-mixture relabeling."),
        ("Supplementary Fig. S3", "New Fig 5 standalone", "Final schematic should be merged into main Fig 1; standalone version is redundant.", "YES", "NO", "Supported as conceptual summary tied to Figures 7-9."),
        ("Supplementary Fig. S4", "Old Fig 1 full evidence architecture", "Main Fig 1 should be simplified; full evidence architecture can move to supplement.", "NO", "YES", "Supported as evidence map, not data panel."),
        ("Supplementary Fig. S5", "Old Fig 5/6 extended SAT panels", "Main Fig 5 should be compressed; detailed SAT boundary panels can support supplement.", "YES", "YES", "Supported with adult-repair/fate-lock wording."),
        ("Supplementary Fig. S6", "W_GRN graph", "Useful mechanistic context but not part of final figure-integration story.", "YES", "NO", "Supported as learned/schematic network if tied to W_GRN_learned.tsv."),
        ("Supplementary Fig. S7", "Batch and normalization QC", "QC supports data closure but not a main biological claim.", "YES", "NO", "Supported as technical validation."),
        ("Supplementary Fig. S8", "Additional Phi validation/QC plots", "Retain only as negative-control/QC material; not as a positive Phi model.", "YES", "YES", "Supported only as rejection/diagnostic evidence."),
    ]
    lines = ["# Final Supplementary Figure Plan", ""]
    for r in rows:
        lines.append(f"## {r[0]}")
        lines.append("")
        lines.append(f"- source_old_or_new: {r[1]}")
        lines.append(f"- reason_for_supplementary_status: {r[2]}")
        lines.append(f"- data_bound_yes_no: {r[3]}")
        lines.append(f"- whether_needs_rebuild: {r[4]}")
        lines.append(f"- claim_supported: {r[5]}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def build_results_mapping() -> list[dict[str, str]]:
    return [
        {"result_number": "Result 1", "result_title": "The manuscript framework is upgraded from organized plasticity to latent-state-regime mixture dynamics", "final_figure": "Figure 1", "old_evidence_used": "Old Fig 1; Old Fig 9", "new_evidence_used": "New Fig 5; model invalidation reports", "main_claim": "Plasticity is permissive and final fate accessibility is represented by latent state regime mixtures.", "limitation_statement": "Figure 1 is conceptual and depends on empirical support in later figures.", "whether_claim_is_empirical_or_model_based": "model-based/conceptual"},
        {"result_number": "Result 2", "result_title": "High-plasticity states occupy a shared accessibility space without fate equivalence", "final_figure": "Figure 2", "old_evidence_used": "Old Fig 2", "new_evidence_used": "none", "main_claim": "Shared accessibility is present but does not imply shared outcome or direct lineage.", "limitation_statement": "Velocity and CellRank are inferred trajectory comparators, not lineage tracing.", "whether_claim_is_empirical_or_model_based": "empirical/model-assisted"},
        {"result_number": "Result 3", "result_title": "Stemness-associated programs increase accessibility but do not determine outcome", "final_figure": "Figure 3", "old_evidence_used": "Old Fig 3", "new_evidence_used": "none", "main_claim": "Stemness-associated programs contribute local accessibility within regimes.", "limitation_statement": "Stemness scores are not fate classifiers.", "whether_claim_is_empirical_or_model_based": "empirical"},
        {"result_number": "Result 4", "result_title": "Developmental positional information is regime-conditioned", "final_figure": "Figure 4", "old_evidence_used": "Old Fig 4; Old Fig 7; Extended Data Fig 1", "new_evidence_used": "none", "main_claim": "Regenerative plasticity is associated with positional-program activity in a regime-conditioned way.", "limitation_statement": "Expression-layer proxies do not directly measure spatial coordinates or morphogen gradients.", "whether_claim_is_empirical_or_model_based": "empirical/proxy-based"},
        {"result_number": "Result 5", "result_title": "Fate-lock and senescence-like programs define an adult repair-failure-biased regime", "final_figure": "Figure 5", "old_evidence_used": "Old Fig 5; Old Fig 6", "new_evidence_used": "none", "main_claim": "Mammalian repair failure is an adult-repair/fate-lock-biased mixture, not the same process as salamander regeneration.", "limitation_statement": "Perturbation time series are required for causal SAT feedback.", "whether_claim_is_empirical_or_model_based": "empirical/model-assisted"},
        {"result_number": "Result 6", "result_title": "Tumor-like plasticity is distinct from embryonic regeneration", "final_figure": "Figure 6", "old_evidence_used": "Old Fig 8", "new_evidence_used": "none", "main_claim": "Tumor-like plasticity is a distinct high-plasticity branch.", "limitation_statement": "Operational proxy results should not be generalized to all cancers.", "whether_claim_is_empirical_or_model_based": "empirical/proxy-based"},
        {"result_number": "Result 7", "result_title": "A single global Phi order parameter is rejected", "final_figure": "Figure 7", "old_evidence_used": "none", "new_evidence_used": "New Fig 1", "main_claim": "Phi is not a valid global discriminative order parameter.", "limitation_statement": "KS significance indicates shape difference but not separability.", "whether_claim_is_empirical_or_model_based": "statistical/model-validation"},
        {"result_number": "Result 8", "result_title": "Latent-state-regime mixture replaces the single-Phi framework", "final_figure": "Figure 8", "old_evidence_used": "none", "new_evidence_used": "New Fig 2; New Fig 3", "main_claim": "Regime identity is probabilistic and represented by P(Z|S,W_GRN).", "limitation_statement": "The mixture is partially supported at processed score/proxy level.", "whether_claim_is_empirical_or_model_based": "model-based with empirical fit"},
        {"result_number": "Result 9", "result_title": "Regime overlap and divergence explain salamander versus mammalian repair without scalar separation", "final_figure": "Figure 9", "old_evidence_used": "none", "new_evidence_used": "New Fig 4", "main_claim": "Adult repair and salamander blastema overlap but are distributionally different latent-state-regime mixtures.", "limitation_statement": "Do not claim complete mammal-versus-salamander separation.", "whether_claim_is_empirical_or_model_based": "statistical/model-validation"},
    ]


def write_claim_audit(path: Path) -> None:
    rows = [
        ("Phi separates mammal and salamander", "Contradicted by AUC approximately 0.480 and unstable bootstrap shift.", "Phi shows distributional structure but is not a global discriminator; regime identity is modeled by P(Z|S,W_GRN).", "removed/main-text negative result"),
        ("high Phi equals salamander blastema", "Collapses blastema into scalar threshold despite mixture overlap.", "Salamander blastema is a distinct latent regenerative regime with overlap and distributional divergence.", "main text"),
        ("single order parameter governs regeneration", "Rejected by data-closure and identifiability failure.", "Regenerative accessibility is better represented by a latent-state-regime mixture dynamical system.", "main text"),
        ("tumor-like plasticity is embryonic reversion", "Old tumor branch evidence says embryonic-like score is not meaningfully increased.", "Tumor-like plasticity remains a distinct high-plasticity branch and is not validated as embryonic regeneration.", "main text/discussion"),
        ("inflammation repair and salamander regeneration are the same process", "Biologically and statistically collapses adult repair and blastema regimes.", "Mammalian inflammatory repair is adult-repair-dominant mixture; salamander blastema is blastema-accessible latent regenerative regime.", "main text"),
        ("DPRI alone defines regeneration competence", "DPRI is expression-layer/proxy and compartment-dependent.", "DPRI/positional information is a regime-conditioned developmental coordinate, not a universal determinant.", "main text"),
        ("stemness determines regeneration outcome", "Stemness increases accessibility but does not specify fate.", "Stemness-associated programs provide local accessibility within regimes.", "main text"),
        ("fate-lock reversal alone explains salamander regeneration", "Ignores positional/developmental reactivation and latent-state-regime structure.", "Fate-lock modulation is one component of regime-conditioned accessibility; salamander regeneration requires blastema-associated latent state regime interpretation.", "discussion"),
        ("mammalian and salamander regeneration differ only quantitatively", "Mixture model indicates overlap plus distributional divergence, not a scalar continuum.", "Mammalian repair and salamander blastema are overlapping but distinct latent-state-regime mixtures.", "main text"),
    ]
    lines = ["# Claim Consistency Audit", ""]
    for i, (claim, issue, replacement, placement) in enumerate(rows, 1):
        lines.append(f"## Flagged claim {i}")
        lines.append("")
        lines.append(f"- original_wording_or_claim: {claim}")
        lines.append(f"- issue: {issue}")
        lines.append(f"- replacement_wording: {replacement}")
        lines.append(f"- whether_it_should_be_in_main_text_or_discussion_or_removed: {placement}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_rebuild_requirements(path: Path) -> None:
    reqs = [
        ("Figure 1", "A-D conceptual/evidence scaffold", "Doc1 old Fig 1/9 assets; new Fig 5 inputs; final_data_locking_report.md; latent_regime_mixture_model.md", "Rebuild old conceptual model around latent state regimes; remove positive single-Phi reading.", "latent state regime probability; no global Phi threshold", "AUC 0.480 may be referenced but full stats appear in Fig 7", "YES", "YES, merge schematic elements", "YES, explicitly conceptual", "PNG 300 dpi; PDF or SVG vector"),
        ("Figure 2", "A-G from old Fig 2", old_panel_sources(2), "Minor caption/title wording only.", "state-space axes and inferred transition labels; no fate-equivalence language", "CellRank/velocity labels as inferred comparators", "NO, use old source assets", "NO, unless resizing to new style", "NO", "PNG 300 dpi; PDF or SVG vector"),
        ("Figure 3", "A-F from old Fig 3", old_panel_sources(3), "Keep boundary result; reduce deterministic wording.", "stemness/accessibility score axes; BMP-Wnt boundary labels", "Spearman/q-value annotation if retained", "NO", "NO, unless style harmonization required", "NO", "PNG 300 dpi; PDF or SVG vector"),
        ("Figure 4", "A-H merged positional + axolotl/blastema panels", old_panel_sources(4) + "; " + old_panel_sources(7), "Merge old Fig 4 and Fig 7; remove universal DPRI or high-Phi language.", "RA/HOX positional proxy; blastema-associated module score; pseudotime", "Only source-supported mean/q/p annotations", "YES, old panels need extraction/recomposition", "NO new analysis; visual recomposition needed", "Limited schematic acceptable for compartment orientation", "PNG 300 dpi; PDF or SVG vector"),
        ("Figure 5", "A-F/H merged fate-lock + SAT panels", old_panel_sources(5) + "; " + old_panel_sources(6), "Merge old Fig 5 and Fig 6; bound SAT interpretation.", "fate-stabilization; lineage restriction; self-absorption; velocity self-transition", "CellRank and velocity summaries labeled as inferred", "YES, extract old panels", "NO new analysis; visual recomposition needed", "Boundary schematic acceptable", "PNG 300 dpi; PDF or SVG vector"),
        ("Figure 6", "A-H from old Fig 8", old_panel_sources(8) + "; Source_Data_Main_Figures_FINAL_Result7_integrated.xlsx; old Figure_8_final assets", "Keep separate tumor branch; avoid embryonic reversion claim.", "tumor-like proxy; stemness; differentiation; local retention", "BH-FDR/q values only where source-supported", "NO", "NO, unless style harmonization required", "NO", "PNG 300 dpi; PDF or SVG vector"),
        ("Figure 7", "A-E from new Fig 1", "Phi_unified.tsv; roc_curve.tsv; permutation_test_results.tsv; bootstrap_confidence_intervals.tsv; ks_test_results.tsv", "Use locked new figure; no visual rescue of Phi.", "Phi; FPR; TPR; bootstrap CI; permutation null", "AUC approximately 0.480; permutation p; bootstrap CI; KS as shape difference", "NO", "NO, locked figure is acceptable", "Interpretation panel acceptable", "PNG 300 dpi; PDF or SVG vector"),
        ("Figure 8", "A-H combined from new Fig 2 and 3", "mixture_density_decomposition_phi.tsv; regime_posterior_probabilities.tsv; observed_regime_to_latent_regime_composition.tsv", "Combine mixture densities with posterior landscape; preserve overlap interpretation.", "Phi mass; Fate-lock axis; Embryonic-accessibility module; P(Z|S)", "No AUC objective; show posterior certainty/mixture bars", "NO", "YES, merge two locked figures into one", "Equation panel acceptable", "PNG 300 dpi; PDF or SVG vector"),
        ("Figure 9", "A-D from new Fig 4", "regime_overlap_matrix.tsv; species_regime_overlap_matrix.tsv; regime_KL_divergence_matrix.tsv", "Use locked new figure; ensure KL label is symmetrized.", "overlap; posterior-composition overlap; symmetrized KL divergence", "Symmetrized KL; no separability claim", "NO", "NO, locked figure is acceptable", "NO", "PNG 300 dpi; PDF or SVG vector"),
    ]
    lines = ["# Figure Rebuild Requirements", ""]
    for fig, layout, src, changes, axes, stats, old_extract, new_redraw, schem, fmt in reqs:
        lines.append(f"## {fig}")
        lines.append("")
        lines.append(f"- panel layout: {layout}")
        lines.append(f"- source data files: {src}")
        lines.append(f"- required visual changes: {changes}")
        lines.append(f"- required axis labels: {axes}")
        lines.append(f"- required statistical annotations: {stats}")
        lines.append(f"- whether old figure panels need extraction from Doc1.docx: {old_extract}")
        lines.append(f"- whether new figure panels need redrawing: {new_redraw}")
        lines.append(f"- whether schematic panels are acceptable: {schem}")
        lines.append(f"- final output format needed: {fmt}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_verdict(path: Path, old_count: int, embedded_count: int, new_count: int) -> None:
    text = f"""# Final Figure Integration Verdict

OLD_FIGURES_AUDITED: yes
NEW_FIGURES_AUDITED: yes
FINAL_MAIN_FIGURES: 9
WITHIN_10_DISPLAY_ITEM_LIMIT: yes
SUPPLEMENTARY_FIGURES_PLANNED: 8
READY_FOR_MANUSCRIPT_REWRITE: yes

## Counts

- total old figures audited: {old_count}
- total old embedded images detected: {embedded_count}
- total new figures audited: {new_count}
- final main figure count: 9
- final supplementary figure count: 8 planned

## Figures That Must Be Rebuilt

- Final Figure 1: old Fig 1/9 plus new Fig 5 conceptual anchor.
- Final Figure 4: merged positional/DPRI and axolotl/blastema evidence.
- Final Figure 5: merged fate-lock and SAT/adult repair-failure evidence.
- Final Figure 8: combined latent-mixture and posterior-landscape figure.

## Figures Usable With Minor Edits

- Final Figure 2 from old Fig 2.
- Final Figure 3 from old Fig 3.
- Final Figure 6 from old Fig 8.
- Final Figure 7 from new Figure1_single_phi_rejection.
- Final Figure 9 from new Figure4_overlap_divergence.

## Figures Moved To Supplementary

- Extended Data Fig. 1 / frog DPRI compartment boundary.
- Full old Fig 1 evidence architecture if not fully absorbed.
- Standalone new Fig 5 schematic if not absorbed into Final Figure 1.
- Extra SAT, W_GRN, batch/QC and Phi diagnostic plots.

## Figures Removed Or Not Used As Positive Main Evidence

- Any single-Phi phase diagram or manual regime-switching plot.
- Any old conceptual panel implying a single order parameter or deterministic mammal-salamander continuum.
- Any tumor-like panel wording that implies embryonic reversion.

## BLOCKING_ISSUES

- None blocking for manuscript rewrite.
- Required before final publication-figure generation: rebuild Figures 1, 4, 5 and 8 from source panels/assets, not screenshots.
- Required before submission: keep all claims aligned with latent-state-regime mixture model and avoid treating Phi as a classifier.
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    figures, embedded = parse_docx_figures()
    old_rows = build_old_inventory(figures)
    new_rows = build_new_inventory()
    merger_rows = build_merger_map()

    write_tsv(
        OUT / "old_figure_inventory.tsv",
        old_rows,
        [
            "old_figure_number",
            "caption",
            "result_section",
            "data_type",
            "empirical_or_conceptual",
            "current_claim",
            "whether_the_claim_remains_valid_under_latent_regime_mixture_model",
            "data_bound_yes_no",
            "source_data_available_yes_no",
            "recommended_status",
            "risk_level",
            "required_fix",
            "doc1_media_target",
            "doc1_caption_paragraph_index",
            "old_png_asset",
            "old_pdf_asset",
            "old_svg_asset",
            "panel_source_data_files",
        ],
    )
    write_tsv(
        OUT / "new_figure_inventory.tsv",
        new_rows,
        [
            "new_figure_number",
            "central_claim",
            "source_data_file",
            "data_bound_yes_no",
            "reproducible_yes_no",
            "main_or_supplement_or_remove",
            "required_visual_fix",
            "claim_risk",
            "recommended_status",
            "png_file",
            "pdf_file",
            "png_available_yes_no",
            "pdf_available_yes_no",
        ],
    )
    write_tsv(
        OUT / "old_new_figure_merger_map.tsv",
        merger_rows,
        [
            "final_figure_number",
            "final_figure_title",
            "old_figures_used",
            "new_figures_used",
            "panels_from_old",
            "panels_from_new",
            "retained_claim",
            "revised_claim",
            "main_message",
            "source_data_files",
            "figure_status",
            "reason_for_decision",
        ],
    )
    write_main_plan(OUT / "final_main_figure_set_under10.md")
    write_supp_plan(OUT / "final_supplementary_figure_plan.md")
    write_tsv(
        OUT / "final_results_to_figure_mapping.tsv",
        build_results_mapping(),
        [
            "result_number",
            "result_title",
            "final_figure",
            "old_evidence_used",
            "new_evidence_used",
            "main_claim",
            "limitation_statement",
            "whether_claim_is_empirical_or_model_based",
        ],
    )
    write_claim_audit(OUT / "claim_consistency_audit.md")
    write_rebuild_requirements(OUT / "figure_rebuild_requirements.md")
    write_verdict(OUT / "final_figure_integration_verdict.md", len(old_rows), embedded, len(new_rows))
    print("figure integration audit complete")
    print(f"old figures audited: {len(old_rows)}; embedded images detected: {embedded}; new figures audited: {len(new_rows)}")


if __name__ == "__main__":
    main()
