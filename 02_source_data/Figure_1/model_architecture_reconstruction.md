# Model Architecture Reconstruction

Generated: 2026-06-20

## Recovered architecture

The final manuscript uses a latent-state-regime mixture architecture rather than a scalar developmental coordinate. The accepted object is:

`P(Z | S, W_GRN)`

with fixed latent state regimes:

- `adult_repair`
- `embryonic_reactivation`
- `salamander_blastema`
- `salamander_intact`

The manuscript should be read as a model-replacement paper: the scalar PGCS / Phi representation failed and was replaced by a posterior regime mixture.

## Rejected scalar layer

The earlier scalar model assumed that a single order parameter could organize repair, regeneration, fate-lock, plasticity, and cross-species differences. The locked validation rejects that assumption:

- ROC AUC was approximately 0.48.
- Permutation testing did not support stable scalar separation.
- Bootstrap uncertainty crossed zero.
- KS testing indicated shape mismatch rather than a usable separation threshold.

Therefore, `Phi` has only one valid role in the final manuscript: a deprecated scalar proxy whose failure motivates replacement by the latent-state-regime mixture.

## Accepted representation layer

The accepted representation is probabilistic:

`cell state -> posterior mass over latent state regimes`

Rather than assigning each sample to one scalar position, the model allows a sample to carry mixed support across regimes. This makes overlap a feature of the representation, not a contradiction.

## Dynamical statement

The locked dynamical statement is:

`dS/dt = sum_Z P(Z|S,W_GRN) F_Z(S,U,W_GRN) + xi(S)`

where:

| Symbol | Reconstructed role | Claim boundary |
|---|---|---|
| `S` | Processed cell-state vector / state-score representation | Not expanded in this recovery step |
| `W_GRN` | Learned gene-regulatory network object used in posterior/regime conditioning | Not re-trained here |
| `Z` | Latent state regime variable | Fixed four-regime definition only |
| `P(Z|S,W_GRN)` | Posterior regime mixture | Primary representation |
| `F_Z(S,U,W_GRN)` | Regime-conditioned dynamical component | Interpreted as computational model structure |
| `xi(S)` | Residual/stochastic component | Not used to claim direct mechanism |

## Biological interpretation

| Biological component | Final architecture role | Forbidden interpretation |
|---|---|---|
| Stemness / Wnt-like plasticity | Local accessibility contribution to `S` | Global fate driver |
| RA/HOX/FGF/SHH/NOTCH positional programs | Regime-conditioned developmental coordinate | Universal species-ranking axis |
| BMP/p53/p21/p16/Rb fate-lock | Adult-repair basin constraint | Complete aging law |
| Salamander blastema | Distinct latent regenerative regime | Elevated scalar state |
| Mammalian repair | Adult-repair-dominant posterior mixture | Lower-intensity salamander regeneration |
| Tumor-like plasticity | Distinct high-plasticity branch | Regeneration-equivalent state |

## Dry-lab perturbation layer

The perturbation-consistency module is supplementary. It tests whether perturbation-associated posterior shifts are directionally compatible with regime-conditioned structure.

Recovered state:

- Global `W_GRN` alone is insufficient.
- Regime-conditioned `W(Z)` reduces error relative to global `W_GRN`.
- The result is partial, not complete.
- RA and BMP provide the strongest directional support.
- NOTCH/SHH inconsistency and counterfactual reversals limit interpretation.

The only safe claim is partial regime-conditioned dry-lab perturbation consistency.

## Model lineage logic

The current manuscript architecture is:

`PGCS/Phi scalar assumption -> validation failure -> scalar embedding breakdown -> latent-state-regime mixture replacement -> partial supplementary perturbation consistency`

This is a replacement logic. The scalar model is not improved, calibrated, rescued, or partially retained as an explanatory model.

## Files anchoring the architecture

| File | Architecture role |
|---|---|
| `outputs/model_lineage_section.md` | Explicit model-replacement section |
| `outputs/model_evolution_map_caption.md` | Figure 1A lineage caption |
| `outputs/MODEL_EVOLUTION_MAP_Figure1A.png` | Visual model-evolution map |
| `outputs/final_claim_safe_main_text_with_model_lineage.md` | Current main-text architecture |
| `outputs/final_9figures_reconstructed/` | Locked main figure system |
| `outputs/SUPP_FIGURE_CAUSAL_CLOSURE_REDESIGNED.png` | Supplementary perturbation audit dashboard |

## Architecture verdict

The architecture is internally coherent if and only if all manuscript text treats `Phi` as rejected, uses `P(Z|S,W_GRN)` as the accepted representation, and restricts perturbation language to partial dry-lab consistency.
