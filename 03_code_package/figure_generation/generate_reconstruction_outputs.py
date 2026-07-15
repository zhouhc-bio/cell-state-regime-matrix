#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)


def write_tsv(name: str, rows: list[dict[str, object]], columns: list[str]) -> None:
    path = OUT / name
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})


def svg_text(x: float, y: float, text: str, size: int = 12, fill: str = "#17202a", anchor: str = "middle") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{size}" fill="{fill}" text-anchor="{anchor}">{html.escape(text)}</text>'
    )


def svg_rect(x: float, y: float, w: float, h: float, fill: str, stroke: str = "#263238", rx: float = 6) -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'


def write_svg(name: str, body: str, width: int, height: int) -> None:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        f'<rect width="100%" height="100%" fill="#f8fafc"/>\n'
        f"{body}\n</svg>\n"
    )
    (OUT / name).write_text(svg, encoding="utf-8")


datasets = [
    {
        "dataset": "GSE153596",
        "species": "Mus musculus",
        "geo_title": "Single Cell RNA Sequencing of neonatal and juvenile mice skin (wound and unwounded)",
        "assay": "10x scRNA-seq with velocyto loom supplementary files",
        "role_in_model": "trajectory / RNA velocity / CellRank terminal-state analysis",
        "public_files": "GSE153596_RAW.tar, 12 loom.gz files, total archive ~705 MB",
        "metadata_evidence": "GEO series metadata and GEO supplementary filelist inspected 2026-06-18",
        "workspace_status": "no local raw matrix, h5ad, loom, scVelo, or CellRank object found",
        "analysis_status": "reported completed by user; not independently revalidated in this workspace",
        "limitations": "mouse skin wound system; cross-species mapping required before unified human/mouse state space",
        "geo_url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE153596",
    },
    {
        "dataset": "GSE90546",
        "species": "Homo sapiens",
        "geo_title": "A multiplexed single-cell CRISPR screening platform enables systematic dissection of the unfolded protein response",
        "assay": "Perturb-seq / CRISPRi scRNA-seq",
        "role_in_model": "perturbation-to-state response inference candidate",
        "public_files": "GSE90546_RAW.tar, 10x matrices and cell_identities files, archive ~942 MB",
        "metadata_evidence": "GEO series metadata and GEO supplementary filelist inspected 2026-06-18",
        "workspace_status": "not downloaded; no perturbation identities available locally",
        "analysis_status": "input dataset validated as CRISPRi Perturb-seq; causal response not computed",
        "limitations": "UPR-focused perturbation screen, not explicitly a Wnt/BMP/RA fate perturbation screen by GEO metadata",
        "geo_url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE90546",
    },
    {
        "dataset": "GSE195467",
        "species": "Homo sapiens",
        "geo_title": "Reconstruction of human Somitogenesis with pluripotent stem cells",
        "assay": "10x scRNA-seq time course",
        "role_in_model": "developmental positional information / somitogenesis time-order validation",
        "public_files": "GSE195467_RAW.tar, 9 sample tar.gz files inside, archive ~332 MB",
        "metadata_evidence": "GEO series metadata and GEO supplementary filelist inspected 2026-06-18",
        "workspace_status": "not downloaded; sample/treatment labels unavailable locally",
        "analysis_status": "dataset validated as somitogenesis time course; RA/BMP modulation label not confirmed from GEO metadata",
        "limitations": "do not treat as RA/BMP perturbation evidence until sample-level labels or paper metadata confirm treatment design",
        "geo_url": "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE195467",
    },
]

write_tsv(
    "dataset_registry.tsv",
    datasets,
    [
        "dataset",
        "species",
        "geo_title",
        "assay",
        "role_in_model",
        "public_files",
        "metadata_evidence",
        "workspace_status",
        "analysis_status",
        "limitations",
        "geo_url",
    ],
)


