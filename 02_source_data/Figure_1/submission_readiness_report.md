# Submission Readiness Report

Generated: 2026-06-20

## Summary verdict

The manuscript logic is reconstructable and internally stable under the locked latent-state-regime mixture framework. The scientific narrative is ready for submission stabilization, but the overall package remains administratively not ready until reference metadata are resolved and a final journal-specific formatting check is completed.

## Readiness matrix

| Item | Status | Evidence |
|---|---|---|
| Project state recovered | yes | Current model, figure logic, and claim boundaries reconstructed |
| Main representation stable | yes | `P(Z|S,W_GRN)` used as accepted working representation |
| Phi scalar model safely rejected | yes | AUC approximately 0.48; permutation/bootstrap instability; KS non-discriminative |
| Figure architecture stable | yes | 9 main figures plus Supplementary Figure 1; no Figure 10 |
| Figure 1A model lineage present | yes | `MODEL_EVOLUTION_MAP_Figure1A.*` present in outputs and final package |
| Main manuscript present | yes | `outputs/FINAL_MANUSCRIPT_WITH_MODEL_EVOLUTION_MAP.docx` |
| Claim-safe main text present | yes | `outputs/final_claim_safe_main_text_with_model_lineage.md` |
| Figure legends present | yes | `outputs/FINAL_FIGURE_LEGENDS_WITH_MODEL_EVOLUTION.docx` |
| Supplementary causal package present | yes | Supplementary Figure 1 and source TSV files present |
| Causal interpretation safe | yes | Partial regime-conditioned dry-lab consistency only |
| Reference package ready | no | RIS/BibTeX metadata unresolved; no fabricated DOI/PMID metadata |
| Portal-specific formatting checked | no | Requires final journal-rule pass |

## Submission package status

Current final package path:

`FINAL_SUBMISSION_PACKAGE/`

Present key files:

- `FINAL_SUBMISSION_PACKAGE/FINAL_MANUSCRIPT_WITH_MODEL_EVOLUTION_MAP.docx`
- `FINAL_SUBMISSION_PACKAGE/FINAL_FIGURE_LEGENDS_WITH_MODEL_EVOLUTION.docx`
- `FINAL_SUBMISSION_PACKAGE/SUPPLEMENTARY_MATERIAL.docx`
- `FINAL_SUBMISSION_PACKAGE/SUPPLEMENTARY_SOURCE_DATA_INDEX.tsv`
- `FINAL_SUBMISSION_PACKAGE/main_figures/`
- `FINAL_SUBMISSION_PACKAGE/supplementary_source_data/`
- `FINAL_SUBMISSION_PACKAGE/references/unresolved_reference_list.md`
- `FINAL_SUBMISSION_PACKAGE/references/endnote_import_todo.md`

## Main figure readiness

| Requirement | Status |
|---|---|
| 9 main figures present | yes |
| Figure 1A model lineage present | yes |
| Figure 10 avoided | yes |
| Latent-state-regime terminology consistent | yes |
| Phi shown only as failure/deprecated proxy | yes |
| Overlap/divergence logic preserved | yes |

## Supplementary readiness

| Requirement | Status |
|---|---|
| Supplementary Figure 1 present | yes |
| Dry-lab perturbation source tables present | yes |
| Partial closure status preserved | yes |
| Wet-lab validation claim avoided | yes |
| Supplementary source-data index present | yes |

## Missing or unresolved items

1. Reference metadata are unresolved.
   - Current package contains `unresolved_reference_list.md` and `endnote_import_todo.md`.
   - DOI, PMID, RIS, and BibTeX metadata should not be fabricated.

2. Journal-specific submission formatting remains to be checked.
   - Figure resolution and file naming may need portal-specific adjustment.
   - Source-data naming may need to match Nature Communications or Cell Systems upload rules.

3. Legacy Phi artifacts remain in `outputs/`.
   - They do not block submission if excluded from positive model claims.
   - They should be treated as historical/failure-context artifacts only.

## Final verdict

MAIN_TEXT_READY: yes

MAIN_FIGURES_READY: yes

MODEL_LINEAGE_READY: yes

SUPPLEMENTARY_PACKAGE_READY: yes

REFERENCE_PACKAGE_READY: no

CAUSAL_CLAIM_SAFE: yes

READY_FOR_SUBMISSION: no

## Required next action

Before journal submission, resolve references from a real bibliography source and perform a final portal-specific format pass. No additional modeling or data analysis is required for manuscript continuity.
