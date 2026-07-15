#!/usr/bin/env python3
"""Rebuild the developmental phase-transition closure outputs.

Run from the project root:
    python3 outputs/figure_reconstruction_pipeline.py

This delegates to the audited pipeline in work/full_data_closure_phase_transition.py.
All figures written by that script are bound in figure_data_binding_map.tsv and use
aligned_state_matrix.tsv plus Phi_unified.tsv as primary figure-data sources.
"""
from pathlib import Path
import runpy

ROOT = Path("/Users/hanchengdezhuanqiangongju/Documents/Codex/2026-06-18/task-reconstruct-and-continue-analysis-of")
runpy.run_path(str(ROOT / "work" / "full_data_closure_phase_transition.py"), run_name="__main__")