pipeline = [
    ("R1", "dataset registry and accession validation", "completed_this_run", "GEO metadata/filelists inspected", "No expression matrix downloaded."),
    ("R2", "raw matrix ingestion and QC", "not_computed_this_run", "no local matrices", "Requires GEO tar download or user-provided h5ad/loom."),
    ("R3", "normalization, HVG selection, batch integration", "not_computed_this_run", "no local matrices", "Do not infer integrated UMAP from absent objects."),
    ("R4", "cell type and fate-state annotation", "schema_defined_only", "marker/state signatures emitted", "Cell-level labels require expression matrix."),
    ("R5", "unified fate-state scoring", "schema_defined_only", "state signature table emitted", "Scores not computed."),
    ("R6", "trajectory and pseudotime reconstruction", "reported_completed_not_verified", "user stated pseudotime validation across 3 datasets", "No local pseudotime vectors found."),
    ("R7", "RNA velocity and CellRank on GSE153596", "reported_completed_not_verified", "user stated scVelo + CellRank completed", "No local velocity graph, fate probabilities, or terminal-state output found."),
    ("R8", "cross-dataset pseudotime validation", "reported_completed_not_verified", "user stated validation completed", "No reproducible validation table found."),
    ("R9", "multiome ATAC/RNA preprocessing", "reported_partial_not_verified", "user stated partially processed", "No local ATAC fragment/peak/cell metadata found."),
    ("R10", "chromVAR motif deviation analysis", "incomplete", "no motif deviation matrix found", "Must compute before TF activity claims from ATAC."),
    ("R11", "Cicero / SCARlink regulatory links", "partial_or_missing", "no coaccessibility or peak-gene table found", "Must compute before chromatin-linked GRN claims."),
    ("R12", "SCENIC+ full GRN reconstruction", "not_computed", "no SCENIC+ eRegulon output found", "Do not claim SCENIC+ regulons."),
    ("R13", "chromatin potential mapping", "not_computed", "no chromatin potential output found", "Do not claim chromatin potential."),
    ("R14", "perturbation-to-fate causal inference graph", "design_only_critical_missing", "GSE90546/GSE195467 metadata inspected", "No perturbation effect sizes or causal edges computed."),
]

write_tsv(
    "r1_r14_module_status.tsv",
    [
        {
            "module": m,
            "module_name": n,
            "status": s,
            "evidence_available": e,
            "constraint_or_next_step": c,
        }
        for m, n, s, e, c in pipeline
    ],
    ["module", "module_name", "status", "evidence_available", "constraint_or_next_step"],
)


signatures = [
    ("stemness", "Wnt/β-catenin/TCF-MYC", "WNT3A", "ligand/pathway"),
    ("stemness", "Wnt/β-catenin/TCF-MYC", "CTNNB1", "signal transducer"),
    ("stemness", "Wnt/β-catenin/TCF-MYC", "TCF7", "TF"),
    ("stemness", "Wnt/β-catenin/TCF-MYC", "TCF7L2", "TF"),
    ("stemness", "Wnt/β-catenin/TCF-MYC", "LEF1", "TF"),
    ("stemness", "Wnt/β-catenin/TCF-MYC", "MYC", "TF/effector"),
    ("stemness", "Wnt/β-catenin/TCF-MYC", "LGR5", "target/state marker"),
    ("stemness", "Wnt/β-catenin/TCF-MYC", "AXIN2", "target/pathway reporter"),
    ("fate_lock", "BMP-SMAD / p53 / p16 / Rb / ARF", "BMP4", "ligand/pathway"),
    ("fate_lock", "BMP-SMAD / p53 / p16 / Rb / ARF", "BMPR1A", "receptor"),
    ("fate_lock", "BMP-SMAD / p53 / p16 / Rb / ARF", "SMAD1", "TF/cofactor"),
    ("fate_lock", "BMP-SMAD / p53 / p16 / Rb / ARF", "SMAD5", "TF/cofactor"),
    ("fate_lock", "BMP-SMAD / p53 / p16 / Rb / ARF", "SMAD4", "TF/cofactor"),
    ("fate_lock", "BMP-SMAD / p53 / p16 / Rb / ARF", "ID1", "target"),
    ("fate_lock", "BMP-SMAD / p53 / p16 / Rb / ARF", "TP53", "TF/tumor suppressor"),
    ("fate_lock", "BMP-SMAD / p53 / p16 / Rb / ARF", "CDKN1A", "cell-cycle arrest"),
    ("fate_lock", "BMP-SMAD / p53 / p16 / Rb / ARF", "CDKN2A", "p16/ARF locus"),
    ("fate_lock", "BMP-SMAD / p53 / p16 / Rb / ARF", "RB1", "cell-cycle gate"),
    ("fate_lock", "BMP-SMAD / p53 / p16 / Rb / ARF", "MDM2", "p53 feedback"),
    ("senescence", "p53 / p16 / SASP", "CDKN1A", "arrest marker"),
    ("senescence", "p53 / p16 / SASP", "CDKN2A", "senescence marker"),
    ("senescence", "p53 / p16 / SASP", "SERPINE1", "senescence/SASP"),
    ("senescence", "p53 / p16 / SASP", "IL6", "SASP"),
    ("senescence", "p53 / p16 / SASP", "CXCL8", "SASP"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "ALDH1A2", "RA synthesis"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "RARA", "TF/nuclear receptor"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "RARB", "TF/RA response"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "RXRA", "TF/nuclear receptor"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "CYP26A1", "RA catabolism/response"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "HOXA1", "HOX TF"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "HOXA9", "HOX TF"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "HOXB1", "HOX TF"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "FGF8", "ligand/pathway"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "FGFR1", "receptor"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "ETV4", "TF/FGF response"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "ETV5", "TF/FGF response"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "DUSP6", "FGF/MAPK reporter"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "SHH", "ligand/pathway"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "GLI1", "TF/SHH response"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "PTCH1", "SHH target"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "NOTCH1", "receptor"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "RBPJ", "TF/cofactor"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "HES1", "TF/Notch response"),
    ("positional", "RA / HOX / FGF / SHH / NOTCH", "HEY1", "TF/Notch response"),
    ("tumor_like_plasticity", "MYC / EMT / cycling", "MYC", "TF"),
    ("tumor_like_plasticity", "MYC / EMT / cycling", "E2F1", "TF/cell-cycle"),
    ("tumor_like_plasticity", "MYC / EMT / cycling", "MKI67", "cycling marker"),
    ("tumor_like_plasticity", "MYC / EMT / cycling", "VIM", "EMT marker"),
    ("tumor_like_plasticity", "MYC / EMT / cycling", "ZEB1", "EMT TF"),
    ("tumor_like_plasticity", "MYC / EMT / cycling", "SNAI1", "EMT TF"),
    ("differentiated_stable", "lineage maturation", "KRT10", "epithelial differentiation"),
    ("differentiated_stable", "lineage maturation", "IVL", "epidermal differentiation"),
    ("differentiated_stable", "lineage maturation", "COL1A1", "mesenchymal differentiation"),
    ("differentiated_stable", "lineage maturation", "MYOD1", "myogenic differentiation"),
    ("differentiated_stable", "lineage maturation", "MEOX1", "somitic mesoderm"),
]

