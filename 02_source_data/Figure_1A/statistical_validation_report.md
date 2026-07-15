# Statistical Validation Report

## Primary Hypothesis

H1: unified `Phi(S,W_GRN)` separates mammalian inflammatory repair from salamander blastema reactivation.

Primary comparison:

- Mammal: `mammalian_inflammatory_repair`, n = 15000
- Salamander: `salamander_blastema_reactivation`, n = 4335
- Salamander intact cells are retained in `Phi_unified.tsv` as reference but excluded from the primary H1 test.

## Results

| test | statistic |
|---|---:|
| KS statistic | 0.0828279 |
| KS p-value | 1.50109e-20 |
| Wasserstein distance | 0.146456 |
| Mean Phi difference, salamander - mammal | -0.0093519 |
| Permutation p-value, two-sided | 0.585041 |
| ROC AUC | 0.479793 |

## Acceptance Criteria

- p < 0.05: FAIL
- AUC > 0.75: FAIL

## System Status

`INVALID_STATISTICAL_CRITERIA_NOT_MET`

## Evidence Boundary

This is a module-score/state-score-level closure. It is suitable as a reproducible figure-data/statistical binding layer for the current model outputs, but final raw-data submission should additionally archive the upstream scripts that produced the input module scores.
