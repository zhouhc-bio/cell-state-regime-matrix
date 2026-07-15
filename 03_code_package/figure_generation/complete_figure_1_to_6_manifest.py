from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path("/Users/hanchengdezhuanqiangongju/Documents/Codex/2026-06-18/task-reconstruct-and-continue-analysis-of")
INPUT = Path("/Users/hanchengdezhuanqiangongju/Downloads/figure_1_to_6_panel_source_manifest.tsv")
OUTPUT = ROOT / "figure_1_to_6_panel_source_manifest_COMPLETED.tsv"
T9 = Path("/Volumes/T9/PGCS/figure_reconstruction_v3/source_data")


def r(path: Path) -> str:
    return str(path)


def out(name: str) -> str:
    return str(ROOT / "outputs" / name)


def t9(name: str) -> str:
    return str(T9 / name)


def joined(*paths: str) -> str:
    return "; ".join(paths)


def file_type(paths: str, candidates: str = "") -> str:
    values = paths if paths and paths not in {"SOURCE_MISSING", "SOURCE_AMBIGUOUS"} else candidates
    if not values:
        return ""
    exts = []
    for item in [x.strip() for x in values.split(";") if x.strip()]:
        suffix = Path(item).suffix.lower().lstrip(".")
        if suffix and suffix not in exts:
            exts.append(suffix.upper())
    return ";".join(exts)


def exists_all(paths: str) -> bool:
    if not paths or paths in {"SOURCE_MISSING", "SOURCE_AMBIGUOUS"}:
        return False
    return all(Path(x.strip()).exists() for x in paths.split(";") if x.strip())


def source(
    status: str,
    paths: str,
    analysis_step: str,
    reproducibility: str,
    notes: str,
    candidates: str = "",
) -> dict[str, str]:
    return {
        "source_status": status,
        "likely_source_data_or_analysis_output": paths if paths else status,
        "exact_source_file_path": paths,
        "source_file_type": file_type(paths, candidates),
        "analysis_step": analysis_step,
        "reproducibility_status": reproducibility,
        "notes": notes,
        "candidate_files": candidates,
    }


S: dict[tuple[str, str], dict[str, str]] = {}

# Figure 1: current figure is a rebuilt conceptual/model-replacement figure.
S[("Figure 1", "A")] = source(
    "SOURCE_CONFIRMED",
    joined(
        out("roc_curve.tsv"),
        out("ks_test_results.tsv"),
        out("permutation_test_results.tsv"),
        out("bootstrap_confidence_intervals.tsv"),
        out("single_phi_model_invalidation.md"),
    ),
    "Scalar Phi invalidation summary using ROC, KS, permutation and bootstrap outputs.",
    "REPRODUCIBLE_WITH_MANUAL_REDRAW",
    "Exact statistics/source summaries exist in current workspace; panel itself is a schematic/summary redraw.",
)
S[("Figure 1", "B")] = source(
    "SOURCE_CONFIRMED",
    joined(out("model_architecture_reconstruction.md"), out("latent_regime_mixture_model.md"), out("project_state_summary.md")),
    "Latent-state-regime replacement logic and posterior-regime framing.",
    "REPRODUCIBLE_WITH_MANUAL_REDRAW",
    "Conceptual panel with exact model-definition source files.",
)
S[("Figure 1", "C")] = source(
    "SOURCE_NOT_REQUIRED_SCHEMATIC",
    joined(out("project_state_summary.md"), out("model_architecture_reconstruction.md")),
    "Regime-name definition and accepted model scope.",
    "SCHEMATIC_NO_NUMERIC_SOURCE_REQUIRED",
    "No numeric panel source required; exact model-state documents define the four regimes.",
)
S[("Figure 1", "D")] = source(
    "SOURCE_CONFIRMED",
    joined(out("inconsistency_report.md"), out("submission_readiness_report.md"), out("model_lineage_section.md"), out("model_evolution_map_caption.md")),
    "Model-evolution and replacement-not-refinement decision boundary.",
    "REPRODUCIBLE_WITH_MANUAL_REDRAW",
    "Decision-boundary schematic derives from exact continuity and lineage reports.",
)