signature_rows = []
for axis, system, gene, role in signatures:
    signature_rows.append(
        {
            "state_axis": axis,
            "system": system,
            "human_symbol": gene,
            "mouse_symbol": gene.title() if gene not in {"MYC", "MKI67"} else {"MYC": "Myc", "MKI67": "Mki67"}[gene],
            "role": role,
            "evidence_status": "curated_signature_not_scored",
        }
    )

write_tsv(
    "state_signature_gene_sets.tsv",
    signature_rows,
    ["state_axis", "system", "human_symbol", "mouse_symbol", "role", "evidence_status"],
)


edges = [
    ("WNT ligand/receptor", "CTNNB1", "activates/stabilizes", "protein_signal", "stemness"),
    ("CTNNB1", "TCF7L2/LEF1", "coactivates", "TF_complex", "stemness"),
    ("TCF7L2/LEF1", "MYC", "transcriptional_activation", "gene_regulation", "stemness"),
    ("TCF7L2/LEF1", "AXIN2", "transcriptional_activation", "gene_regulation", "stemness"),
    ("TCF7L2/LEF1", "LGR5", "transcriptional_activation", "gene_regulation", "stemness"),
    ("BMP ligand/receptor", "SMAD1/5-SMAD4", "activates", "TF_complex", "fate_lock"),
    ("SMAD1/5-SMAD4", "ID1/ID2/ID3", "transcriptional_activation", "gene_regulation", "fate_lock"),
    ("SMAD1/5-SMAD4", "CDKN1A", "candidate_activation", "gene_regulation", "fate_lock"),
    ("DNA damage/stress", "TP53", "activates", "TF", "fate_lock"),
    ("TP53", "CDKN1A", "transcriptional_activation", "gene_regulation", "senescence"),
    ("TP53", "MDM2", "negative_feedback_target", "gene_regulation", "fate_lock"),
    ("CDKN2A/p16", "RB1", "reinforces_hypophosphorylated_RB", "cell_cycle_gate", "senescence"),
    ("CDKN2A/ARF", "MDM2", "inhibits", "protein_signal", "fate_lock"),
    ("RB1", "E2F targets", "represses", "cell_cycle_gate", "senescence"),
    ("RA", "RARA/RXRA", "activates", "nuclear_receptor", "positional"),
    ("RARA/RXRA", "HOX genes", "transcriptional_regulation", "gene_regulation", "positional"),
    ("RARA/RXRA", "CYP26A1", "transcriptional_activation", "gene_regulation", "positional"),
    ("FGF ligand/receptor", "MAPK-ETV4/ETV5", "activates", "TF_pathway", "positional"),
    ("MAPK-ETV4/ETV5", "DUSP6/SPRY2", "transcriptional_activation", "gene_regulation", "positional"),
    ("SHH", "GLI1/GLI2", "activates", "TF_pathway", "positional"),
    ("GLI1/GLI2", "PTCH1/HHIP", "transcriptional_activation", "gene_regulation", "positional"),
    ("NOTCH receptor", "RBPJ-NICD", "activates", "TF_complex", "positional"),
    ("RBPJ-NICD", "HES1/HEY1", "transcriptional_activation", "gene_regulation", "positional"),
    ("MYC", "cell-cycle/growth program", "activates", "gene_program", "tumor_like_plasticity"),
    ("EMT TFs", "motility/plasticity program", "activates", "gene_program", "tumor_like_plasticity"),
]

