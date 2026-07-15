# Final Closure State Report

## Scope

This is a regime-conditioned causal dynamics closure audit. It conditions the existing W_GRN on locked latent state regimes and existing perturbation-derived posterior shifts. It does not retrain W_GRN, generate new perturbations, or establish wet-lab causality.

## Governing Form

`dS/dt = W(S,Z) * S + B(Z) + xi(S,Z)`

where `W(S,Z)` is represented here by `W(Z) = E[W | Z]` estimated from the locked global W_GRN, posterior-weighted regime state context, and existing pathway ΔZ response gates.

## Input Availability

- `perturbation_deltaZ`: available
- `counterfactual`: available
- `cross_dataset`: available
- `closure_summary`: available
- `null_control`: available
- `w_grn`: available
- `w_grn_sparse`: available
- `posterior`: available

## Closure Classification

- Final class: `PARTIAL_CLOSURE`
- Decision: causal closure fails globally but holds locally in regime-conditioned subspaces
- Prediction error reduction proxy: 0.6262
- Likelihood improvement: 9.8401
- Bootstrap p-value for positive error reduction: 0.0295
- Mean regime-conditioned cosine: 0.4577
- Cross-regime instability ratio: 1.0000
- Counterfactual direction reversal frequency: 0.7000

## Required Interpretation

causal closure fails globally but holds locally in regime-conditioned subspaces

The local statement is conditional: regime conditioning reduces error or improves directional alignment, but global W is rejected because counterfactual inconsistency and/or cross-regime instability remain.

## Regime GRN Summary

latent_regime	module	n_edges	mean_abs_regime_conditioned_weight	median_abs_regime_conditioned_weight	signed_weight_sum	sparse_edge_fraction	status
adult_repair	ALL_MODULES	5761	0.14419394764774143	0.13	265.7150420480318	0.18121853844818608	computed_regime_conditioned_expected_W
embryonic_reactivation	ALL_MODULES	5761	0.13344400749584537	0.125	282.6550654162611	0.18121853844818608	computed_regime_conditioned_expected_W
salamander_blastema	ALL_MODULES	5761	0.11941389950249422	0.113	300.1241471719149	0.18121853844818608	computed_regime_conditioned_expected_W
salamander_intact	ALL_MODULES	5761	0.15414202568662447	0.1332454409870614	254.03578444746756	0.18121853844818608	computed_regime_conditioned_expected_W


## Regime Delta Consistency Summary

latent_regime	n_pathways	within_regime_cosine_global_W	within_regime_cosine_regime_conditioned_LOO	within_regime_corr_global_W	within_regime_corr_regime_conditioned_LOO	mean_global_abs_error	mean_regime_conditioned_abs_error_LOO	error_reduction_fraction	global_sign_alignment_rate	regime_conditioned_sign_alignment_rate_LOO
adult_repair	5	-0.26837916467966083	0.319852416988121	0.21375834431258706	0.13717634725175887	0.06872623311081888	0.06934684821750262	-0.009030250583980326	0.4	0.4
embryonic_reactivation	5	-0.3286197020366118	0.8146408126493176	0.5734275592326354	0.49180909495465713	0.12724805420227095	0.05363874376198743	0.5784710100421311	0.2	0.8
salamander_blastema	5	-0.17234441902299324	-0.17396047233639014	-0.2251254456204416	-0.9973129387097043	0.020682167721152698	0.01984331240375175	0.04055935183926629	0.4	0.8
salamander_intact	5	-0.45764230139982226	0.8701641127206539	0.12928849554910757	-0.8960454443258309	0.06778635662495264	0.028287923936024757	0.5826900080714505	0.2	1.0


## Bias Summary

level	latent_regime	pathway	systematic_bias_mean	systematic_bias_sd	mean_abs_bias	bias_symmetry_score	direction_reversal_frequency	n_pathways	status
regime_summary	adult_repair	ALL_PATHWAYS	-0.06747422724090348	0.06343874377516444	0.06872623311081888	0.0182172921931657	0.6	5	computed
regime_summary	embryonic_reactivation	ALL_PATHWAYS	0.12724805420227095	0.05246914905912324	0.12724805420227095	0.0	0.8	5	computed
regime_summary	salamander_blastema	ALL_PATHWAYS	0.0080125296635855	0.01990288678372679	0.020682167721152698	0.6125875308809782	0.6	5	computed
regime_summary	salamander_intact	ALL_PATHWAYS	-0.06778635662495264	0.028552707472087904	0.06778635662495264	0.0	0.8	5	computed


## Evidence Boundary

The regime-conditioned W(Z) matrix is an evidence-conditioned expectation of existing W_GRN, not a newly trained causal GRN. Cross-dataset perturbation invariance remains limited where pathway perturbations are available from only one direct perturbation dataset.