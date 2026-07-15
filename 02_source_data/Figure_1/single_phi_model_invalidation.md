# Formal Invalidation of Single-Phi Model

## Model Invalidation

**Phi(S, W_GRN) is NOT a valid discriminative or order parameter.**

All classifier and global-threshold interpretations of `Phi` are removed.

## Evidence

- ROC AUC = 0.480, which is random classification performance.
- Permutation p-value for mean separation = 0.585, not significant.
- Bootstrap CI for mean shift crosses zero: [-0.042, 0.025].
- KS test is significant (p = 1.50e-20) but only indicates distribution-shape difference; it does not provide discriminative ordering.
- Batch/species entanglement prevents a single scalar from serving as a universal biological coordinate.

## Removed Interpretation

`Phi >= 0` must not be interpreted as embryonic reactivation, and `Phi < 0` must not be interpreted as adult repair. `ROC/AUC` is no longer an optimization objective for the dynamical system.

## Replacement

The model is replaced by a latent state regime mixture:

```text
Z in {adult_repair, embryonic_reactivation, salamander_blastema, salamander_intact}

P(Phi | S) = sum_Z P(Phi | S, Z) P(Z | S, W_GRN)
```

Each latent state regime has its own `Phi` distribution. No global `Phi` threshold exists.

## Mandatory Final Statement

Single scalar order parameter Phi is insufficient;
cell fate system is governed by a latent state regime mixture model rather than a separable embedding.
