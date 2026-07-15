# Project State Summary

Generated: 2026-06-20

## Locked project identity

This project is a computational cell-fate modeling manuscript that reconstructs regeneration and repair as a representation problem across mammalian and salamander systems.

The final accepted structure is a latent-state-regime mixture framework:

`P(Z | S, W_GRN)`

where `Z` is restricted to four latent regenerative regimes:

- `adult_repair`
- `embryonic_reactivation`
- `salamander_blastema`
- `salamander_intact`

The scalar `Phi` / PGCS model is rejected and retained only as a failed diagnostic projection. It must not be used as a positive model, threshold, classifier, or biological order parameter.

## Locked conclusions

| Topic | Current state | Manuscript interpretation |
|---|---|---|
| Scalar Phi / PGCS model | Rejected | A failed scalar embedding assumption, not a recoverable model |
| Phi validation evidence | AUC approximately 0.48; permutation instability; bootstrap interval includes zero; KS significant but non-discriminative | Supports scalar failure and motivates replacement |
| Accepted representation | Latent-state-regime mixture | Observed states carry posterior mass over regimes |
| Salamander blastema | Distinct latent regenerative regime | Not a higher position on the mammalian repair coordinate |
| Mammalian repair | Adult-repair-dominant mixture | Constrained by fate-lock, inflammatory context, and senescence-like retention |
| Tumor-like plasticity | Separate high-plasticity branch | Not equivalent to regeneration |
| Global causal closure | Not established | Main manuscript must not claim complete causal validation |
| Dry-lab perturbation layer | Partial regime-conditioned consistency | Supplementary support only; no wet-lab validation claim |

## Narrative reconstruction

The manuscript now follows a failure-driven replacement logic:

1. Old model: PGCS / Phi assumed that cell fate could be compressed into a single scalar.
2. Failure layer: Phi showed random-level discrimination, unstable permutation/bootstrap behavior, and KS shape differences without separability.
3. Transition: scalar embedding breaks across species and regimes.
4. Replacement: latent-state-regime mixture `P(Z | S, W_GRN)`.
5. Final claim: replacement, not refinement.

This logic is explicitly represented by the model evolution map, currently available as:

- `outputs/MODEL_EVOLUTION_MAP_Figure1A.png`
- `outputs/MODEL_EVOLUTION_MAP_Figure1A.pdf`
- `outputs/MODEL_EVOLUTION_MAP_Figure1A.svg`
- `FINAL_SUBMISSION_PACKAGE/main_figures/MODEL_EVOLUTION_MAP_Figure1A.png`

## Current manuscript files

| File | Role | Status |
|---|---|---|
| `outputs/FINAL_MANUSCRIPT_WITH_MODEL_EVOLUTION_MAP.docx` | Current manuscript with model lineage figure inserted | Current working manuscript |
| `outputs/final_claim_safe_main_text_with_model_lineage.md` | Clean text version with model lineage and claim-safe wording | Current text source |
| `outputs/FINAL_FIGURE_LEGENDS_WITH_MODEL_EVOLUTION.docx` | Figure legends including Figure 1A | Current legend source |
| `FINAL_SUBMISSION_PACKAGE/FINAL_MANUSCRIPT_WITH_MODEL_EVOLUTION_MAP.docx` | Packaged manuscript copy | Submission package copy |
| `FINAL_SUBMISSION_PACKAGE/final_claim_safe_main_text_with_model_lineage.md` | Packaged clean text copy | Submission package copy |

## Figure system

The locked figure architecture is 9 main figures plus Supplementary Figure 1. Figure 1A is the model-evolution panel that anchors the replacement narrative. It is embedded before the nine main-result figures and does not create a Figure 10.

Main figure roles:

- Figure 1: Phi failure plus regime replacement logic.
- Figure 2: latent state mixture / shared accessibility; accessibility is not fate determination.
- Figure 3: stemness is local accessibility, not a global fate driver.
- Figure 4: positional information as regime-conditioned coordinate.
- Figure 5: adult repair / fate-lock basin constraint.
- Figure 6: tumor-like plasticity as distinct branch.
- Figure 7: scalar Phi rejection statistics.
- Figure 8: latent state regime posterior landscape and locked dynamical statement.
- Figure 9: overlap and symmetrized divergence across species/regimes.

Supplementary Figure 1:

- Dry-lab perturbation consistency audit.
- Supports `PARTIAL_CLOSURE` only.
- Does not establish wet-lab validation or global causal closure.

## Module inventory

| Module | Status | Current role |
|---|---|---|
| Scalar Phi / PGCS | Invalidated | Failure evidence and lineage context only |
| Latent-state-regime mixture | Accepted working representation | Central model |
| Posterior regime assignment | Active | `P(Z | S, W_GRN)` |
| Regime-conditioned dynamics | Active | `dS/dt = sum_Z P(Z|S,W_GRN) F_Z(S,U,W_GRN) + xi(S)` |
| Stemness/accessibility layer | Retained | Local accessibility component |
| Positional-program layer | Retained | Regime-conditioned developmental coordinate |
| Fate-lock layer | Retained | Adult-repair basin constraint |
| Tumor-like plasticity | Retained | Boundary branch distinct from regeneration |
| Dry-lab perturbation consistency | Supplementary | Partial local consistency only |
| Reference package | Incomplete | Metadata unresolved; no DOI/PMID fabrication |

## Important continuity rule

The final project state is not a re-analysis task. The correct next action is manuscript stabilization around the locked latent-state-regime mixture framework, while isolating all obsolete scalar-positive artifacts as historical outputs.
