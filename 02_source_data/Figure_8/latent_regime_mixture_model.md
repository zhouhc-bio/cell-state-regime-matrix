# Latent Regime Mixture Dynamical System

## State and Latent Regime

```text
S = [Stemness, Transitional, Fate_lock, Embryonic_module_score]
Z in {adult_repair, embryonic_reactivation, salamander_blastema, salamander_intact}
```

`Z` is not observed directly. It is inferred as `P(Z|S)` by a mixture model.

## Replacement of Single Phi

```text
P(Phi | S) = sum_Z P(Phi | S,Z) P(Z | S,W_GRN)
```

The dynamical system should be written as:

```text
dS/dt = sum_Z P(Z|S,W_GRN) F_Z(S,U,W_GRN) + xi(S)
```

No global threshold on `Phi` is used.

## Fitting Objective

The model objective is no longer AUC. The intended objectives are:

1. maximize likelihood `P(S|Z)`;
2. minimize `KL(P_empirical(Phi) || P_mixture(Phi))`;
3. maximize mutual information `I(S;Z)` subject to reproducible, non-degenerate components.
