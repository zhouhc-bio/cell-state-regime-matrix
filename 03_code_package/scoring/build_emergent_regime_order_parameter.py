#!/usr/bin/env python3
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/hanchengdezhuanqiangongju/Documents/Codex/2026-06-18/task-reconstruct-and-continue-analysis-of")
OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

STATE_AXES = ["Stemness", "Transitional", "Fate_lock", "Embryonic_program_activation"]
AXIS_RENAME = {
    "P": "Stemness",
    "C": "Transitional",
    "S": "Fate_lock",
    "G": "Embryonic_program_activation",
}
K_SIGMOID = 7.0
TERM_WEIGHTS = {
    "stemness_minus_baseline": 0.22,
    "inverse_fate_lock": 0.22,
    "embryonic_axis_score": 0.24,
    "WE_eigenmode_alignment": 0.20,
    "anti_WA_eigenmode_alignment": 0.12,
}


def sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-x))


def get_fonts() -> tuple[ImageFont.ImageFont, ImageFont.ImageFont, ImageFont.ImageFont]:
    for name in ["Arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]:
        try:
            return ImageFont.truetype(name, 22), ImageFont.truetype(name, 15), ImageFont.truetype(name, 12)
        except Exception:
            pass
    f = ImageFont.load_default()
    return f, f, f


def load_state_axis_matrix() -> pd.DataFrame:
    mat = pd.read_csv(OUT / "W_GRN_learned_state_axis_matrix.tsv", sep="\t")
    mat = mat.rename(columns=AXIS_RENAME)
    return mat[["source", *STATE_AXES]].fillna(0.0)


def gene_sets_from_wgrn() -> tuple[set[str], set[str]]:
    w = pd.read_csv(OUT / "W_GRN_learned.tsv", sep="\t")
    embryonic_pat = re.compile(r"(HOX|FGF|FGFR|SHH|GLI|WNT|FZD|TCF7|LEF|RAR|RARB|RARG|RARA|CYP26|ALDH1A)", re.I)
    adult_pat = re.compile(r"(BMP|SMAD|TP53|CDKN|RB1|ARF|NFKB|RELA|TNF|IL1|IL6|JUN|FOS|CXCL|CCL|SERPINE)", re.I)
    embryonic_modules = {"WNT_stemness_module", "FGF_SHH_module", "RA_module"}
    adult_modules = {"BMP_module", "p53_Rb_fate_lock_module"}

    embryonic: set[str] = set()
    adult: set[str] = set()
    for _, row in w.iterrows():
        source = str(row.get("source", ""))
        target = str(row.get("target", ""))
        module = str(row.get("module", ""))
        if module in embryonic_modules or embryonic_pat.search(source) or embryonic_pat.search(target):
            embryonic.add(source)
            if not target.startswith("STATE_AXIS:"):
                embryonic.add(target)
        if module in adult_modules or adult_pat.search(source) or adult_pat.search(target):
            adult.add(source)
            if not target.startswith("STATE_AXIS:"):
                adult.add(target)
    return embryonic, adult


def normalized(v: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(v))
    if norm == 0:
        return v.copy()
    return v / norm


def module_eigenmode(axis_matrix: pd.DataFrame, genes: set[str], orientation: np.ndarray) -> tuple[np.ndarray, int, str]:
    rows = axis_matrix[axis_matrix["source"].isin(genes)]
    if len(rows) < 3:
        return normalized(orientation), len(rows), "fallback_orientation_due_to_low_module_overlap"
    x = rows[STATE_AXES].to_numpy(dtype=float)
    x = x - x.mean(axis=0, keepdims=True)
    try:
        _, _, vt = np.linalg.svd(x, full_matrices=False)
        mode = normalized(vt[0])
        status = "W_GRN_module_PC1_oriented_by_biology"
    except np.linalg.LinAlgError:
        mode = normalized(orientation)
        status = "fallback_orientation_due_to_svd_failure"
    if float(np.dot(mode, orientation)) < 0:
        mode = -mode
    return mode, len(rows), status


def build_modes(axis_matrix: pd.DataFrame) -> dict[str, object]:
    embryonic_genes, adult_genes = gene_sets_from_wgrn()
    embryonic_orientation = normalized(np.array([0.45, 0.20, -0.55, 0.70], dtype=float))
    adult_orientation = normalized(np.array([-0.35, 0.10, 0.75, -0.55], dtype=float))
    embryonic_mode, n_emb, emb_status = module_eigenmode(axis_matrix, embryonic_genes, embryonic_orientation)
    adult_mode, n_adult, adult_status = module_eigenmode(axis_matrix, adult_genes, adult_orientation)
    return {
        "embryonic_mode": embryonic_mode,
        "adult_mode": adult_mode,
        "n_embryonic_genes_with_state_axis": n_emb,
        "n_adult_genes_with_state_axis": n_adult,
        "embryonic_mode_status": emb_status,
        "adult_mode_status": adult_status,
    }


def phi_terms(S: np.ndarray, modes: dict[str, object]) -> dict[str, float]:
    centered = S - 0.5
    embryonic_mode = np.asarray(modes["embryonic_mode"], dtype=float)
    adult_mode = np.asarray(modes["adult_mode"], dtype=float)
    terms = {
        "stemness_minus_baseline": centered[0],
        "inverse_fate_lock": 0.5 - S[2],
        "embryonic_axis_score": centered[3],
        "WE_eigenmode_alignment": float(np.dot(centered, embryonic_mode)),
        "anti_WA_eigenmode_alignment": -float(np.dot(centered, adult_mode)),
    }
    return terms


def phi_score(S: np.ndarray, modes: dict[str, object]) -> tuple[float, float, dict[str, float]]:
    terms = phi_terms(S, modes)
    phi = float(sum(TERM_WEIGHTS[k] * terms[k] for k in TERM_WEIGHTS))
    r = float(sigmoid(K_SIGMOID * phi))
    return phi, r, terms


def compute_phi_for_trajectory(modes: dict[str, object]) -> pd.DataFrame:
    traj = pd.read_csv(OUT / "mammal_vs_salamander_trajectory_comparison.tsv", sep="\t")
    rows = []
    for _, row in traj.iterrows():
        S = row[STATE_AXES].to_numpy(dtype=float)
        phi, r, terms = phi_score(S, modes)
        out = row.to_dict()
        out["Phi"] = phi
        out["R_emergent"] = r
        out["dominant_regime_emergent"] = "embryonic_accessible_E" if r >= 0.5 else "adult_constrained_A"
        out.update({f"Phi_term_{k}": v for k, v in terms.items()})
        rows.append(out)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "emergent_R_trajectory_reanalysis.tsv", sep="\t", index=False)
    return df