network_rows = [
    {
        "source": s,
        "target": t,
        "interaction": i,
        "edge_layer": layer,
        "state_axis": axis,
        "evidence_status": "curated_prior_not_data_derived",
        "required_data_to_validate": "RNA effect size plus chromVAR/SCENIC+/peak-gene evidence where applicable",
    }
    for s, t, i, layer, axis in edges
]

write_tsv(
    "candidate_regulatory_network_edges.tsv",
    network_rows,
    [
        "source",
        "target",
        "interaction",
        "edge_layer",
        "state_axis",
        "evidence_status",
        "required_data_to_validate",
    ],
)


states = [
    "stem_like",
    "differentiating_positional",
    "differentiated_stable",
    "fate_lock_high",
    "senescence_deep",
    "tumor_like_metastable",
]

transition_rows = []
for src in states:
    row = {"from_state": src}
    for dst in states:
        row[dst] = "NA"
    row["evidence_status"] = "not_computed"
    row["reason"] = "requires cell-level state labels and trajectory/velocity transition probabilities"
    transition_rows.append(row)

write_tsv(
    "differential_state_transition_matrix_template.tsv",
    transition_rows,
    ["from_state"] + states + ["evidence_status", "reason"],
)

prior_allowed = {
    ("stem_like", "differentiating_positional"),
    ("stem_like", "tumor_like_metastable"),
    ("differentiating_positional", "differentiated_stable"),
    ("differentiating_positional", "fate_lock_high"),
    ("fate_lock_high", "senescence_deep"),
    ("tumor_like_metastable", "stem_like"),
    ("tumor_like_metastable", "differentiating_positional"),
    ("differentiated_stable", "fate_lock_high"),
}
prior_rows = []
for src in states:
    row = {"from_state": src}
    for dst in states:
        row[dst] = 1 if (src, dst) in prior_allowed or src == dst else 0
    row["evidence_status"] = "hypothesis_only_not_data_derived"
    prior_rows.append(row)

write_tsv(
    "prior_transition_adjacency_hypothesis.tsv",
    prior_rows,
    ["from_state"] + states + ["evidence_status"],
)


perturbations = [
    ("CRISPRi target gene", "GSE90546", "target vs non-targeting cells", "state score shift, terminal probability shift", "not_computed"),
    ("RA modulation", "GSE195467", "condition label required", "positional/HOX score shift", "label_unconfirmed"),
    ("BMP modulation", "GSE195467", "condition label required", "fate-lock/SMAD score shift", "label_unconfirmed"),
    ("Wnt activation/inhibition", "not assigned", "external perturbation dataset required", "stemness score and plastic transition shift", "missing_dataset"),
    ("FGF modulation", "GSE195467 candidate", "sample label/time model required", "FGF/MAPK positional score shift", "not_computed"),
    ("NOTCH modulation", "not assigned", "external perturbation dataset required", "segmentation/oscillation score shift", "missing_dataset"),
]

write_tsv(
    "perturbation_response_map_template.tsv",
    [
        {
            "perturbation": p,
            "dataset": d,
            "contrast": c,
            "primary_readout": r,
            "evidence_status": s,
            "minimum_acceptance_criteria": "effect size, FDR, bootstrap sign stability, and traceable input cells",
        }
        for p, d, c, r, s in perturbations
    ],
    [
        "perturbation",
        "dataset",
        "contrast",
        "primary_readout",
        "evidence_status",
        "minimum_acceptance_criteria",
    ],
)