# Figure 2: old Figure 2 panel sources retained under accessibility-not-fate interpretation.
for panel in "ABCDEFG":
    p = t9(f"Figure_2_panel_{panel.lower()}_source_data.tsv")
    status = "SOURCE_PARTIAL" if panel == "G" else "SOURCE_CONFIRMED"
    notes = "Exact T9 source-data path found for old/current Figure 2 panel."
    if panel == "G":
        notes = "Exact numeric source for current panel g found; uploaded row title also mentions interpretation text, which is supported by figure legend rather than a separate numeric TSV."
    S[("Figure 2", panel)] = source(
        status,
        p,
        "Shared high-plasticity/accessibility state-space source-data panel.",
        "REPRODUCIBLE_FROM_SOURCE",
        notes,
    )

# Figure 3: old Figure 3 panel sources retained.
for panel in "ABCDEF":
    S[("Figure 3", panel)] = source(
        "SOURCE_CONFIRMED",
        t9(f"Figure_3_panel_{panel.lower()}_source_data.tsv"),
        "Wnt/stemness module and boundary-analysis source-data panel.",
        "REPRODUCIBLE_FROM_SOURCE" if panel != "F" else "REPRODUCIBLE_WITH_MANUAL_REDRAW",
        "Exact T9 source-data path found for current Figure 3 panel.",
    )

# Figure 4: rebuilt/merged positional-information figure from old Figure 4 and axolotl/blastema sources.
S[("Figure 4", "A")] = source(
    "SOURCE_CONFIRMED",
    t9("Figure_4_panel_a_source_data.tsv"),
    "RA/RARG and RA/HOX positional-program evidence.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact RA/RARG positional-score source found on T9.",
)
S[("Figure 4", "B")] = source(
    "SOURCE_CONFIRMED",
    t9("Figure_4_panel_b_source_data.tsv"),
    "RA/RARG effect-size summary.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact RA/RARG effect-size source found on T9.",
)
S[("Figure 4", "C")] = source(
    "SOURCE_CONFIRMED",
    t9("Figure_4_panel_c_source_data.tsv"),
    "Module means for RA/HOX/FGF/SHH/NOTCH-like positional programs.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact module-mean source found on T9.",
)
S[("Figure 4", "D")] = source(
    "SOURCE_CONFIRMED",
    joined(t9("Figure_4_panel_d_source_data.tsv"), t9("Figure_6_panel_d_source_data.tsv")),
    "Axolotl regeneration-stage embedding/context panels merged into current positional-information figure.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Current panel combines old Figure 4 and axolotl source panels; both exact paths are listed.",
)
S[("Figure 4", "E")] = source(
    "SOURCE_CONFIRMED",
    joined(t9("Figure_4_panel_f_source_data.tsv"), t9("Figure_6_panel_e_source_data.tsv"), t9("Figure_6_panel_f_source_data.tsv")),
    "Blastema progenitor and blastema-associated regenerative/positional score panels.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Current row is composite; exact source paths for blastema progenitor and regenerative scores are listed.",
)
S[("Figure 4", "F")] = source(
    "SOURCE_CONFIRMED",
    t9("Figure_6_panel_g_source_data.tsv"),
    "RA/HOX positional identity in salamander/axolotl context.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact axolotl RA/HOX positional-identity source found on T9.",
)
S[("Figure 4", "G")] = source(
    "SOURCE_CONFIRMED",
    joined(t9("Figure_4_panel_g_source_data.tsv"), t9("Figure_6_panel_h_source_data.tsv"), t9("Figure_6_panel_j_source_data.tsv")),
    "Stage-wise module dynamics and pseudotime trend source panels.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Composite row; exact stage and pseudotime source paths are listed.",
)
S[("Figure 4", "H")] = source(
    "SOURCE_CONFIRMED",
    joined(t9("Figure_6_panel_i_source_data.tsv"), t9("Figure_6_panel_k_source_data.tsv")),
    "Basin-like proxy distributions and branch-comparison boundary schematic.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Composite row; exact proxy and branch-comparison sources are listed.",
)