def build_phi_formula_table(modes: dict[str, object]) -> None:
    rows = []
    interpretations = {
        "stemness_minus_baseline": "Stemness axis above neutral state increases developmental accessibility.",
        "inverse_fate_lock": "Low Fate_lock removes adult/senescent basin constraint.",
        "embryonic_axis_score": "Embryonic/positional axis activation increases blastema-like accessibility.",
        "WE_eigenmode_alignment": "State aligns with embryonic W_GRN mode derived from HOX/FGF/SHH/WNT/RA-linked genes.",
        "anti_WA_eigenmode_alignment": "State is anti-aligned with adult W_GRN mode derived from BMP/SMAD/p53/inflammatory genes.",
    }
    computations = {
        "stemness_minus_baseline": "Stemness - 0.5",
        "inverse_fate_lock": "0.5 - Fate_lock",
        "embryonic_axis_score": "Embryonic_program_activation - 0.5",
        "WE_eigenmode_alignment": "dot(S - 0.5, first W_GRN embryonic module PC1)",
        "anti_WA_eigenmode_alignment": "-dot(S - 0.5, first W_GRN adult module PC1)",
    }
    for name, weight in TERM_WEIGHTS.items():
        rows.append(
            {
                "Phi_term": name,
                "coefficient": weight,
                "calculation": computations[name],
                "biological_mapping": interpretations[name],
                "source": "S and W_GRN_learned_state_axis_matrix.tsv",
                "status": "mechanistic_weight_not_species_fitted",
            }
        )
    for label, mode in [("WE_eigenmode_vector", modes["embryonic_mode"]), ("WA_eigenmode_vector", modes["adult_mode"])]:
        for axis, value in zip(STATE_AXES, np.asarray(mode, dtype=float)):
            rows.append(
                {
                    "Phi_term": label,
                    "coefficient": value,
                    "calculation": f"{label} component on {axis}",
                    "biological_mapping": "Empirical state-space reduction of W_GRN module activity.",
                    "source": "W_GRN_learned_state_axis_matrix.tsv",
                    "status": "computed_from_learned_W_GRN",
                }
            )
    rows.extend(
        [
            {
                "Phi_term": "R_emergent",
                "coefficient": K_SIGMOID,
                "calculation": "R(S) = 1 / (1 + exp(-k * Phi(S,W_GRN)))",
                "biological_mapping": "Continuous embryonic accessibility of the regulatory network.",
                "source": "Phi terms above",
                "status": "derived_from_Phi_not_directly_from_U",
            },
            {
                "Phi_term": "embryonic_module_overlap_n",
                "coefficient": modes["n_embryonic_genes_with_state_axis"],
                "calculation": "count of W_GRN genes in embryonic module with state-axis weights",
                "biological_mapping": "HOX/FGF/SHH/WNT/RA-linked state-axis evidence.",
                "source": "W_GRN_learned.tsv",
                "status": modes["embryonic_mode_status"],
            },
            {
                "Phi_term": "adult_module_overlap_n",
                "coefficient": modes["n_adult_genes_with_state_axis"],
                "calculation": "count of W_GRN genes in adult module with state-axis weights",
                "biological_mapping": "BMP/SMAD/p53/inflammatory state-axis evidence.",
                "source": "W_GRN_learned.tsv",
                "status": modes["adult_mode_status"],
            },
        ]
    )
    pd.DataFrame(rows).to_csv(OUT / "Phi_score_formula.tsv", sep="\t", index=False)