causal_edges = [
    ("perturbation_or_treatment", "pathway_activity_score", "causal_effect_estimation", "R14 design; not estimated"),
    ("pathway_activity_score", "TF_activity_or_motif_deviation", "mediation", "requires chromVAR/SCENIC+"),
    ("TF_activity_or_motif_deviation", "chromatin_accessibility", "regulatory_coupling", "requires ATAC/multiome"),
    ("chromatin_accessibility", "GRN_edge_weight", "peak_to_gene_support", "requires Cicero/SCARlink/SCENIC+"),
    ("GRN_edge_weight", "fate_state_probability", "state_transition_model", "requires CellRank/trajectory probabilities"),
    ("fate_state_probability", "attractor_shift_label", "classification", "requires pre-registered thresholds"),
]

write_tsv(
    "r14_causal_graph_edges_design.tsv",
    [
        {
            "source_node": s,
            "target_node": t,
            "analysis_role": r,
            "status": st,
            "evidence_status": "design_only_not_data_derived",
        }
        for s, t, r, st in causal_edges
    ],
    ["source_node", "target_node", "analysis_role", "status", "evidence_status"],
)


attractor_claims = [
    ("stemness recovery", "not_claimed", "requires increased stemness score plus transition probability into stem_like state after perturbation"),
    ("fate-lock reinforcement", "not_claimed", "requires BMP/SMAD/p53/p16/Rb axis score increase plus reduced exit probability"),
    ("senescence stabilization", "not_claimed", "requires senescence signature increase and terminal/deep-attractor probability"),
    ("tumor-like plastic transition", "not_claimed", "requires MYC/EMT/cycling score increase plus metastable transition dynamics"),
]

write_tsv(
    "attractor_claims_ledger.tsv",
    [
        {
            "attractor_shift": a,
            "claim_status": s,
            "required_traceable_data_output": r,
            "current_evidence": "not available in current workspace",
        }
        for a, s, r in attractor_claims
    ],
    ["attractor_shift", "claim_status", "required_traceable_data_output", "current_evidence"],
)


chromatin_rows = [
    ("chromVAR", "motif deviation matrix", "not_computed", "ATAC fragments/peaks + motif database + background peaks"),
    ("Cicero", "coaccessibility links", "not_computed", "ATAC cell data + reduced dimensions"),
    ("SCARlink", "peak-to-gene links", "not_computed", "paired RNA/ATAC multiome object"),
    ("SCENIC+", "eRegulons/GRN", "not_computed", "paired RNA/ATAC + motif ranking + enhancer-to-gene links"),
    ("chromatin potential", "future RNA tendency from chromatin", "not_computed", "multiome RNA/ATAC counts with method-specific model"),
]

write_tsv(
    "chromatin_module_requirements.tsv",
    [
        {
            "module": m,
            "expected_output": o,
            "status": s,
            "required_inputs": req,
            "constraint": "No chromatin-derived result should be reported until this output exists.",
        }
        for m, o, s, req in chromatin_rows
    ],
    ["module", "expected_output", "status", "required_inputs", "constraint"],
)


def state_space_svg() -> None:
    wells = [
        (150, 230, "stem-like", "#2c7fb8"),
        (340, 160, "differentiating\npositional", "#41ab5d"),
        (545, 235, "differentiated\nstable", "#756bb1"),
        (420, 340, "fate-lock\nhigh", "#dd8b28"),
        (645, 370, "senescence\ndeep", "#b8322c"),
        (205, 390, "tumor-like\nmetastable", "#636363"),
    ]
    body = [
        svg_text(400, 36, "Unified cell-fate state space (schema / hypothesis only)", 20, "#111827"),
        svg_text(400, 60, "No local cell-level coordinates or attractor probabilities were available in this run.", 12, "#475569"),
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" fill="#475569"/></marker></defs>',
    ]
    arrows = [
        (190, 220, 300, 170),
        (390, 170, 505, 220),
        (380, 185, 410, 305),
        (460, 350, 590, 370),
        (180, 260, 205, 355),
        (255, 382, 140, 245),
    ]
    for x1, y1, x2, y2 in arrows:
        body.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"/>')
    for x, y, label, color in wells:
        body.append(f'<ellipse cx="{x}" cy="{y}" rx="88" ry="45" fill="{color}" opacity="0.88" stroke="#1f2937" stroke-width="1.2"/>')
        lines = label.split("\n")
        for idx, line in enumerate(lines):
            body.append(svg_text(x, y + (idx - (len(lines) - 1) / 2) * 15 + 4, line, 13, "#ffffff"))
    write_svg("trajectory_state_space_schema.svg", "\n".join(body), 800, 470)