# Figure 5: current fate-lock/adult-repair figure merges fate-stabilization and SAT source panels.
S[("Figure 5", "A")] = source(
    "SOURCE_NOT_REQUIRED_SCHEMATIC",
    joined(
        t9("Figure_5_true_result4_fate_stabilization_lineage_restriction_panel_a_source_data.tsv"),
        t9("Figure_5_true_result4_fate_stabilization_lineage_restriction_panel_h_source_data.tsv"),
    ),
    "Basin-constraint schematic components.",
    "SCHEMATIC_NO_NUMERIC_SOURCE_REQUIRED",
    "Schematic has exact component TSVs, but no numeric source is required.",
)
S[("Figure 5", "B")] = source(
    "SOURCE_CONFIRMED",
    t9("Figure_5_true_result4_fate_stabilization_lineage_restriction_panel_b_source_data.tsv"),
    "Fate-stabilization score projection.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact fate-stabilization source found on T9.",
)
S[("Figure 5", "C")] = source(
    "SOURCE_CONFIRMED",
    t9("Figure_5_true_result4_fate_stabilization_lineage_restriction_panel_c_source_data.tsv"),
    "p53/BMP-associated stabilization score projection.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact p53/BMP stabilization source found on T9.",
)
S[("Figure 5", "D")] = source(
    "SOURCE_CONFIRMED",
    t9("Figure_5_true_result4_fate_stabilization_lineage_restriction_panel_d_source_data.tsv"),
    "Senescence-like absorption/retention source panel.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact CellRank senescence-absorption source found on T9.",
)
S[("Figure 5", "E")] = source(
    "SOURCE_CONFIRMED",
    joined(
        t9("Figure_5_true_result4_fate_stabilization_lineage_restriction_panel_e_source_data.tsv"),
        t9("Figure_5_true_result4_fate_stabilization_lineage_restriction_panel_f_source_data.tsv"),
    ),
    "Velocity/transition and self-retention summaries.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact transition-matrix and velocity self-transition sources are listed.",
)
S[("Figure 5", "F")] = source(
    "SOURCE_CONFIRMED",
    joined(
        t9("Figure_6_SAT_mammalian_repair_failure_panel_a_source_data.tsv"),
        t9("Figure_6_SAT_mammalian_repair_failure_panel_b_source_data.tsv"),
        t9("Figure_6_SAT_mammalian_repair_failure_panel_c_source_data.tsv"),
        t9("Figure_6_SAT_mammalian_repair_failure_panel_d_source_data.tsv"),
        t9("Figure_6_SAT_mammalian_repair_failure_panel_e_source_data.tsv"),
        t9("Figure_6_SAT_mammalian_repair_failure_panel_f_source_data.tsv"),
    ),
    "Senescence Amplification Trap / aging-SAT bounded source panels.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact SAT/adult-repair source paths found on T9; interpret as bounded adult-repair/fate-lock evidence only.",
)
S[("Figure 5", "G")] = source(
    "SOURCE_CONFIRMED",
    t9("Figure_5_true_result4_fate_stabilization_lineage_restriction_panel_g_source_data.tsv"),
    "Perturbation-linked validation/source summary.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact perturbation-linked summary source found on T9.",
)
S[("Figure 5", "H")] = source(
    "SOURCE_CONFIRMED",
    joined(
        t9("Figure_5_true_result4_fate_stabilization_lineage_restriction_panel_h_source_data.tsv"),
        out("unsupported_claims_audit.md"),
        str(ROOT / "figure_audit_final.md"),
    ),
    "Allowed/not-allowed claim boundary for fate-lock/adult-repair interpretation.",
    "REPRODUCIBLE_WITH_MANUAL_REDRAW",
    "Claim-boundary panel combines schematic source with current claim-safety audits.",
)

