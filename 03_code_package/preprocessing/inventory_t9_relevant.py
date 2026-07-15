#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
from pathlib import Path


ROOTS = [
    Path("/Volumes/T9/PGCS"),
    Path("/Volumes/T9/最终投稿包_有序归档"),
    Path("/Volumes/T9/nature_reviewer_alignment_outputs"),
]

OUT = Path("/Users/hanchengdezhuanqiangongju/Documents/Codex/2026-06-18/task-reconstruct-and-continue-analysis-of/outputs")
OUT.mkdir(parents=True, exist_ok=True)

SKIP_DIR_NAMES = {
    ".Spotlight-V100",
    ".Trashes",
    ".TemporaryItems",
    "System Volume Information",
    "__pycache__",
}

RELEVANT_SUFFIXES = (
    ".h5ad",
    ".h5mu",
    ".loom",
    ".rds",
    ".rdata",
    ".h5",
    ".mtx",
    ".mtx.gz",
    ".tar",
    ".tar.gz",
    ".tsv",
    ".tsv.gz",
    ".csv",
    ".csv.gz",
    ".xlsx",
    ".r",
    ".R",
    ".py",
    ".ipynb",
    ".yaml",
    ".yml",
    ".json",
)

KEYWORDS = [
    "GSE153596",
    "GSE75748",
    "GSE147298",
    "GSE178758",
    "GSE239276",
    "GSE157660",
    "GSE126074",
    "GSE90546",
    "GSE195467",
    "GSE195655",
    "GSE90063",
    "GSE133344",
    "GSE221321",
    "GSE216800",
    "GSE216909",
    "GSE236519",
    "GSE249416",
    "perturb",
    "crispr",
    "sceptre",
    "scperturb",
    "causal",
    "falsification",
    "validation",
    "cellrank",
    "scvelo",
    "velocity",
    "pseudotime",
    "trajectory",
    "terminal",
    "transition",
    "state_score",
    "module_score",
    "PC_score",
    "pc_score",
    "chromvar",
    "motif",
    "cicero",
    "scarlink",
    "scenic",
    "grn",
    "peak_gene",
    "multiome",
    "atac",
    "fragments",
    "W_GRN",
    "regulatory",
    "source_data",
]


def suffix_match(name: str) -> str:
    low = name.lower()
    return ",".join(s for s in RELEVANT_SUFFIXES if low.endswith(s.lower()))


def keyword_match(path: str) -> str:
    low = path.lower()
    hits = []
    for kw in KEYWORDS:
        if kw.lower() in low:
            hits.append(kw)
    return ",".join(dict.fromkeys(hits))


def classify(path: Path, suffix_hits: str, keyword_hits: str) -> str:
    low = path.as_posix().lower()
    if any(x in low for x in ["h5ad", "h5mu", ".loom", ".rds", ".rdata"]):
        return "processed_single_cell_object"
    if any(x in low for x in ["perturb", "crispr", "scperturb", "sceptre", "causal"]):
        return "perturbation_or_causal_artifact"
    if any(x in low for x in ["chromvar", "motif", "cicero", "scarlink", "scenic", "peak_gene", "grn"]):
        return "chromatin_or_grn_artifact"
    if any(x in low for x in ["cellrank", "scvelo", "velocity", "pseudotime", "trajectory", "transition"]):
        return "trajectory_or_transition_artifact"
    if any(x in low for x in ["source_data", "source-data", "sourcedata"]):
        return "source_data_artifact"
    if suffix_hits:
        return "data_or_code_candidate"
    if keyword_hits:
        return "keyword_candidate"
    return "other"


def main() -> int:
    rows = []
    dir_rows = []
    for root in ROOTS:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES and not d.startswith("._")]
            pdir = Path(dirpath)
            try:
                rel_depth = len(pdir.relative_to(root).parts)
            except ValueError:
                rel_depth = 0
            if rel_depth <= 4:
                dir_rows.append(
                    {
                        "root": str(root),
                        "directory": str(pdir),
                        "n_files_immediate": len(filenames),
                        "n_subdirs_immediate": len(dirnames),
                    }
                )
            for fn in filenames:
                if fn.startswith("._"):
                    continue
                path = pdir / fn
                s_hits = suffix_match(fn)
                k_hits = keyword_match(path.as_posix())
                if not s_hits and not k_hits:
                    continue
                try:
                    st = path.stat()
                except OSError:
                    continue
                rows.append(
                    {
                        "path": str(path),
                        "size_bytes": st.st_size,
                        "mtime_epoch": int(st.st_mtime),
                        "suffix_hits": s_hits,
                        "keyword_hits": k_hits,
                        "artifact_class": classify(path, s_hits, k_hits),
                    }
                )

    rows.sort(key=lambda r: (r["artifact_class"], r["path"]))
    dir_rows.sort(key=lambda r: r["directory"])

    with (OUT / "t9_relevant_artifact_inventory.tsv").open("w", newline="", encoding="utf-8") as f:
        cols = ["path", "size_bytes", "mtime_epoch", "suffix_hits", "keyword_hits", "artifact_class"]
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
        w.writeheader()
        w.writerows(rows)

    with (OUT / "t9_directory_inventory.tsv").open("w", newline="", encoding="utf-8") as f:
        cols = ["root", "directory", "n_files_immediate", "n_subdirs_immediate"]
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
        w.writeheader()
        w.writerows(dir_rows)

    print(f"relevant_files={len(rows)}")
    print(f"directories={len(dir_rows)}")
    print(OUT / "t9_relevant_artifact_inventory.tsv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