def grn_svg() -> None:
    nodes = [
        (80, 90, "Wnt", "#2c7fb8"),
        (80, 160, "BMP", "#dd8b28"),
        (80, 230, "RA", "#41ab5d"),
        (80, 300, "FGF/SHH/NOTCH", "#756bb1"),
        (300, 90, "TCF/LEF-MYC", "#2c7fb8"),
        (300, 160, "SMAD-p53-p16/Rb", "#dd8b28"),
        (300, 230, "RAR/RXR-HOX", "#41ab5d"),
        (300, 300, "ETV/GLI/RBPJ", "#756bb1"),
        (555, 120, "RNA state scores", "#334155"),
        (555, 220, "motif deviation", "#334155"),
        (555, 320, "peak-gene links", "#334155"),
        (750, 220, "fate transition", "#b8322c"),
    ]
    body = [
        svg_text(440, 34, "Candidate signaling-TF-chromatin GRN", 20, "#111827"),
        svg_text(440, 56, "Edges are curated priors until RNA/ATAC/SCENIC+ outputs are computed.", 12, "#475569"),
        '<defs><marker id="arrow2" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" fill="#475569"/></marker></defs>',
    ]
    edges_xy = [
        (150, 90, 220, 90),
        (150, 160, 220, 160),
        (150, 230, 220, 230),
        (165, 300, 210, 300),
        (385, 90, 485, 120),
        (405, 160, 485, 120),
        (380, 230, 485, 120),
        (395, 300, 485, 120),
        (405, 90, 485, 220),
        (420, 160, 485, 220),
        (390, 230, 485, 220),
        (410, 300, 485, 220),
        (625, 120, 700, 220),
        (625, 220, 700, 220),
        (625, 320, 700, 220),
    ]
    for x1, y1, x2, y2 in edges_xy:
        body.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#475569" stroke-width="1.8" marker-end="url(#arrow2)"/>')
    for x, y, label, color in nodes:
        body.append(svg_rect(x - 64, y - 22, 128, 44, color, "#1f2937", 6))
        body.append(svg_text(x, y + 5, label, 12, "#ffffff"))
    write_svg("candidate_grn_schema.svg", "\n".join(body), 880, 390)


def status_svg() -> None:
    status_color = {
        "completed_this_run": "#2c7fb8",
        "schema_defined_only": "#41ab5d",
        "reported_completed_not_verified": "#f1c232",
        "reported_partial_not_verified": "#dd8b28",
        "incomplete": "#b8322c",
        "partial_or_missing": "#b8322c",
        "not_computed": "#b8322c",
        "design_only_critical_missing": "#b8322c",
        "not_computed_this_run": "#9ca3af",
    }
    body = [
        svg_text(470, 34, "R1-R14 module completion status", 20, "#111827"),
        svg_text(470, 56, "Blue=verified this run, green=schema only, yellow/orange=reported not verified, red=missing.", 12, "#475569"),
    ]
    start_x, start_y = 40, 90
    cell_w, cell_h = 120, 62
    for idx, (m, n, s, _e, _c) in enumerate(pipeline):
        col, row = idx % 7, idx // 7
        x, y = start_x + col * (cell_w + 10), start_y + row * (cell_h + 22)
        body.append(svg_rect(x, y, cell_w, cell_h, status_color.get(s, "#9ca3af"), "#1f2937", 5))
        body.append(svg_text(x + cell_w / 2, y + 22, m, 15, "#ffffff"))
        body.append(svg_text(x + cell_w / 2, y + 42, s.replace("_", " "), 8, "#ffffff"))
    write_svg("r1_r14_status_matrix.svg", "\n".join(body), 940, 270)


