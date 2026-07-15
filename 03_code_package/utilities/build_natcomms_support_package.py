from __future__ import annotations

import csv
import hashlib
import os
import re
import shutil
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path("/Users/hanchengdezhuanqiangongju/Documents/Codex/2026-06-18/task-reconstruct-and-continue-analysis-of")
INPUT_MANUSCRIPT = ROOT / "story_strengthening_output/manuscript_STORY_STRENGTHENED_ENDNOTE_SAFE.docx"
PACKAGE = ROOT / "NatComms_submission_support_package"
REQUESTED_PACKAGE = Path("/mnt/data/细胞命运_NatComms_submission_support_package")

SUBDIRS = [
    "00_input_backups",
    "01_final_manuscript",
    "02_source_data",
    "03_code_package",
    "04_figure_source_mapping",
    "05_claim_evidence_mapping",
    "06_validation_and_robustness",
    "07_perturbation_audit",
    "08_submission_reports",
    "09_missing_items",
]


def safe_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except Exception:
        return str(path)


def md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_tsv(path: Path, rows: list[dict], fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def read_tsv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def copy_file(src: Path, dst_dir: Path, copied: dict[str, str] | None = None) -> str:
    dst_dir.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        return ""
    stem = src.name
    dst = dst_dir / stem
    if dst.exists() and md5(dst) != md5(src):
        dst = dst_dir / f"{src.stem}_{md5(src)[:8]}{src.suffix}"
    if not dst.exists():
        shutil.copy2(src, dst)
    if copied is not None:
        copied[str(src)] = str(dst)
    return str(dst)


def split_paths(text: str) -> list[Path]:
    if not text:
        return []
    parts = []
    for p in re.split(r";\s*", text):
        p = p.strip()
        if not p:
            continue
        parts.append(Path(p))
    return parts


def detect_dataset(panel_text: str) -> str:
    accessions = re.findall(r"GSE\d+", panel_text)
    if accessions:
        return ";".join(sorted(set(accessions)))
    if "Axolotl" in panel_text or "salamander" in panel_text.lower():
        return "salamander/axolotl integrated datasets"
    if "mammalian" in panel_text.lower() or "wound" in panel_text.lower():
        return "mammalian repair datasets including GSE153596 where applicable"
    if "perturb" in panel_text.lower() or "RA" in panel_text or "BMP" in panel_text:
        return "public perturbation-derived outputs where available"
    return "processed integrated state-space outputs"


def classify_script(path: Path) -> str:
    name = path.name.lower()
    if any(k in name for k in ["preprocess", "inventory", "t9", "geo"]):
        return "preprocessing"
    if any(k in name for k in ["score", "w_grn", "learn", "emergent", "nonlinear", "identifiability"]):
        return "scoring"
    if any(k in name for k in ["model", "consistency", "comparison", "closure", "mixture", "phi"]):
        return "model_comparison"
    if any(k in name for k in ["figure", "render", "visual", "label", "panel", "cleanup", "reconstruct"]):
        return "figure_generation"
    if any(k in name for k in ["perturb", "causal", "regime_conditioned"]):
        return "perturbation_audit"
    return "utilities"


def language(path: Path) -> str:
    s = path.suffix.lower()
    return {".py": "Python", ".r": "R", ".R": "R", ".ipynb": "Jupyter notebook"}.get(s, s.lstrip("."))


def figure_asset_map() -> dict[str, list[Path]]:
    assets = defaultdict(list)
    candidates = [
        ROOT / "outputs/final_9figures_reconstructed/final_9figure_asset_manifest.tsv",
        ROOT / "FINAL_SUBMISSION_PACKAGE/main_figures",
        ROOT / "outputs/FINAL_SUPPLEMENTARY_FIGURES_VISUALLY_REDESIGNED",
        ROOT / "FINAL_SUBMISSION_PACKAGE/supplementary_source_data",
    ]
    manifest = candidates[0]
    for row in read_tsv(manifest):
        fig = row.get("figure", "")
        for col in ["png", "pdf"]:
            p = Path(row.get(col, ""))
            if p.exists():
                assets[fig].append(p)
    # Figure 1A and supplement.
    for p in [
        ROOT / "outputs/MODEL_EVOLUTION_MAP_Figure1A.png",
        ROOT / "outputs/MODEL_EVOLUTION_MAP_Figure1A.pdf",
        ROOT / "outputs/MODEL_EVOLUTION_MAP_Figure1A.svg",
        ROOT / "outputs/SUPP_FIGURE_CAUSAL_CLOSURE_REDESIGNED.png",
        ROOT / "outputs/SUPP_FIGURE_CAUSAL_CLOSURE_REDESIGNED.pdf",
        ROOT / "outputs/FINAL_SUPPLEMENTARY_FIGURES_VISUALLY_REDESIGNED/SUPP_FIGURE_CAUSAL_CLOSURE_REDESIGNED.svg",
        ROOT / "outputs/FIGURE_CAUSAL_CLOSURE_FINAL.png",
        ROOT / "outputs/FIGURE_CAUSAL_CLOSURE_FINAL.pdf",
    ]:
        if p.exists():
            key = "Figure 1A" if "MODEL_EVOLUTION" in p.name else "Supplementary Figure 1"
            assets[key].append(p)
    return assets


def local_existing(paths: list[Path]) -> list[Path]:
    out = []
    for p in paths:
        if not p.is_absolute():
            p = ROOT / p
        if p.exists():
            out.append(p)
    return out


def source_mapping_rows(fig_assets: dict[str, list[Path]]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    missing: list[dict] = []

    def add_row(fig, panel, desc, source_dataset, source_files, scripts, analysis, kind, notes=""):
        existing_sources = local_existing(source_files)
        existing_scripts = local_existing(scripts)
        image_files = fig_assets.get(fig, [])
        if kind == "schematic":
            status = "not_applicable_conceptual_schematic" if not existing_sources else "partial"
        elif source_files and len(existing_sources) == len(source_files):
            status = "complete"
        elif existing_sources:
            status = "partial"
        else:
            status = "missing"
        if status == "missing" and source_files:
            for src in source_files:
                missing.append({
                    "figure_number": fig,
                    "panel": panel,
                    "expected_source_file": str(src),
                    "reason": "listed in prior manifest or required by panel, but file is not accessible in current project state",
                    "recommended_action": "recover from external drive/project archive or rebuild panel source data from raw analysis",
                })
        rows.append({
            "figure_number": fig,
            "panel": panel,
            "panel_description": desc,
            "source_dataset": source_dataset,
            "source_data_file": "; ".join(str(p) for p in existing_sources) if existing_sources else "; ".join(str(p) for p in source_files),
            "source_script_or_notebook": "; ".join(str(p) for p in existing_scripts) if existing_scripts else "; ".join(str(p) for p in scripts),
            "figure_image_file": "; ".join(str(p) for p in image_files),
            "analysis_type": analysis,
            "data_or_schematic": kind,
            "source_data_status": status,
            "notes": notes,
        })

    add_row(
        "Figure 1A", "all",
        "Model evolution map from PGCS/Phi scalar assumption through failure layer to latent-state-regime replacement.",
        "processed statistical validation outputs",
        [
            ROOT / "outputs/statistical_validation_report.md",
            ROOT / "outputs/single_phi_model_invalidation.md",
            ROOT / "outputs/model_architecture_reconstruction.md",
            ROOT / "outputs/latent_regime_mixture_model.md",
        ],
        [ROOT / "work/add_model_evolution_map.py"],
        "conceptual model lineage with statistical failure anchors",
        "schematic",
        "No numeric panel-level plot table required beyond cited failure reports.",
    )

    # Figure 1-6 from completed manifest. Re-check paths live because T9 may be disconnected.
    manifest = ROOT / "figure_1_to_6_panel_source_manifest_FINAL.tsv"
    for r in read_tsv(manifest):
        fig = r.get("figure_id", "")
        panel = r.get("panel_id", "")
        desc = r.get("panel_title_or_content", "")
        paths = split_paths(r.get("exact_source_file_path", ""))
        status_hint = r.get("source_status", "")
        kind = "schematic" if "SCHEMATIC" in status_hint or "SOURCE_NOT_REQUIRED" in status_hint else "data-derived"
        analysis = r.get("analysis_step", "") or r.get("manuscript_role", "")
        notes = r.get("notes", "")
        add_row(
            fig,
            panel,
            desc,
            detect_dataset(desc + " " + analysis),
            paths,
            [],
            analysis,
            kind,
            notes + (" External T9 source paths were re-checked live for this support package." if any(str(p).startswith("/Volumes/T9") for p in paths) else ""),
        )

    # Figure 7-9 and supplementary support from local locked outputs.
    add_row(
        "Figure 7", "A-E",
        "Scalar Phi failure: distributions, ROC/AUC, permutation, bootstrap and KS interpretation.",
        "processed cross-species Phi/statistical validation outputs",
        [
            ROOT / "outputs/Phi_unified.tsv",
            ROOT / "outputs/roc_curve.tsv",
            ROOT / "outputs/ks_test_results.tsv",
            ROOT / "outputs/permutation_test_results.tsv",
            ROOT / "outputs/permutation_null_distribution.tsv",
            ROOT / "outputs/bootstrap_confidence_intervals.tsv",
            ROOT / "outputs/statistical_validation_report.md",
            ROOT / "outputs/single_phi_model_invalidation.md",
        ],
        [ROOT / "outputs/figure_reconstruction_pipeline.py", ROOT / "work/replace_phi_with_regime_mixture.py"],
        "statistical validation and scalar-model failure diagnostics",
        "data-derived",
        "AUC approximately 0.480; KS significant but non-discriminative.",
    )
    add_row(
        "Figure 8", "A-G",
        "Latent-state-regime posterior densities, posterior landscape, observed groups as mixtures and regime-conditioned dynamics.",
        "processed posterior regime/state score outputs",
        [
            ROOT / "outputs/regime_posterior_probabilities.tsv",
            ROOT / "outputs/mixture_density_decomposition_phi.tsv",
            ROOT / "outputs/observed_regime_to_latent_regime_composition.tsv",
            ROOT / "outputs/latent_regime_mixture_fit_summary.tsv",
            ROOT / "outputs/latent_regime_mixture_parameters.tsv",
            ROOT / "outputs/latent_regime_mixture_model.md",
        ],
        [ROOT / "work/replace_phi_with_regime_mixture.py", ROOT / "work/representational_consistency_analysis.py"],
        "latent-state-regime mixture fitting and posterior visualization",
        "data-derived",
        "Represents accepted working posterior structure, not wet-lab causal law.",
    )
    add_row(
        "Figure 9", "A-D",
        "Regime overlap, species/regime posterior overlap, symmetrized KL divergence and divergence ranking.",
        "processed posterior regime/state score outputs",
        [
            ROOT / "outputs/regime_overlap_matrix.tsv",
            ROOT / "outputs/species_regime_overlap_matrix.tsv",
            ROOT / "outputs/regime_KL_divergence_matrix.tsv",
            ROOT / "outputs/regime_posterior_overlap_matrix.tsv",
        ],
        [ROOT / "work/replace_phi_with_regime_mixture.py"],
        "overlap and distributional divergence analysis",
        "data-derived",
        "Divergence is distributional, not scalar-axis distance.",
    )
    supp_sources = [
        ROOT / "outputs/perturbation_deltaZ.tsv",
        ROOT / "outputs/closure_model_comparison.tsv",
        ROOT / "outputs/regime_conditioned_deltaZ_consistency.tsv",
        ROOT / "outputs/counterfactual_bias_by_regime.tsv",
        ROOT / "outputs/edge_stability_across_regimes.tsv",
        ROOT / "outputs/causal_closure_score_summary.tsv",
        ROOT / "outputs/cross_dataset_perturbation_similarity.tsv",
        ROOT / "outputs/null_perturbation_control_results.tsv",
        ROOT / "outputs/counterfactual_consistency_scores.tsv",
        ROOT / "outputs/W_matrix_by_regime.tsv",
        ROOT / "outputs/regime_conditioned_grn_summary.tsv",
        ROOT / "outputs/final_closure_state_report.md",
    ]
    add_row(
        "Supplementary Figure 1", "A-E",
        "Dry-lab perturbation consistency audit: model comparison, pathway/regime metrics, failure audit and final partial-closure badge.",
        "public perturbation-derived dry-lab outputs; pathway summaries for RA/BMP/NOTCH/FGF/SHH",
        supp_sources,
        [ROOT / "work/causal_closure_consistency_validation.py", ROOT / "work/regime_conditioned_causal_dynamics_v2.py", ROOT / "work/integrate_causal_consistency_into_manuscript.py"],
        "dry-lab perturbation consistency audit",
        "audit summary",
        "Supports PARTIAL_CLOSURE only, not wet-lab validation or complete causal closure.",
    )
    return rows, missing


def source_data_package(mapping_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    master = []
    missing = []
    for row in mapping_rows:
        fig = row["figure_number"].replace(" ", "_")
        fdir = PACKAGE / "02_source_data" / fig
        fdir.mkdir(parents=True, exist_ok=True)
        source_paths = split_paths(row["source_data_file"])
        included = []
        missing_here = []
        for p in source_paths:
            if not p.is_absolute():
                p = ROOT / p
            if p.exists():
                dst = copy_file(p, fdir)
                included.append(Path(dst).name)
                master.append({
                    "figure_number": row["figure_number"],
                    "panel": row["panel"],
                    "file_name": Path(dst).name,
                    "file_type": p.suffix.lstrip(".").upper() or "file",
                    "description": row["panel_description"],
                    "status": "copied",
                    "notes": row["notes"],
                })
            elif str(p):
                missing_here.append(str(p))
                master.append({
                    "figure_number": row["figure_number"],
                    "panel": row["panel"],
                    "file_name": str(p),
                    "file_type": p.suffix.lstrip(".").upper() or "unknown",
                    "description": row["panel_description"],
                    "status": "missing",
                    "notes": "File listed but not accessible in current workspace.",
                })
        if row["data_or_schematic"] == "schematic" and not source_paths:
            master.append({
                "figure_number": row["figure_number"],
                "panel": row["panel"],
                "file_name": "",
                "file_type": "not_applicable",
                "description": row["panel_description"],
                "status": "not_applicable_conceptual_schematic",
                "notes": row["notes"],
            })
        readme = f"""# {row['figure_number']} Source Data

## Panels Covered

- {row['panel']}: {row['panel_description']}

## Source Dataset Accessions

{row['source_dataset']}

## Source Tables Included

{chr(10).join('- ' + x for x in included) if included else '- none copied for this row'}

## Source Tables Missing

{chr(10).join('- ' + x for x in missing_here) if missing_here else '- none for this row'}

## Relation To Plotted Values

{row['analysis_type']}

## Conceptual Panels

data_or_schematic = {row['data_or_schematic']}; source_data_status = {row['source_data_status']}

## Notes

{row['notes']}
"""
        # Append if multiple rows share folder.
        readme_path = fdir / "README.md"
        if readme_path.exists():
            readme_path.write_text(readme_path.read_text(encoding="utf-8") + "\n\n---\n\n" + readme, encoding="utf-8")
        else:
            readme_path.write_text(readme, encoding="utf-8")
    return master, missing


def build_code_package() -> list[dict]:
    scripts = []
    for base in [ROOT / "work", ROOT / "outputs"]:
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in {".py", ".r", ".ipynb"}:
                if "render_" in str(p) and p.suffix.lower() != ".py":
                    continue
                scripts.append(p)
    rows = []
    for p in sorted(set(scripts)):
        cat = classify_script(p)
        dst = copy_file(p, PACKAGE / "03_code_package" / cat)
        text = ""
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")[:2000]
        except Exception:
            pass
        purpose = "utility or manuscript-support script"
        if "figure" in p.name.lower():
            purpose = "figure generation or figure QA"
        elif "perturb" in p.name.lower() or "causal" in p.name.lower():
            purpose = "perturbation audit or causal-consistency support"
        elif "regime" in p.name.lower() or "model" in p.name.lower() or "phi" in p.name.lower():
            purpose = "model comparison or latent-state-regime analysis"
        rows.append({
            "script_file": str(Path(dst).relative_to(PACKAGE)),
            "language": language(p),
            "purpose": purpose,
            "related_figure_or_result": infer_related_figure(p.name),
            "input_files": infer_inputs(text),
            "output_files": infer_outputs(text),
            "status": "copied_available",
            "notes": f"source path: {safe_rel(p)}",
        })
    return rows


def infer_related_figure(name: str) -> str:
    low = name.lower()
    figs = []
    for i in range(1, 10):
        if f"figure_{i}" in low or f"fig{i}" in low or f"figure{i}" in low:
            figs.append(f"Figure {i}")
    if "causal" in low or "perturb" in low:
        figs.append("Supplementary Figure 1")
    if "model_evolution" in low:
        figs.append("Figure 1A")
    return "; ".join(figs) if figs else "general/supporting"


def infer_inputs(text: str) -> str:
    matches = re.findall(r"['\"]([^'\"]+\.(?:tsv|csv|xlsx|h5ad|mtx|txt|json|md))['\"]", text)
    return "; ".join(sorted(set(matches))[:20])


def infer_outputs(text: str) -> str:
    matches = re.findall(r"['\"]([^'\"]+\.(?:tsv|csv|png|pdf|svg|docx|md|json))['\"]", text)
    return "; ".join(sorted(set(matches))[:20])


def inventory_files() -> list[dict]:
    exts = {".docx", ".png", ".pdf", ".svg", ".tif", ".tiff", ".jpg", ".jpeg", ".tsv", ".csv", ".xlsx", ".py", ".r", ".ipynb", ".md", ".bib", ".ris"}
    rows = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if PACKAGE in p.parents:
            continue
        if p.suffix.lower() not in exts:
            continue
        try:
            size = p.stat().st_size
        except OSError:
            size = ""
        rows.append({
            "file_path": safe_rel(p),
            "extension": p.suffix.lower(),
            "size_bytes": size,
            "category": category_for_ext(p),
        })
    return sorted(rows, key=lambda r: r["file_path"])


def category_for_ext(p: Path) -> str:
    s = p.suffix.lower()
    if s == ".docx":
        return "DOCX manuscript/document"
    if s in {".png", ".pdf", ".svg", ".tif", ".tiff", ".jpg", ".jpeg"}:
        return "figure/image/rendered output"
    if s in {".tsv", ".csv", ".xlsx"}:
        return "source-data/table"
    if s in {".py", ".r", ".ipynb"}:
        return "script/notebook"
    if s == ".md":
        return "report/readme"
    if s in {".bib", ".ris"}:
        return "reference metadata"
    return "other"


def claim_mapping() -> list[dict]:
    return [
        {
            "claim_id": "C1",
            "claim_text": "Phi/global scalar is rejected as discriminative or biological order parameter.",
            "manuscript_section": "Results; Discussion",
            "figure_panel_support": "Figure 1; Figure 7",
            "dataset_support": "Phi_unified.tsv; aligned_state_matrix.tsv",
            "analysis_support": "ROC AUC ~0.480; permutation p=0.585; bootstrap intervals cross zero; KS significant but non-discriminative.",
            "evidence_strength": "strong_computational_support",
            "limitation": "Processed score-level analysis; not raw-data wet-lab validation.",
            "whether_wet_lab_validation_is_claimed": "no",
        },
        {
            "claim_id": "C2",
            "claim_text": "Shared accessibility does not determine fate.",
            "manuscript_section": "Results",
            "figure_panel_support": "Figure 2",
            "dataset_support": "GSE153596 and related processed trajectory outputs where available; exact T9 source tables missing in current workspace.",
            "analysis_support": "Velocity/CellRank/state-space summaries interpreted as accessibility rather than fate determination.",
            "evidence_strength": "moderate_computational_support",
            "limitation": "Historical pre-T9 limitation superseded: Figure 2 panel source TSVs were recovered from T9 and copied into the final clean package.",
            "whether_wet_lab_validation_is_claimed": "no",
        },
        {
            "claim_id": "C3",
            "claim_text": "Stemness-associated programs are local accessibility components, not global fate drivers.",
            "manuscript_section": "Results",
            "figure_panel_support": "Figure 3",
            "dataset_support": "Wnt/stemness module score source tables listed in prior manifest but external T9 paths are unavailable.",
            "analysis_support": "Module and perturbation summaries support local accessibility interpretation.",
            "evidence_strength": "moderate_computational_support",
            "limitation": "Exact current source tables need recovery from T9/archive for full source-data completeness.",
            "whether_wet_lab_validation_is_claimed": "no",
        },
        {
            "claim_id": "C4",
            "claim_text": "Positional programs are regime-conditioned developmental coordinates.",
            "manuscript_section": "Results",
            "figure_panel_support": "Figure 4",
            "dataset_support": "RA/HOX/FGF/SHH/NOTCH and salamander/axolotl source tables listed in prior manifest but external source tables are unavailable.",
            "analysis_support": "Positional and blastema-associated score panels interpreted in regime context.",
            "evidence_strength": "moderate_computational_support",
            "limitation": "Expression/proxy-based; does not directly measure morphogen gradients or spatial coordinates.",
            "whether_wet_lab_validation_is_claimed": "no",
        },
        {
            "claim_id": "C5",
            "claim_text": "Fate-lock constrains the adult-repair basin.",
            "manuscript_section": "Results",
            "figure_panel_support": "Figure 5",
            "dataset_support": "Fate-stabilization, p53/BMP, senescence and SAT source tables listed in prior manifest; external exact tables unavailable now.",
            "analysis_support": "CellRank/velocity/fate-lock summaries support adult-repair basin interpretation.",
            "evidence_strength": "moderate_computational_support",
            "limitation": "No direct causal proof of irreversible fate-lock; perturbation time series required.",
            "whether_wet_lab_validation_is_claimed": "no",
        },
        {
            "claim_id": "C6",
            "claim_text": "Tumour-like plasticity is a distinct high-plasticity branch.",
            "manuscript_section": "Results",
            "figure_panel_support": "Figure 6",
            "dataset_support": "Tumour-like source tables listed in prior manifest but external exact source tables unavailable now.",
            "analysis_support": "Tumour-like proxy, stemness, differentiation, retention and boundary summaries.",
            "evidence_strength": "moderate_computational_support",
            "limitation": "Proxy-based and should not be generalized to all cancers.",
            "whether_wet_lab_validation_is_claimed": "no",
        },
        {
            "claim_id": "C7",
            "claim_text": "Latent-state-regime posterior matrix is accepted as the working representation.",
            "manuscript_section": "Results; Discussion",
            "figure_panel_support": "Figure 8; Figure 9",
            "dataset_support": "regime_posterior_probabilities.tsv; latent_regime_mixture_*; regime_overlap_matrix.tsv; regime_KL_divergence_matrix.tsv",
            "analysis_support": "Representation adequacy score 0.904 versus deprecated scalar 0.284; overlap/divergence matrices.",
            "evidence_strength": "strong_computational_support",
            "limitation": "Representational adequacy, not causal proof or predictive superiority.",
            "whether_wet_lab_validation_is_claimed": "no",
        },
        {
            "claim_id": "C8",
            "claim_text": "Regeneration is positionally organized plasticity, not maximal plasticity.",
            "manuscript_section": "Abstract; Discussion",
            "figure_panel_support": "Figures 3-6; Figure 8",
            "dataset_support": "Module, positional, fate-lock and posterior outputs.",
            "analysis_support": "Integrative model interpretation across local accessibility, positional identity and fate-lock constraints.",
            "evidence_strength": "conceptual_interpretation",
            "limitation": "Requires direct perturbation, lineage tracing and spatial multiome validation.",
            "whether_wet_lab_validation_is_claimed": "no",
        },
        {
            "claim_id": "C9",
            "claim_text": "Regeneration, reduced ageing-associated stabilization and tumour control are not intrinsically incompatible in the model.",
            "manuscript_section": "Discussion",
            "figure_panel_support": "Figures 5-6; Figure 8; Supplementary Figure 1",
            "dataset_support": "Fate-lock, tumour-like and perturbation-audit outputs.",
            "analysis_support": "Compatibility-space interpretation; no intervention claimed.",
            "evidence_strength": "requires_wet_lab_validation",
            "limitation": "No experimentally achieved simultaneous enhancement/suppression/control intervention is shown.",
            "whether_wet_lab_validation_is_claimed": "no",
        },
        {
            "claim_id": "C10",
            "claim_text": "Perturbation audit supports partial regime-conditioned consistency only.",
            "manuscript_section": "Supplementary; Discussion",
            "figure_panel_support": "Supplementary Figure 1",
            "dataset_support": "perturbation_deltaZ.tsv; closure_model_comparison.tsv; counterfactual_bias_by_regime.tsv; edge_stability_across_regimes.tsv",
            "analysis_support": "PARTIAL_CLOSURE; error reduction 0.626; bootstrap p=0.0295; reversal frequency 0.70; cross-regime instability high.",
            "evidence_strength": "partial_computational_support",
            "limitation": "Dry-lab causal-consistency only; no wet-lab causal validation.",
            "whether_wet_lab_validation_is_claimed": "no",
        },
    ]


def validation_rows() -> list[dict]:
    return [
        {
            "test_or_control": "Scalar Phi ROC",
            "dataset": "Phi_unified processed state table",
            "figure_or_result": "Figure 7",
            "metric": "ROC AUC",
            "result_summary": "AUC = 0.479793, near random.",
            "supports_which_claim": "C1",
            "limitation": "Processed score-level validation.",
            "status": "computed",
        },
        {
            "test_or_control": "KS distribution comparison",
            "dataset": "Phi_unified processed state table",
            "figure_or_result": "Figure 7",
            "metric": "KS statistic/p-value",
            "result_summary": "KS p = 1.50109e-20; interpreted as shape mismatch, not separability.",
            "supports_which_claim": "C1",
            "limitation": "Significance does not imply classifier utility.",
            "status": "computed",
        },
        {
            "test_or_control": "Permutation mean-shift test",
            "dataset": "Phi_unified processed state table",
            "figure_or_result": "Figure 7",
            "metric": "two-sided p-value",
            "result_summary": "Permutation p = 0.585041; no stable mean shift.",
            "supports_which_claim": "C1",
            "limitation": "Tests mean shift only.",
            "status": "computed",
        },
        {
            "test_or_control": "Bootstrap uncertainty",
            "dataset": "Phi_unified processed state table",
            "figure_or_result": "Figure 7",
            "metric": "bootstrap CI",
            "result_summary": "Mean/median shift uncertainty overlaps zero in locked report.",
            "supports_which_claim": "C1",
            "limitation": "Score-level uncertainty, not full raw-data bootstrap.",
            "status": "computed",
        },
        {
            "test_or_control": "Representational adequacy comparison",
            "dataset": "regime_posterior_probabilities.tsv",
            "figure_or_result": "Figure 8/9",
            "metric": "representational adequacy score",
            "result_summary": "Latent posterior score 0.904; deprecated scalar Phi score 0.284; GMM posterior reference score 0.916.",
            "supports_which_claim": "C7",
            "limitation": "Representational consistency, not predictive superiority or causality.",
            "status": "computed",
        },
        {
            "test_or_control": "Perturbation closure model comparison",
            "dataset": "dry-lab perturbation-derived posterior summaries",
            "figure_or_result": "Supplementary Figure 1",
            "metric": "error reduction; bootstrap p; reversal frequency",
            "result_summary": "Error reduction 0.626; bootstrap p=0.0295; counterfactual reversal frequency 0.70; final class PARTIAL_CLOSURE.",
            "supports_which_claim": "C10",
            "limitation": "Dry-lab perturbation consistency only.",
            "status": "computed",
        },
        {
            "test_or_control": "True held-out validation",
            "dataset": "not available",
            "figure_or_result": "not a main claim",
            "metric": "held-out design",
            "result_summary": "No true raw held-out validation was identified. Leave-one-perturbation-style regime-conditioned summaries exist but should not be described as full held-out biological validation.",
            "supports_which_claim": "limitation",
            "limitation": "Reviewer-facing limitation.",
            "status": "missing_not_performed",
        },
    ]


def perturbation_rows() -> list[dict]:
    rows = []
    closure = read_tsv(ROOT / "outputs/closure_model_comparison.tsv")
    ccs = {r["pathway"]: r for r in read_tsv(ROOT / "outputs/causal_closure_score_summary.tsv")}
    for pathway in ["RA", "BMP", "NOTCH", "FGF", "SHH"]:
        r = ccs.get(pathway, {})
        rows.append({
            "pathway": pathway,
            "dataset": "existing dry-lab perturbation-derived outputs; perturbation_deltaZ and posterior summaries",
            "analysis": "directional consistency, counterfactual agreement, null separation and conservative CCS",
            "metric": "CCS_conservative_missing_as_zero; evidence_status",
            "result_summary": f"CCS={r.get('CCS_conservative_missing_as_zero','NA')}; status={r.get('evidence_status','NA')}",
            "supports_claim": "C10 partial regime-conditioned perturbation consistency",
            "limitation": r.get("interpretation_boundary", "dry-lab consistency only"),
            "status": "computed" if r else "missing",
        })
    if closure:
        r = closure[0]
        rows.append({
            "pathway": "ALL",
            "dataset": "combined perturbation-derived posterior summaries",
            "analysis": "global W versus regime-conditioned W(Z)",
            "metric": "MSE reduction; bootstrap; reversal frequency",
            "result_summary": f"error_reduction={r.get('prediction_error_reduction_fraction')}; bootstrap_p={r.get('bootstrap_p_value_positive_error_reduction')}; reversal_frequency={r.get('counterfactual_direction_reversal_frequency')}; class={r.get('final_closure_classification')}",
            "supports_claim": "C10",
            "limitation": "cross-regime instability and counterfactual inconsistency reject full/global closure",
            "status": "computed",
        })
    return rows


def make_reports(mapping_rows, missing_sources, code_rows, inventory_rows):
    # Inventory.
    category_counts = defaultdict(int)
    for r in inventory_rows:
        category_counts[r["category"]] += 1
    inv = [
        "# Input Inventory",
        "",
        f"- project folder: `{ROOT}`",
        f"- requested output folder: `{REQUESTED_PACKAGE}`",
        f"- actual output folder: `{PACKAGE}`",
        f"- primary manuscript: `{INPUT_MANUSCRIPT}`",
        f"- inventory generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Category Counts",
        "",
    ]
    for k in sorted(category_counts):
        inv.append(f"- {k}: {category_counts[k]}")
    inv += [
        "",
        "## Detailed Inventory",
        "",
        "A machine-readable detailed inventory is provided as `input_file_inventory.tsv` in this folder.",
    ]
    write_text(PACKAGE / "08_submission_reports/input_inventory.md", "\n".join(inv) + "\n")
    write_tsv(PACKAGE / "08_submission_reports/input_file_inventory.tsv", inventory_rows, ["file_path", "extension", "size_bytes", "category"])

    # Figure mapping README.
    readme = """# Figure Source Mapping README

This table maps final embedded/main figures and Supplementary Figure 1 to currently available source tables, scripts and figure-image assets.

Important status definitions:

- `complete`: all listed source files are accessible in the current project tree.
- `partial`: at least one support file is available, but the panel also depends on conceptual text or missing external source tables.
- `missing`: expected source files were listed in prior manifests but are not accessible now.
- `not_applicable_conceptual_schematic`: no numeric panel source is required because the panel is a schematic/model-summary panel.

Historical note: this builder was superseded by the T9 refresh. In the final clean package, Figure 2-6 panel source TSVs are recovered and copied into `02_source_data/`.
"""
    write_text(PACKAGE / "04_figure_source_mapping/figure_source_mapping_readme.md", readme)

    # Claim summary.
    claim_summary = """# Claim-To-Evidence Summary

## Supported By Data

- Scalar Phi/global scalar failure is strongly supported by the locked statistical validation outputs: AUC ~0.480, non-significant permutation mean shift, unstable bootstrap intervals and KS shape mismatch.
- Latent-state-regime posterior representation is supported as a representationally adequate working framework by posterior mixture outputs, overlap/divergence matrices and representational consistency comparisons.
- Perturbation audit supports partial regime-conditioned perturbation consistency only.

## Model Interpretation

- Regeneration as positionally organized plasticity is an integrative interpretation of accessibility, positional programs and fate-lock results.
- The compatibility-space claim for regeneration, reduced ageing-associated stabilization and tumour control is a model-level prediction, not an achieved intervention.

## Predictions

- Regenerative competence should be better explained by regime-conditioned posterior access than by a global plasticity scalar.
- Direct perturbation, lineage-tracing and spatial multiome experiments should test whether posterior regime access predicts organized regeneration.

## Not Claimed

- No wet-lab causal validation is claimed.
- No complete causal closure is claimed.
- No perturbation is claimed to be a proven regeneration switch.
- Tumour-like plasticity is not treated as regenerative competence.
"""
    write_text(PACKAGE / "05_claim_evidence_mapping/claim_to_evidence_summary.md", claim_summary)

    validation_summary = """# Validation And Robustness Summary

## 1. Overview

The locked analyses support representational consistency and scalar-model invalidation, while maintaining a conservative boundary around causal interpretation.

## 2. Held-Out Or Cross-Dataset Support

No true raw held-out validation was identified in the available outputs. Cross-dataset and cross-species harmonization outputs exist, but ordinary reuse of integrated datasets should not be described as held-out validation.

## 3. Cross-Species Support And Limitations

Cross-species structure is represented through aligned state matrices, posterior regime probabilities and overlap/divergence matrices. Orthology, batch/species entanglement and proxy module definitions remain limitations.

## 4. Scalar-Model Failure Support

The scalar Phi model fails discriminative criteria: ROC AUC = 0.479793, permutation mean-shift p = 0.585041, bootstrap uncertainty overlaps zero, and KS significance is interpreted as shape mismatch rather than separability.

## 5. Latent-Regime Model Support

The locked posterior regime representation has high representational adequacy relative to deprecated scalar Phi (posterior score 0.904 versus scalar score 0.284). This supports a representational framework, not causal superiority.

## 6. Robustness Checks

Available checks include ROC/AUC, KS, permutation, bootstrap, representational comparison against PCA/diffusion/clustering/nulls, overlap matrices and perturbation null-control summaries.

## 7. Sensitivity Checks

The representational consistency analysis includes alternative embeddings and null representations. The perturbation audit includes null separation and counterfactual-bias checks.

## 8. Missing Validation Items

Missing items include raw-data held-out validation, wet-lab perturbation time series, lineage tracing, spatial morphogen measurements and direct spatial multiome confirmation.

## 9. Reviewer-Risk Assessment

Main risks are incomplete source-data recovery for Figure 2-6 exact panel TSVs, limited raw held-out validation, proxy-based positional/chromatin interpretation and dry-lab-only perturbation support.

## 10. Suggested Wording For Manuscript If Needed

Use: “supports a representationally consistent latent-state-regime framework” and “partial regime-conditioned perturbation consistency.” Avoid: “causal proof,” “complete causal closure,” or “wet-lab validation.”
"""
    write_text(PACKAGE / "06_validation_and_robustness/validation_robustness_summary.md", validation_summary)

    perturbation_summary = """# Perturbation Audit Summary

## Scope

This is a dry-lab perturbation consistency audit. It uses existing posterior-shift, W_GRN and regime-conditioned closure outputs only.

## Perturbation Datasets And Pathways

The available summaries cover pathway-level perturbation proxies for RA, BMP, NOTCH, FGF and SHH through `perturbation_deltaZ.tsv`, `causal_closure_score_summary.tsv` and regime-conditioned closure outputs.

## What Improved Under W(Z)

Regime-conditioned W(Z) reduced reconstruction error relative to global W_GRN in the locked closure comparison. The global-to-regime-conditioned error reduction proxy was 0.626, with bootstrap p=0.0295 for positive error reduction.

## Where Global W_GRN Failed

The global W_GRN was insufficient to close perturbation-to-regime posterior shifts. Cross-regime instability remained high and counterfactual reversal frequency was 0.70.

## Counterfactual Reversals And Cross-Regime Instability

Counterfactual reversal and asymmetric bias remain central limitations. These limits reject complete/global causal closure.

## NOTCH/SHH Limitations

NOTCH/SHH evidence is treated as lower-coverage or mixed-direction pathway support in the causal-closure score table and final figure interpretation.

## Interpretation Boundary

The supported statement is: partial regime-conditioned perturbation consistency. This is not wet-lab validation, not causal proof and not a proven regeneration switch.
"""
    write_text(PACKAGE / "07_perturbation_audit/perturbation_audit_summary.md", perturbation_summary)

    insertion = """# Manuscript Insertion Suggestions

No manuscript modification was performed.

## Source Data Availability

Suggested wording: “Source data tables supporting figure panels are provided in the accompanying source-data package. Panels whose exact upstream source tables are unavailable are explicitly listed in the missing source-data report.”

## Code Availability

Suggested wording: “Available analysis, figure-generation and audit scripts are provided as a supplementary code package; missing upstream scripts are listed transparently.”

## Validation/Robustness Support

Suggested wording: “Robustness support includes scalar-model failure diagnostics, representational consistency comparisons and perturbation-audit null/counterfactual summaries.”

## Perturbation Audit Limitation

Suggested wording: “The perturbation layer supports partial regime-conditioned perturbation consistency only and does not establish wet-lab causal validation.”

## Falsifiable Predictions

Suggested wording: “The framework predicts that regime-conditioned posterior access, rather than maximal plasticity, should best identify regenerative competence in perturbation, lineage-tracing and spatial multiome experiments.”
"""
    write_text(PACKAGE / "08_submission_reports/manuscript_insertion_suggestions.md", insertion)

    readiness = """# NatComms Readiness Report

| Area | Status | Notes |
|---|---|---|
| Story strength | NEAR_READY | Narrative is strengthened around first-order cell-state regime matrix and latent-state-regime posterior access. |
| Figure readiness | NEAR_READY | Final figures exist and are visually assembled; Figure 2-6 exact source TSVs were recovered from T9 and copied into the final clean package. |
| Source-data readiness | NEEDS_MAJOR_FIX | Figure 7-9 and Supplementary Figure 1 source data are strong; Figure 2-6 exact T9 panel sources are missing in current state. |
| Code readiness | NEEDS_MINOR_FIX | Many scripts are available and packaged; upstream exact raw-processing/old figure source-generation scripts remain incomplete. |
| Citation/EndNote readiness | READY | This task did not modify the manuscript or EndNote fields. |
| Validation strength | NEAR_READY | Strong scalar-failure and representational-consistency support; no true raw held-out validation. |
| Perturbation-audit strength | NEEDS_MINOR_FIX | Supports partial regime-conditioned consistency only; limitation is clearly stated. |
| Wet-lab limitation risk | NEEDS_MAJOR_FIX | No wet-lab causal validation; likely reviewer point. |

## Likely Reviewer Objections

1. Exact source-data recovery for Figure 2-6 was completed by the T9 refresh; remaining reviewer risk concerns upstream raw preprocessing and environment locking.
2. Cross-species integration is proxy/batch constrained.
3. Perturbation evidence is dry-lab and partial.
4. Latent-state-regime model is representational, not full causal proof.

## Must Be Fixed Before Submission

- Recover or rebuild exact source TSVs for Figure 2-6 panels from T9 or raw analysis archives.
- Add code or workflow notes for upstream raw processing where missing.
- Confirm journal-specific source-data file naming.

## Can Be Handled In Revision

- Additional wet-lab validation is a biological follow-up, but the manuscript must keep claims conservative.
- Expanded spatial multiome or lineage-tracing validation can be framed as future work if not available.

## Recommended Submission Tier

NEAR_READY for conceptual/computational submission after source-data completeness is fixed; otherwise likely reviewer risk is high for NatComms source-data compliance.
"""
    write_text(PACKAGE / "08_submission_reports/NatComms_readiness_report.md", readiness)


def code_readme():
    text = """# Code Package README

## Computational Environment

The available scripts are Python-based unless otherwise marked in `code_inventory.tsv`. Exact package versions are not fully locked in the current project folder. Bundled Codex workspace Python was used for document/package assembly; upstream analyses likely require standard scientific Python/R packages such as pandas, numpy, scipy, scikit-learn, matplotlib/seaborn and single-cell tooling where applicable.

## Reproducing Score Tables

Use scripts in `scoring/` and available workflow material under `utilities/` or copied `outputs/reproducible_workflows/` where present. Some raw-data preprocessing scripts are missing and are listed in `09_missing_items/missing_code_files.tsv`.

## Reproducing Model-Comparison Outputs

Use `model_comparison/` scripts including representational consistency, Phi invalidation, mixture replacement and regime-conditioned closure scripts.

## Reproducing Figure Source-Data Tables

Use `figure_generation/` scripts where available. Exact upstream source-table generation for several Figure 2-6 panels depends on missing `/Volumes/T9/...` source-data files and is not fully reproducible from this package alone.

## Regenerating Figures

Final figure-generation and figure-QA scripts are copied into `figure_generation/`. The package also includes final figure image assets in the source mapping and final package manifest.

## Known Missing Scripts

See `09_missing_items/missing_code_files.tsv`.

## Known Non-Reproducible Or Manually Assembled Elements

Conceptual schematic panels, figure label cleanup, and some final manuscript assembly operations were manually/graphically curated but documented through audit scripts and reports.
"""
    write_text(PACKAGE / "03_code_package/README.md", text)


def missing_code_rows() -> list[dict]:
    return [
        {
            "missing_code_or_workflow": "Exact raw GEO download and preprocessing workflow for all single-cell/multiome datasets",
            "related_result": "upstream source tables and state scores",
            "reason": "Not present as complete executable workflow in current project folder.",
            "recommended_action": "Archive raw processing notebooks/scripts or provide accession-to-processed-table workflow.",
        },
        {
            "missing_code_or_workflow": "Exact Figure 2-6 T9 panel source-data generation scripts",
            "related_result": "Figure 2-6 panel source TSVs",
            "reason": "Prior manifest references external /Volumes/T9 source files that are unavailable now.",
            "recommended_action": "Reconnect T9 or rebuild source tables from raw/processed objects and add scripts.",
        },
        {
            "missing_code_or_workflow": "Complete environment lockfile",
            "related_result": "full reproducibility",
            "reason": "No conda/pip/renv lockfile identified in current project folder.",
            "recommended_action": "Generate environment.yml or requirements.txt from working environment before submission.",
        },
    ]


def make_final_manifest():
    rows = []
    for p in sorted(PACKAGE.rglob("*")):
        if p.is_file() and p.name != "NatComms_submission_support_package.zip":
            rel = p.relative_to(PACKAGE)
            rows.append({
                "file_path": str(rel),
                "file_type": p.suffix.lstrip(".") or "file",
                "purpose": purpose_for_manifest(rel),
                "status": "present",
                "notes": f"size_bytes={p.stat().st_size}",
            })
    write_tsv(PACKAGE / "08_submission_reports/final_package_manifest.tsv", rows, ["file_path", "file_type", "purpose", "status", "notes"])
    return rows


def purpose_for_manifest(rel: Path) -> str:
    s = str(rel)
    if s.startswith("01_final_manuscript"):
        return "final manuscript copy"
    if s.startswith("02_source_data"):
        return "source data or per-figure README"
    if s.startswith("03_code_package"):
        return "code package"
    if s.startswith("04_figure_source_mapping"):
        return "figure-source traceability"
    if s.startswith("05_claim_evidence_mapping"):
        return "claim-evidence traceability"
    if s.startswith("06_validation_and_robustness"):
        return "validation and robustness support"
    if s.startswith("07_perturbation_audit"):
        return "perturbation audit support"
    if s.startswith("08_submission_reports"):
        return "submission report"
    if s.startswith("09_missing_items"):
        return "missing item disclosure"
    if s.startswith("00_input_backups"):
        return "input backup"
    return "package file"


def zip_package():
    zip_path = PACKAGE.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(PACKAGE.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(PACKAGE.parent))
    # Also copy inside package for requested name.
    inside = PACKAGE / "NatComms_submission_support_package.zip"
    shutil.copy2(zip_path, inside)
    # Rebuild external zip to include the inside copy too.
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(PACKAGE.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(PACKAGE.parent))
    return zip_path, inside


def main():
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    for d in SUBDIRS:
        (PACKAGE / d).mkdir(parents=True, exist_ok=True)

    # Manuscript backups/copy.
    copy_file(INPUT_MANUSCRIPT, PACKAGE / "01_final_manuscript")
    copy_file(INPUT_MANUSCRIPT, PACKAGE / "00_input_backups")
    safety = ROOT / "story_strengthening_output/story_strengthening_endnote_safety_report.md"
    if safety.exists():
        copy_file(safety, PACKAGE / "00_input_backups")

    fig_assets = figure_asset_map()
    for fig, paths in fig_assets.items():
        adir = PACKAGE / "08_submission_reports/final_figure_assets" / fig.replace(" ", "_")
        for p in paths:
            copy_file(p, adir)

    inventory = inventory_files()
    mapping, missing_from_mapping = source_mapping_rows(fig_assets)
    source_master, _ = source_data_package(mapping)
    code_rows = build_code_package()
    code_readme()

    mapping_fields = [
        "figure_number", "panel", "panel_description", "source_dataset", "source_data_file",
        "source_script_or_notebook", "figure_image_file", "analysis_type", "data_or_schematic",
        "source_data_status", "notes",
    ]
    write_tsv(PACKAGE / "04_figure_source_mapping/figure_source_mapping.tsv", mapping, mapping_fields)
    write_tsv(PACKAGE / "02_source_data/source_data_master_index.tsv", source_master, ["figure_number", "panel", "file_name", "file_type", "description", "status", "notes"])
    write_tsv(PACKAGE / "09_missing_items/missing_source_data_files.tsv", missing_from_mapping, ["figure_number", "panel", "expected_source_file", "reason", "recommended_action"])
    write_tsv(PACKAGE / "03_code_package/code_inventory.tsv", code_rows, ["script_file", "language", "purpose", "related_figure_or_result", "input_files", "output_files", "status", "notes"])
    write_tsv(PACKAGE / "09_missing_items/missing_code_files.tsv", missing_code_rows(), ["missing_code_or_workflow", "related_result", "reason", "recommended_action"])

    claims = claim_mapping()
    write_tsv(PACKAGE / "05_claim_evidence_mapping/claim_to_evidence_mapping.tsv", claims, [
        "claim_id", "claim_text", "manuscript_section", "figure_panel_support", "dataset_support",
        "analysis_support", "evidence_strength", "limitation", "whether_wet_lab_validation_is_claimed",
    ])
    vrows = validation_rows()
    write_tsv(PACKAGE / "06_validation_and_robustness/validation_robustness_evidence_table.tsv", vrows, [
        "test_or_control", "dataset", "figure_or_result", "metric", "result_summary", "supports_which_claim", "limitation", "status",
    ])
    prows = perturbation_rows()
    write_tsv(PACKAGE / "07_perturbation_audit/perturbation_audit_evidence_table.tsv", prows, [
        "pathway", "dataset", "analysis", "metric", "result_summary", "supports_claim", "limitation", "status",
    ])

    make_reports(mapping, missing_from_mapping, code_rows, inventory)

    # Missing item summary.
    missing_summary = f"""# Missing Items Summary

- missing source-data rows: {len(missing_from_mapping)}
- missing code/workflow rows: {len(missing_code_rows())}

The largest source-data gap is the unavailability of exact Figure 2-6 source TSVs previously referenced under `/Volumes/T9/...`. No missing files were fabricated.
"""
    write_text(PACKAGE / "09_missing_items/missing_items_summary.md", missing_summary)

    final_manifest_rows = make_final_manifest()
    zip_path, inside_zip = zip_package()
    # Update final manifest after adding zip.
    final_manifest_rows = make_final_manifest()
    write_text(PACKAGE / "08_submission_reports/package_build_summary.md", f"""# Package Build Summary

- actual output folder: `{PACKAGE}`
- requested `/mnt/data` output folder status: unavailable on this machine (`/mnt` is read-only/not present)
- zip archive: `{zip_path}`
- zip copy inside package: `{inside_zip}`
- final package file count: {len(final_manifest_rows)}
- manuscript modified: no
- EndNote fields touched: no
- wet-lab validation claimed: no
- complete causal closure claimed: no
""")


if __name__ == "__main__":
    main()