# Figure 6: current tumor-like branch maps to old Figure 8 / T9 Figure_7 source panels.
S[("Figure 6", "A")] = source(
    "SOURCE_CONFIRMED",
    t9("Figure_7_panel_a_source_data.tsv"),
    "Tumor-like plasticity proxy projection.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact source found; current final Figure 6 maps to old/T9 Figure 7 tumor-like source data.",
)
S[("Figure 6", "B")] = source(
    "SOURCE_CONFIRMED",
    t9("Figure_7_panel_b_source_data.tsv"),
    "Stemness score in tumor-like branch.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact source found; current final Figure 6 maps to old/T9 Figure 7 tumor-like source data.",
)
S[("Figure 6", "C")] = source(
    "SOURCE_CONFIRMED",
    t9("Figure_7_panel_c_source_data.tsv"),
    "Differentiation score in tumor-like branch.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact source found; current final Figure 6 maps to old/T9 Figure 7 tumor-like source data.",
)
S[("Figure 6", "D")] = source(
    "SOURCE_CONFIRMED",
    t9("Figure_7_panel_d_source_data.tsv"),
    "Local retention/high-plasticity boundary.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact local self-retention source found.",
)
S[("Figure 6", "E")] = source(
    "SOURCE_CONFIRMED",
    t9("Figure_7_panel_e_source_data.tsv"),
    "Stemness score by tumor-like quartile.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact quartile source found.",
)
S[("Figure 6", "F")] = source(
    "SOURCE_CONFIRMED",
    t9("Figure_7_panel_f_source_data.tsv"),
    "Differentiation score by tumor-like quartile.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact quartile source found.",
)
S[("Figure 6", "G")] = source(
    "SOURCE_AMBIGUOUS",
    "",
    "Boundary score comparison.",
    "NOT_REPRODUCIBLE_CURRENTLY",
    "Multiple plausible boundary-score source files exist, including a corrected file and older/v4/v5 variants. Exact final-generation choice is not recoverable from the current manifest, so this is not guessed.",
    joined(
        t9("Figure_7_panel_g_corrected_source_data.tsv"),
        t9("Figure_7_panel_g_source_data.tsv"),
        t9("Figure_7_panel_g_source_data_v4.tsv"),
        t9("Figure_7_panel_g_source_data_v5.tsv"),
    ),
)
S[("Figure 6", "H")] = source(
    "SOURCE_CONFIRMED",
    t9("Figure_7_panel_h_source_data.tsv"),
    "Module mean heatmap / cross-system tumor-like branch summary.",
    "REPRODUCIBLE_FROM_SOURCE",
    "Exact source found; current final Figure 6 maps to old/T9 Figure 7 tumor-like source data.",
)


def main() -> None:
    with INPUT.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        original_fields = reader.fieldnames or []
        rows = list(reader)

    added_fields = [
        "exact_source_file_path",
        "source_file_type",
        "analysis_step",
        "reproducibility_status",
        "notes",
        "candidate_files",
        "path_existence_check",
    ]
    fields = original_fields + [x for x in added_fields if x not in original_fields]

    for row in rows:
        key = (row["figure_id"], row["panel_id"])
        resolved = S.get(key)
        if not resolved:
            resolved = source(
                "SOURCE_MISSING",
                "",
                "No matching resolver entry.",
                "NOT_REPRODUCIBLE_CURRENTLY",
                "No resolver rule was defined for this row.",
            )
        row["source_status"] = resolved["source_status"]
        row["likely_source_data_or_analysis_output"] = resolved["likely_source_data_or_analysis_output"]
        for k, v in resolved.items():
            if k != "source_status" and k != "likely_source_data_or_analysis_output":
                row[k] = v

        paths_to_check = row.get("exact_source_file_path") or row.get("candidate_files", "")
        if row["source_status"] == "SOURCE_AMBIGUOUS":
            row["path_existence_check"] = "candidate_paths_exist" if exists_all(row.get("candidate_files", "")) else "candidate_path_missing"
        elif row["source_status"] == "SOURCE_MISSING":
            row["path_existence_check"] = "missing"
        else:
            row["path_existence_check"] = "all_paths_exist" if exists_all(paths_to_check) else "one_or_more_paths_missing"

    with OUTPUT.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