def color_interp(v: float) -> tuple[int, int, int]:
    v = max(0.0, min(1.0, v))
    blue = np.array([44, 127, 184], dtype=float)
    cream = np.array([245, 245, 220], dtype=float)
    red = np.array([184, 50, 44], dtype=float)
    if v < 0.5:
        out = blue + (cream - blue) * (v / 0.5)
    else:
        out = cream + (red - cream) * ((v - 0.5) / 0.5)
    return tuple(int(x) for x in out)


def draw_phi_distribution(df: pd.DataFrame) -> None:
    img = Image.new("RGB", (1120, 720), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((255, 24), "Phi distribution: mammal vs salamander trajectory reanalysis", fill=(17, 24, 39), font=title)
    left, top, width, height = 90, 120, 720, 440
    draw.rectangle([left, top, left + width, top + height], outline=(30, 41, 59), width=2)
    bins = np.linspace(-0.75, 0.75, 42)
    systems = [
        ("mammalian_adult_repair", (221, 139, 40), "mammalian adult repair"),
        ("salamander_embryonic_reactivation", (44, 127, 184), "salamander embryonic"),
    ]
    hist_data = []
    max_density = 0.0
    for system, color, label in systems:
        values = df.loc[df["system"] == system, "Phi"].to_numpy()
        hist, edges = np.histogram(values, bins=bins, density=True)
        max_density = max(max_density, float(hist.max()))
        hist_data.append((hist, edges, color, label))
    max_density = max(max_density, 1e-6)
    for hist, edges, color, _ in hist_data:
        pts = []
        for h, x0, x1 in zip(hist, edges[:-1], edges[1:]):
            x = left + ((x0 + x1) / 2 - bins.min()) / (bins.max() - bins.min()) * width
            y = top + height - h / max_density * height
            pts.append((int(x), int(y)))
        if len(pts) > 1:
            draw.line(pts, fill=color, width=4)
            for x, y in pts:
                draw.ellipse([x - 2, y - 2, x + 2, y + 2], fill=color)
    x0 = int(left + (0 - bins.min()) / (bins.max() - bins.min()) * width)
    draw.line([(x0, top), (x0, top + height)], fill=(15, 23, 42), width=2)
    draw.text((x0 + 8, top + 8), "Phi=0 / R=0.5", fill=(15, 23, 42), font=small)
    draw.text((left + 300, top + height + 34), "Phi(S, W_GRN)", fill=(30, 41, 59), font=font)
    draw.text((18, top + 190), "density", fill=(30, 41, 59), font=font)
    for i, (_, color, label) in enumerate(systems):
        draw.rectangle([840, 160 + 34 * i, 860, 180 + 34 * i], fill=color)
        draw.text((870, 156 + 34 * i), label, fill=(30, 41, 59), font=small)
    draw.text((840, 260), "Evidence boundary:", fill=(17, 24, 39), font=font)
    notes = ["reanalysis of model", "trajectory states;", "not species-fitted", "single-cell data."]
    for i, note in enumerate(notes):
        draw.text((840, 292 + 22 * i), note, fill=(51, 65, 85), font=small)
    img.save(OUT / "salamander_vs_mammal_Phi_distribution.png")


def build_phi_phase_diagram(modes: dict[str, object]) -> pd.DataFrame:
    rows = []
    imbalance_vals = np.linspace(-1, 1, 81)
    embryonic_vals = np.linspace(-1, 1, 81)
    for imbalance in imbalance_vals:
        for emb_access in embryonic_vals:
            stemness = np.clip(0.5 + 0.35 * imbalance, 0, 1)
            fate_lock = np.clip(0.5 - 0.35 * imbalance, 0, 1)
            embryonic_axis = np.clip(0.5 + 0.35 * emb_access, 0, 1)
            transitional = np.clip(0.5 + 0.12 * (emb_access - abs(imbalance)), 0, 1)
            S = np.array([stemness, transitional, fate_lock, embryonic_axis], dtype=float)
            phi, r, terms = phi_score(S, modes)
            rows.append(
                {
                    "stemness_vs_fate_lock_imbalance": float(imbalance),
                    "embryonic_module_accessibility": float(emb_access),
                    "Stemness": stemness,
                    "Transitional": transitional,
                    "Fate_lock": fate_lock,
                    "Embryonic_program_activation": embryonic_axis,
                    "Phi": phi,
                    "R_emergent": r,
                    "dominant_regime": "embryonic_accessible_E" if r >= 0.5 else "adult_constrained_A",
                    **{f"Phi_term_{k}": v for k, v in terms.items()},
                }
            )
    grid = pd.DataFrame(rows)
    grid.to_csv(OUT / "Phi_phase_diagram.tsv", sep="\t", index=False)
    return grid


def draw_phi_phase_diagram(grid: pd.DataFrame) -> None:
    img = Image.new("RGB", (940, 720), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((255, 24), "Emergent phase diagram from Phi(S, W_GRN)", fill=(17, 24, 39), font=title)
    left, top, plot_w, plot_h = 90, 90, 560, 560
    piv = grid.pivot(
        index="embryonic_module_accessibility",
        columns="stemness_vs_fate_lock_imbalance",
        values="R_emergent",
    ).sort_index(ascending=True)
    arr = piv.to_numpy()
    canvas = Image.new("RGB", arr.shape[::-1], "white")
    pix = canvas.load()
    for j in range(arr.shape[0]):
        for i in range(arr.shape[1]):
            pix[i, arr.shape[0] - 1 - j] = color_interp(float(arr[j, i]))
    canvas = canvas.resize((plot_w, plot_h))
    img.paste(canvas, (left, top))
    draw.rectangle([left, top, left + plot_w, top + plot_h], outline=(30, 41, 59), width=2)
    boundary = []
    for emb, sub in grid.groupby("embryonic_module_accessibility", sort=True):
        sub = sub.sort_values("stemness_vs_fate_lock_imbalance")
        xs = sub["stemness_vs_fate_lock_imbalance"].to_numpy()
        rs = sub["R_emergent"].to_numpy()
        if not np.any(rs >= 0.5):
            continue
        idx = int(np.argmax(rs >= 0.5))
        if idx == 0:
            xval = xs[idx]
        else:
            r0, r1 = rs[idx - 1], rs[idx]
            x0, x1 = xs[idx - 1], xs[idx]
            frac = 0.0 if r1 == r0 else (0.5 - r0) / (r1 - r0)
            xval = x0 + frac * (x1 - x0)
        px = int(left + (xval + 1) / 2 * plot_w)
        py = int(top + (1 - (emb + 1) / 2) * plot_h)
        boundary.append((px, py))
    if len(boundary) > 1:
        draw.line(boundary, fill=(255, 255, 255), width=5)
        draw.line(boundary, fill=(15, 23, 42), width=2)
    draw.text((185, 665), "Stemness - Fate_lock imbalance", fill=(30, 41, 59), font=font)
    draw.text((10, 315), "Embryonic module accessibility", fill=(30, 41, 59), font=small)
    draw.text((690, 125), "Blue: adult-constrained", fill=(44, 127, 184), font=font)
    draw.text((690, 165), "Red: embryonic-accessible", fill=(184, 50, 44), font=font)
    draw.line([(690, 210), (750, 210)], fill=(15, 23, 42), width=2)
    draw.text((760, 200), "Phi=0 boundary", fill=(30, 41, 59), font=small)
    draw.text((690, 250), "No direct U axis:", fill=(17, 24, 39), font=font)
    for i, note in enumerate(["R is derived from", "state and W_GRN", "module alignment."]):
        draw.text((690, 285 + 22 * i), note, fill=(51, 65, 85), font=small)
    img.save(OUT / "Phi_phase_diagram.png")


def build_bifurcation(df: pd.DataFrame, modes: dict[str, object]) -> pd.DataFrame:
    adult = df.loc[df["system"] == "mammalian_adult_repair", STATE_AXES].tail(25).mean().to_numpy(dtype=float)
    embryo = df.loc[df["system"] == "salamander_embryonic_reactivation", STATE_AXES].tail(25).mean().to_numpy(dtype=float)
    rows = []
    for q in np.linspace(0, 1, 121):
        S = (1 - q) * adult + q * embryo
        phi, r, terms = phi_score(S, modes)
        rows.append(
            {
                "state_continuation_coordinate": float(q),
                "Phi": phi,
                "R_emergent": r,
                "dR_dPhi": K_SIGMOID * r * (1 - r),
                "dominant_regime": "embryonic_accessible_E" if r >= 0.5 else "adult_constrained_A",
                **{axis: S[i] for i, axis in enumerate(STATE_AXES)},
                **{f"Phi_term_{k}": v for k, v in terms.items()},
            }
        )
    bif = pd.DataFrame(rows)
    bif.to_csv(OUT / "Phi_bifurcation_analysis.tsv", sep="\t", index=False)
    return bif


def draw_bifurcation(bif: pd.DataFrame) -> None:
    img = Image.new("RGB", (1020, 700), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((265, 24), "Bifurcation analysis using Phi order parameter", fill=(17, 24, 39), font=title)
    left, top, width, height = 100, 100, 600, 460
    draw.rectangle([left, top, left + width, top + height], outline=(30, 41, 59), width=2)
    q = bif["state_continuation_coordinate"].to_numpy()
    phi = bif["Phi"].to_numpy()
    r = bif["R_emergent"].to_numpy()
    ymin, ymax = -0.65, 0.65
    def map_pt(x: float, y: float) -> tuple[int, int]:
        px = int(left + x * width)
        py = int(top + (1 - (y - ymin) / (ymax - ymin)) * height)
        return px, py
    phi_pts = [map_pt(float(x), float(y)) for x, y in zip(q, phi)]
    r_pts = [map_pt(float(x), float((y - 0.5) * 1.2)) for x, y in zip(q, r)]
    draw.line(phi_pts, fill=(30, 64, 116), width=4)
    draw.line(r_pts, fill=(184, 50, 44), width=4)
    yzero = map_pt(0, 0)[1]
    draw.line([(left, yzero), (left + width, yzero)], fill=(15, 23, 42), width=1)
    crossing = bif.iloc[(bif["Phi"].abs()).argsort()[:1]]
    if len(crossing):
        cx = float(crossing["state_continuation_coordinate"].iloc[0])
        xline = int(left + cx * width)
        draw.line([(xline, top), (xline, top + height)], fill=(15, 23, 42), width=2)
        draw.text((xline + 8, top + 8), f"Phi=0 at q={cx:.2f}", fill=(15, 23, 42), font=small)
    draw.text((220, 590), "state continuation: adult repair -> embryonic reactivation", fill=(30, 41, 59), font=small)
    draw.text((30, 305), "Phi / centered R", fill=(30, 41, 59), font=small)
    draw.rectangle([750, 150, 770, 170], fill=(30, 64, 116))
    draw.text((780, 146), "Phi(S,W_GRN)", fill=(30, 41, 59), font=small)
    draw.rectangle([750, 185, 770, 205], fill=(184, 50, 44))
    draw.text((780, 181), "R_emergent centered", fill=(30, 41, 59), font=small)
    draw.text((750, 250), "Updated criterion:", fill=(17, 24, 39), font=font)
    notes = ["bifurcation occurs", "when Phi crosses 0,", "not when an external", "R(U,S) switch is set."]
    for i, note in enumerate(notes):
        draw.text((750, 285 + 22 * i), note, fill=(51, 65, 85), font=small)
    img.save(OUT / "Phi_bifurcation_analysis.png")


def write_emergent_definition(df: pd.DataFrame, modes: dict[str, object], bif: pd.DataFrame) -> None:
    summary = df.groupby("system").agg(
        Phi_mean=("Phi", "mean"),
        Phi_final=("Phi", "last"),
        R_emergent_mean=("R_emergent", "mean"),
        R_emergent_final=("R_emergent", "last"),
    )
    crossing = bif.iloc[(bif["Phi"].abs()).argsort()[:1]]
    q_cross = float(crossing["state_continuation_coordinate"].iloc[0])
    md = f"""# Emergent R Definition

## 核心修正

`R` 不再定义为外部的成人/胚胎机制选择器。新的模型先从细胞状态和经验基因调控网络计算发育机制秩序参数：

```text
Phi(S, W_GRN) = a1 Stemness - a2 Fate_lock + a3 Embryonic_axis
                + a4 projection_on_W_E_modes - a5 projection_on_W_A_modes
```

然后由 `Phi` 连续产生胚胎可达性：

```text
R(S) = 1 / (1 + exp(-k * Phi(S, W_GRN)))
k = {K_SIGMOID:.1f}
```

因此 `R` 是调控网络的胚胎可达性，而不是手写开关。`U` 不再直接进入 `R`；WNT/FGF/SHH/RA/BMP 等扰动只能先改变 `S` 或 `W_GRN(U)` 的有效状态，再间接改变 `Phi` 与 `R`。

## W_GRN 模态来源

- 胚胎模态 `W_E`：从 HOX/FGF/SHH/WNT/RA 相关基因在 `W_GRN_learned_state_axis_matrix.tsv` 中的状态轴权重计算，重叠基因数 = {modes['n_embryonic_genes_with_state_axis']}，状态 = `{modes['embryonic_mode_status']}`。
- 成人模态 `W_A`：从 BMP/SMAD/p53/炎症相关基因在 `W_GRN_learned_state_axis_matrix.tsv` 中的状态轴权重计算，重叠基因数 = {modes['n_adult_genes_with_state_axis']}，状态 = `{modes['adult_mode_status']}`。

## 修订后的动力学

```text
dS/dt = [(1 - R(S)) W_A + R(S) W_E] S + B(U) + xi(S)
```

其中：

- `R(S)` 由 `Phi(S,W_GRN)` 涌现，不是外部指定；
- `B(U)` 是路径扰动对状态轴的直接输入；
- `xi(S)` 是状态依赖噪声；
- 成人修复与胚胎再激活仍是两个不同吸引子机制。

## 轨迹重分析摘要

| system | Phi_mean | Phi_final | R_mean | R_final |
|---|---:|---:|---:|---:|
| mammalian_adult_repair | {summary.loc['mammalian_adult_repair','Phi_mean']:.3f} | {summary.loc['mammalian_adult_repair','Phi_final']:.3f} | {summary.loc['mammalian_adult_repair','R_emergent_mean']:.3f} | {summary.loc['mammalian_adult_repair','R_emergent_final']:.3f} |
| salamander_embryonic_reactivation | {summary.loc['salamander_embryonic_reactivation','Phi_mean']:.3f} | {summary.loc['salamander_embryonic_reactivation','Phi_final']:.3f} | {summary.loc['salamander_embryonic_reactivation','R_emergent_mean']:.3f} | {summary.loc['salamander_embryonic_reactivation','R_emergent_final']:.3f} |

## Phi 分岔判据

沿成人修复状态到胚胎再激活状态的连续路径，`Phi=0` 的机制边界出现在：

```text
state_continuation_coordinate ~= {q_cross:.3f}
```

边界由 `Phi` 的符号决定，而不是由手动 `R(U,S)` 阈值决定。

## 可证伪预测

1. 单细胞转录组或 multiome 数据中应可测得连续的 `Phi(S,W_GRN)`。
2. 蝾螈 blastema 形成期应显示 `Phi` 上升并跨过 `Phi=0` 附近的机制边界。
3. 哺乳动物瘢痕修复应保持低 `Phi` 或无法稳定跨过 `Phi=0`。
4. WNT/FGF/SHH 操作应连续移动 `Phi` 分布，而不是产生离散的人工机制标签跳变。

## 证据边界

当前输出把 `R` 从手写函数改写为由 learned `W_GRN` 状态轴权重和模拟轨迹状态共同决定的秩序参数。这里的“mammal vs salamander”分布是上一轮机制轨迹的重分析，不是新的物种实测单细胞数据拟合。
"""
    (OUT / "emergent_R_definition.md").write_text(md, encoding="utf-8")


def main() -> int:
    axis_matrix = load_state_axis_matrix()
    modes = build_modes(axis_matrix)
    build_phi_formula_table(modes)
    df = compute_phi_for_trajectory(modes)
    grid = build_phi_phase_diagram(modes)
    bif = build_bifurcation(df, modes)
    draw_phi_distribution(df)
    draw_phi_phase_diagram(grid)
    draw_bifurcation(bif)
    write_emergent_definition(df, modes, bif)
    print("emergent R reconstruction complete")
    print(f"embryonic_mode_overlap_n={modes['n_embryonic_genes_with_state_axis']}")
    print(f"adult_mode_overlap_n={modes['n_adult_genes_with_state_axis']}")
    print(df.groupby("system")["R_emergent"].agg(["mean", "min", "max"]).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