def causal_svg() -> None:
    labels = [
        (95, 160, "perturbation\nor treatment", "#2c7fb8"),
        (255, 160, "pathway\nactivity", "#41ab5d"),
        (415, 160, "TF / motif\nactivity", "#756bb1"),
        (575, 160, "chromatin\naccessibility", "#dd8b28"),
        (735, 160, "fate-state\nprobability", "#b8322c"),
    ]
    body = [
        svg_text(420, 36, "R14 perturbation-to-fate causal graph skeleton", 20, "#111827"),
        svg_text(420, 58, "Design only: no causal effects estimated without perturbation identities and state probabilities.", 12, "#475569"),
        '<defs><marker id="arrow3" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" fill="#475569"/></marker></defs>',
    ]
    for idx in range(len(labels) - 1):
        x1, y1 = labels[idx][0] + 65, labels[idx][1]
        x2, y2 = labels[idx + 1][0] - 65, labels[idx + 1][1]
        body.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#475569" stroke-width="2" marker-end="url(#arrow3)"/>')
    for x, y, label, color in labels:
        body.append(f'<ellipse cx="{x}" cy="{y}" rx="67" ry="42" fill="{color}" opacity="0.9" stroke="#1f2937"/>')
        lines = label.split("\n")
        for idx, line in enumerate(lines):
            body.append(svg_text(x, y + (idx - 0.5) * 15 + 5, line, 12, "#ffffff"))
    write_svg("r14_causal_graph_schema.svg", "\n".join(body), 840, 260)


state_space_svg()
grn_svg()
status_svg()
causal_svg()


report = """# 细胞命运动力系统多数据集分析重建报告

生成日期：2026-06-18  
工作目录检查结论：当前 workspace 只有 `work/` 和 `outputs/`，没有可复用的 `.h5ad`、`.loom`、`.rds`、矩阵、chromVAR、Cicero、SCENIC+、CellRank 或 perturbation effect 文件。

## 核心结论

本轮完成的是 **R1-R14 分析框架重建、数据证据账本、候选状态空间/GRN/R14 因果图设计，以及 figure-ready 模板**。由于本地没有原始矩阵或既有分析对象，不能声称已经计算出新的吸引子位置、状态转移概率、chromVAR motif deviation、SCENIC+ regulon、chromatin potential 或扰动因果效应。

已核对的公开数据元数据：

- GSE153596：小鼠新生/juvenile 皮肤 wound/unwound scRNA-seq，GEO 提供 velocyto loom 文件所在总 tar；适合作为 trajectory / velocity / CellRank 数据源，但本地无对象可复核。
- GSE90546：人源 CRISPRi Perturb-seq，GEO 标题和摘要确认其为 UPR Perturb-seq；适合作为扰动分析候选，但不是 GEO 元数据中直接标注的 Wnt/BMP/RA 命运扰动数据。
- GSE195467：人 iPSC somitogenesis scRNA-seq 时间序列；GEO 元数据未直接确认 RA/BMP modulation 标签，因此不能把它直接当作 RA/BMP 扰动证据，除非后续样本标签或论文补充表确认。

## R1-R14 状态

详见 `r1_r14_module_status.tsv` 与 `r1_r14_status_matrix.svg`。

- R1 已在本轮完成：数据集 accession、GEO 标题、物种、补充文件结构已记录。
- R2-R5 只定义了统一状态空间与 signature schema；没有计算 cell-level scores。
- R6-R8 为用户报告已完成，但当前 workspace 没有可验证输出，因此标记为 reported-not-verified。
- R9 为用户报告部分完成，但当前 workspace 没有 ATAC/multiome 对象。
- R10 chromVAR、R11 Cicero/SCARlink、R12 SCENIC+、R13 chromatin potential 均未计算。
- R14 扰动到命运因果图是 critical missing step；本轮只产出设计骨架和结果表模板。

## Step 1：统一细胞命运状态空间

本轮定义了六个可计算状态：

1. `stem_like`
2. `differentiating_positional`
3. `differentiated_stable`
4. `fate_lock_high`
5. `senescence_deep`
6. `tumor_like_metastable`

对应 marker/signature 存放在 `state_signature_gene_sets.tsv`。这些是 curated signatures，尚未在本地矩阵上打分。`trajectory_state_space_schema.svg` 是状态空间示意图，不是数据驱动的 UMAP/landscape。

## Step 2：信号通路-TF-染色质候选网络

`candidate_regulatory_network_edges.tsv` 给出 Wnt、BMP、RA、FGF、SHH、NOTCH 与 TCF/LEF-MYC、SMAD-p53-p16/Rb、RAR/RXR-HOX、ETV/GLI/RBPJ 等节点之间的候选边。

证据等级：`curated_prior_not_data_derived`。这些边不能替代 chromVAR、Cicero/SCARlink 或 SCENIC+ 结果。

## Step 3：扰动因果推断

`r14_causal_graph_edges_design.tsv` 和 `perturbation_response_map_template.tsv` 定义了 R14 最小因果推断图：

`perturbation_or_treatment -> pathway_activity_score -> TF_activity_or_motif_deviation -> chromatin_accessibility -> GRN_edge_weight -> fate_state_probability -> attractor_shift_label`

当前没有估计任何扰动效应。GSE90546 需要先下载/抽取 CRISPRi target identity 与 count matrix；GSE195467 需要先确认是否存在 RA/BMP 条件标签。

## Step 4：吸引子移动

本轮没有提出任何吸引子移动的实证结论。`attractor_claims_ledger.tsv` 明确记录：

- stemness recovery：not claimed
- fate-lock reinforcement：not claimed
- senescence stabilization：not claimed
- tumor-like plastic transition：not claimed

每个 claim 需要 cell-level state score、transition/terminal probability、扰动 contrast、统计显著性和可追溯输入细胞。

## Step 5：已生成输出

- `dataset_registry.tsv`
- `r1_r14_module_status.tsv`
- `state_signature_gene_sets.tsv`
- `candidate_regulatory_network_edges.tsv`
- `differential_state_transition_matrix_template.tsv`
- `prior_transition_adjacency_hypothesis.tsv`
- `perturbation_response_map_template.tsv`
- `r14_causal_graph_edges_design.tsv`
- `attractor_claims_ledger.tsv`
- `chromatin_module_requirements.tsv`
- `trajectory_state_space_schema.svg`
- `candidate_grn_schema.svg`
- `r1_r14_status_matrix.svg`
- `r14_causal_graph_schema.svg`

## 需要继续计算的最小闭环

1. 下载或接入原始/处理后对象：GSE153596 loom/h5ad、GSE90546 10x + cell identities、GSE195467 10x + sample metadata、多组学 ATAC/RNA 对象。
2. 计算每个细胞的 state signature score，并统一到同一状态空间。
3. 用 trajectory/velocity/CellRank 输出生成真实 transition matrix。
4. 对 ATAC/multiome 运行 chromVAR、Cicero/SCARlink、SCENIC+、chromatin potential。
5. 对 GSE90546 和已确认条件标签的数据运行扰动响应模型，输出 `Δstate_score`、`Δterminal_probability`、FDR 和 bootstrap sign stability。
6. 只有当 `attractor_claims_ledger.tsv` 所列证据全部满足时，才标记具体 attractor shift 为 completed。
"""

