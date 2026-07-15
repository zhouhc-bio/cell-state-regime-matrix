# Inconsistency Report

Generated: 2026-06-20

## Scope

This report checks manuscript continuity against the locked project state:

- Phi / PGCS scalar model rejected.
- Latent-state-regime mixture `P(Z|S,W_GRN)` accepted as the working representation.
- Four regimes only: `adult_repair`, `embryonic_reactivation`, `salamander_blastema`, `salamander_intact`.
- Dry-lab perturbation layer supports partial regime-conditioned consistency only.
- No new model, new data, or new figure count is introduced.

## Current final-text check

Primary checked text source:

- `outputs/final_claim_safe_main_text_with_model_lineage.md`

Supporting package copy:

- `FINAL_SUBMISSION_PACKAGE/final_claim_safe_main_text_with_model_lineage.md`

### Result

| Check | Status | Notes |
|---|---|---|
| Phi used as positive model | PASS | Current final text treats Phi as rejected/deprecated |
| Phi used as classifier/order parameter | PASS | Figure 7 and model-lineage section define failure only |
| Regime mixture used consistently | PASS | `P(Z|S,W_GRN)` is the accepted representation |
| Fixed regime names maintained | PASS | Uses `adult_repair`, `embryonic_reactivation`, `salamander_blastema`, `salamander_intact` |
| Salamander blastema treated as distinct regime | PASS | Not framed as scalar increase |
| Mammalian repair treated as adult-repair mixture | PASS | Not framed as lower-intensity salamander regeneration |
| Tumor-like plasticity separated from regeneration | PASS | Figure 6 retains boundary-branch logic |
| Main figure count preserved | PASS | Nine main figures retained; Figure 1A is lineage panel, no Figure 10 |
| Supplementary causal layer limited | PASS | Supplementary Figure 1 remains partial dry-lab consistency |

## Known legacy artifacts requiring isolation

Several files in `outputs/` preserve earlier Phi-oriented work products. These are not errors by themselves, but they must not be used as final model evidence except when documenting failure of the scalar assumption.

| Legacy artifact class | Examples | Required handling |
|---|---|---|
| Phi phase/threshold artifacts | `Phi_phase_diagram.*`, `Phi_bifurcation_analysis.*`, `figure5_regime_threshold_crossing_statistics.tsv` | Historical or failure-context only |
| Scalar validation plots | `roc_curve.png`, `Phi_distribution_by_species.png`, `bootstrap_confidence_intervals.png` | Use only to support rejection of scalar model |
| Earlier text drafts | `main_text_clean_version.md`, `results_final_rewritten.md`, `discussion_final_rewritten.md` | Prefer claim-safe lineage versions where available |
| Old figure inventories | `old_figure_inventory.tsv`, `old_paper_to_new_model_mapping.tsv` | Use only as migration/audit evidence |

## Text-level concerns found in older drafts

Older draft files still contain an over-strong sufficiency phrase. This was already corrected in the current claim-safe text to:

`minimal working representation supported by the locked outputs and evaluated baselines`

Risk: future assembly must use `outputs/final_claim_safe_main_text_with_model_lineage.md`, not older pre-edit Markdown files.

## Causal-claim safety

Current final-text status is safe:

- No wet-lab validation claim is present in the current final text.
- The perturbation analysis is described as supplementary dry-lab consistency.
- The final interpretation is partial and regime-conditioned.
- Counterfactual reversal and cross-regime instability are retained as limitations.

Risk: table names and older file names include "closure" terminology. That is acceptable as source-data naming, but prose should use "partial regime-conditioned perturbation consistency" or "computational causal-consistency support".

## Figure consistency

| Figure | Consistency status | Required guardrail |
|---|---|---|
| Figure 1A | PASS | Must remain a replacement map |
| Figure 1 | PASS | Must not resemble a scalar-axis model |
| Figure 2 | PASS | Accessibility is not fate determination |
| Figure 3 | PASS | Stemness is local accessibility only |
| Figure 4 | PASS | Positional programs are regime-conditioned |
| Figure 5 | PASS | Fate-lock is basin constraint, not linear axis |
| Figure 6 | PASS | Tumor-like plasticity remains separate |
| Figure 7 | PASS | Phi failure only |
| Figure 8 | PASS | Uses latent posterior dynamics |
| Figure 9 | PASS | Overlap and divergence are both required |
| Supplementary Figure 1 | PASS_WITH_LIMITS | Partial dry-lab consistency only |

## Missing logical links

No major logical break is present in the current final text. The key link that must be preserved is:

`Phi failure statistics -> scalar embedding breakdown -> latent state regime mixture replacement -> overlap/divergence interpretation -> supplementary partial perturbation consistency`

If any section is rewritten later, this chain must remain intact.

## Inconsistency verdict

CURRENT_FINAL_TEXT_CONSISTENT: yes

CURRENT_FIGURE_SYSTEM_CONSISTENT: yes

LEGACY_PHI_ARTIFACTS_PRESENT: yes

LEGACY_ARTIFACTS_BLOCK_SUBMISSION: no, if excluded from final positive claims

CAUSAL_LANGUAGE_SAFE: yes

ACTION_REQUIRED_BEFORE_SUBMISSION: resolve references and ensure final assembly uses the claim-safe lineage manuscript files.