(OUT / "cell_fate_reconstruction_report.md").write_text(report, encoding="utf-8")


protocol = """# 继续计算协议

本文件是后续真正运行 R2-R14 的执行清单，不包含已计算结果。

## 输入对象

- GSE153596：需要 loom 或已整合 h5ad，包含 spliced/unspliced/layer 信息。
- GSE90546：需要 10x matrix、barcodes、genes 和 cell_identities/perturbation target。
- GSE195467：需要 10x matrix 和样本级 time/treatment metadata。RA/BMP modulation 必须先从样本标签或论文补充表确认。
- Multiome：需要 RNA counts、ATAC peaks/fragments、cell metadata、peak annotation。

## R14 统计模型

对每个扰动 target 或 treatment contrast：

1. 计算每个细胞的 signature score：stemness、fate_lock、senescence、positional、tumor_like_plasticity、differentiated_stable。
2. 拟合批次/测序深度/细胞周期/时间点校正模型：
   `state_score ~ perturbation + batch + nUMI + percent_mito + cell_cycle + time`
3. 若有 CellRank/velocity：
   `terminal_probability[state] ~ perturbation + covariates`
4. 生成差异状态转移矩阵：
   `P_perturbed(from,to) - P_control(from,to)`
5. 接受因果边的最低条件：
   effect size 非零、FDR 通过、bootstrap sign stability 通过、方向与时间/velocity 顺序一致、输入细胞可追溯。

## 禁止事项

- 没有 chromVAR 输出时，不报告 motif activity 结论。
- 没有 Cicero/SCARlink/SCENIC+ 输出时，不报告数据驱动 GRN 结论。
- 没有 transition/terminal probability 时，不报告 attractor shift 结论。
"""

(OUT / "recompute_protocol.md").write_text(protocol, encoding="utf-8")

print(f"Wrote reconstruction outputs to {OUT}")
