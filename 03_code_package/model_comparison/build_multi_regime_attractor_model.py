#!/usr/bin/env python3
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/Users/hanchengdezhuanqiangongju/Documents/Codex/2026-06-18/task-reconstruct-and-continue-analysis-of")
OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

STATE_AXES = ["Stemness", "Transitional", "Fate_lock", "Embryonic_program_activation"]


def sigmoid(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-x))


def regime_switch(U: dict[str, float], S: np.ndarray) -> float:
    developmental_drive = 0.28 * U["WNT"] + 0.26 * U["FGF"] + 0.22 * U["SHH"] + 0.18 * U["RA_balance"]
    adult_lock = 0.30 * U["BMP"] + 0.25 * U["inflammation"] + 0.20 * S[2]
    state_access = 0.12 * S[0] + 0.10 * S[1] + 0.18 * S[3]
    raw = 7.0 * (developmental_drive + state_access - adult_lock - 0.42)
    return float(sigmoid(raw))


def adult_target(U: dict[str, float]) -> np.ndarray:
    return np.clip(
        np.array(
            [
                0.22 + 0.10 * U["WNT"] + 0.05 * U["FGF"],
                0.36 + 0.24 * U["NOTCH"] + 0.18 * U["inflammation"],
                0.58 + 0.28 * U["BMP"] + 0.20 * U["inflammation"],
                0.08 + 0.06 * U["WNT"] + 0.04 * U["FGF"],
            ]
        ),
        0,
        1,
    )


def embryonic_target(U: dict[str, float]) -> np.ndarray:
    return np.clip(
        np.array(
            [
                0.68 + 0.20 * U["WNT"] + 0.10 * U["FGF"],
                0.58 + 0.12 * U["NOTCH"] + 0.10 * U["FGF"],
                0.16 + 0.10 * U["BMP"],
                0.52 + 0.18 * U["WNT"] + 0.20 * U["FGF"] + 0.18 * U["SHH"] + 0.16 * U["RA_balance"],
            ]
        ),
        0,
        1,
    )


def W_adult(U: dict[str, float]) -> np.ndarray:
    W = np.array(
        [
            [0.18, 0.08, -0.32, -0.10],
            [0.12, 0.26 + 0.12 * U["NOTCH"], 0.08, -0.04],
            [-0.24, -0.08, 0.46 + 0.22 * U["BMP"] + 0.18 * U["inflammation"], -0.25],
            [0.06, 0.02, -0.34, 0.08],
        ]
    )
    return W


def W_embryonic(U: dict[str, float]) -> np.ndarray:
    W = np.array(
        [
            [0.42 + 0.12 * U["WNT"], 0.16, -0.18, 0.22],
            [0.18, 0.34 + 0.08 * U["NOTCH"], -0.10, 0.26],
            [-0.18, -0.10, 0.18 + 0.06 * U["BMP"], -0.38],
            [0.28, 0.18, -0.36, 0.52 + 0.10 * U["FGF"] + 0.08 * U["SHH"]],
        ]
    )
    return W


def drift(S: np.ndarray, U: dict[str, float]) -> tuple[np.ndarray, float]:
    R = regime_switch(U, S)
    WA = W_adult(U)
    WE = W_embryonic(U)
    W_total = (1 - R) * WA + R * WE
    target = (1 - R) * adult_target(U) + R * embryonic_target(U)
    # Coupling around center plus attraction to the regime-specific target.
    centered = S - 0.5
    vector = 0.34 * (target - S) + 0.10 * (W_total @ centered)
    # Mechanistic saturation keeps axes bounded without creating a third regime.
    vector += -0.08 * S * (S - 1.0) * (2.0 * S - 1.0)
    return vector, R


def simulate(U: dict[str, float], S0: np.ndarray, n_steps: int = 160, dt: float = 0.08, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    S = S0.astype(float).copy()
    rows = []
    for t in range(n_steps + 1):
        dS, R = drift(S, U)
        rows.append(
            {
                "time": t * dt,
                "regime_R": R,
                **{axis: S[i] for i, axis in enumerate(STATE_AXES)},
                **{f"U_{k}": v for k, v in U.items()},
            }
        )
        noise = rng.normal(0, 0.006, size=4)
        S = np.clip(S + dt * dS + noise, 0, 1)
    return pd.DataFrame(rows)


def potential_grid(n: int = 220) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    fate = np.linspace(0, 1, n)
    emb = np.linspace(0, 1, n)
    X, Y = np.meshgrid(fate, emb)
    # Adult well: high Fate_lock, low embryonic axis.
    VA = ((X - 0.78) ** 2 / 0.030 + (Y - 0.16) ** 2 / 0.024)
    # Embryonic well: low Fate_lock, high embryonic activation.
    VE = ((X - 0.22) ** 2 / 0.035 + (Y - 0.80) ** 2 / 0.030)
    ridge = 0.35 * np.exp(-((X - 0.50) ** 2 + (Y - 0.48) ** 2) / 0.022)
    V = -np.log(np.exp(-VA) + np.exp(-VE) + 1e-9) + ridge
    return X, Y, V, np.exp(-VE) / (np.exp(-VA) + np.exp(-VE) + 1e-9)


def color_ramp(v: float) -> tuple[int, int, int]:
    v = max(0.0, min(1.0, v))
    stops = [
        (0.0, (30, 64, 116)),
        (0.35, (93, 173, 226)),
        (0.60, (245, 245, 220)),
        (0.82, (221, 139, 40)),
        (1.0, (157, 36, 30)),
    ]
    for (a, ca), (b, cb) in zip(stops[:-1], stops[1:]):
        if a <= v <= b:
            f = (v - a) / (b - a)
            return tuple(int(ca[i] + f * (cb[i] - ca[i])) for i in range(3))
    return stops[-1][1]


def get_fonts() -> tuple[ImageFont.ImageFont, ImageFont.ImageFont, ImageFont.ImageFont]:
    for name in ["Arial.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]:
        try:
            return ImageFont.truetype(name, 22), ImageFont.truetype(name, 15), ImageFont.truetype(name, 12)
        except Exception:
            pass
    f = ImageFont.load_default()
    return f, f, f


def draw_dual_landscape() -> None:
    X, Y, V, RE = potential_grid()
    Vn = (V - V.min()) / (V.max() - V.min())
    plot_w, plot_h = 700, 560
    img = Image.new("RGB", (980, 720), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((240, 24), "Dual-regime attractor landscape", fill=(17, 24, 39), font=title)
    canvas = Image.new("RGB", Vn.shape[::-1], "white")
    pix = canvas.load()
    for j in range(Vn.shape[0]):
        for i in range(Vn.shape[1]):
            pix[i, Vn.shape[0] - 1 - j] = color_ramp(float(Vn[j, i]))
    canvas = canvas.resize((plot_w, plot_h))
    img.paste(canvas, (80, 90))
    draw.rectangle([80, 90, 80 + plot_w, 90 + plot_h], outline=(30, 41, 59), width=2)
    draw.text((300, 665), "Fate_lock", fill=(30, 41, 59), font=font)
    draw.text((12, 300), "Embryonic activation", fill=(30, 41, 59), font=font)
    def px(fate, emb):
        return int(80 + fate * plot_w), int(90 + (1 - emb) * plot_h)
    for fate, emb, label, color in [
        (0.78, 0.16, "Adult basin A\nscar-forming repair", (184, 50, 44)),
        (0.22, 0.80, "Embryonic basin E\nblastema / pattern restoration", (44, 127, 184)),
    ]:
        x, y = px(fate, emb)
        draw.ellipse([x - 10, y - 10, x + 10, y + 10], fill=color, outline=(15, 23, 42), width=2)
        for k, line in enumerate(label.split("\n")):
            draw.text((x + 16, y - 18 + 18 * k), line, fill=(15, 23, 42), font=small)
    draw.text((805, 150), "Regime meaning", fill=(17, 24, 39), font=font)
    notes = [
        "A: inflammation-dependent",
        "partial plasticity",
        "high Fate_lock",
        "",
        "E: developmental re-entry",
        "blastema access",
        "high embryonic axis",
    ]
    for i, note in enumerate(notes):
        draw.text((805, 185 + i * 22), note, fill=(51, 65, 85), font=small)
    img.save(OUT / "dual_attractor_landscape.png")


def draw_phase_diagram(grid: pd.DataFrame) -> None:
    n = int(math.sqrt(len(grid)))
    img = Image.new("RGB", (900, 720), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((260, 24), "Phase diagram of R(U,S)", fill=(17, 24, 39), font=title)
    plot_w = plot_h = 560
    left, top = 90, 90
    piv = grid.pivot(index="adult_lock_pressure", columns="developmental_drive", values="R").sort_index(ascending=True)
    arr = piv.to_numpy()
    canvas = Image.new("RGB", arr.shape[::-1], "white")
    pix = canvas.load()
    for j in range(arr.shape[0]):
        for i in range(arr.shape[1]):
            r = float(arr[j, i])
            pix[i, arr.shape[0] - 1 - j] = (
                int(44 + r * (184 - 44)),
                int(127 + r * (50 - 127)),
                int(184 + r * (44 - 184)),
            )
    canvas = canvas.resize((plot_w, plot_h))
    img.paste(canvas, (left, top))
    draw.rectangle([left, top, left + plot_w, top + plot_h], outline=(30, 41, 59), width=2)
    boundary = []
    for lock, sub in grid.groupby("adult_lock_pressure", sort=True):
        sub = sub.sort_values("developmental_drive")
        devs = sub["developmental_drive"].to_numpy()
        rs = sub["R"].to_numpy()
        if not np.any(rs >= 0.5):
            continue
        idx = int(np.argmax(rs >= 0.5))
        if idx == 0:
            dev = devs[idx]
        else:
            r0, r1 = rs[idx - 1], rs[idx]
            d0, d1 = devs[idx - 1], devs[idx]
            frac = 0.0 if r1 == r0 else (0.5 - r0) / (r1 - r0)
            dev = d0 + frac * (d1 - d0)
        boundary.append((int(left + dev * plot_w), int(top + (1.0 - lock) * plot_h)))
    if len(boundary) > 1:
        draw.line(boundary, fill=(255, 255, 255), width=5)
        draw.line(boundary, fill=(15, 23, 42), width=2)
    draw.text((250, 665), "developmental drive: WNT + FGF + SHH + RA balance", fill=(30, 41, 59), font=small)
    draw.text((12, 330), "adult lock pressure: BMP + inflammation + Fate_lock", fill=(30, 41, 59), font=small)
    draw.text((690, 120), "R≈0 adult repair", fill=(44, 127, 184), font=font)
    draw.text((690, 160), "R≈1 embryonic re-entry", fill=(184, 50, 44), font=font)
    draw.line([(690, 200), (750, 200)], fill=(15, 23, 42), width=2)
    draw.text((760, 190), "R=0.5 boundary", fill=(30, 41, 59), font=small)
    draw.text((690, 220), "Boundary marks access", fill=(51, 65, 85), font=small)
    draw.text((690, 242), "to blastema-like basin", fill=(51, 65, 85), font=small)
    img.save(OUT / "phase_diagram_R_US.png")


def draw_trajectory_comparison(mammal: pd.DataFrame, salamander: pd.DataFrame) -> None:
    img = Image.new("RGB", (1200, 780), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title, font, small = get_fonts()
    draw.text((330, 24), "Mammal vs salamander regeneration trajectories", fill=(17, 24, 39), font=title)
    left, top, pw, ph = 80, 100, 540, 540
    draw.rectangle([left, top, left + pw, top + ph], outline=(30, 41, 59), width=2)
    draw.text((250, 660), "Fate_lock", fill=(30, 41, 59), font=font)
    draw.text((12, 350), "Embryonic activation", fill=(30, 41, 59), font=font)
    def pt(row):
        return int(left + row["Fate_lock"] * pw), int(top + (1 - row["Embryonic_program_activation"]) * ph)
    for fate, emb, label, color in [
        (0.78, 0.16, "A", (184, 50, 44)),
        (0.22, 0.80, "E", (44, 127, 184)),
    ]:
        x = int(left + fate * pw)
        y = int(top + (1 - emb) * ph)
        draw.ellipse([x - 12, y - 12, x + 12, y + 12], fill=color, outline=(15, 23, 42), width=2)
        draw.text((x + 15, y - 8), label, fill=(15, 23, 42), font=font)
    for df, color in [(mammal, (221, 139, 40)), (salamander, (44, 127, 184))]:
        points = [pt(row) for _, row in df.iterrows()]
        draw.line(points, fill=color, width=4)
        for p in points[::25]:
            draw.ellipse([p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3], fill=color)
    # Time traces
    trace_left, trace_top, tw, th = 720, 110, 390, 210
    for block, axis_name, ylab in [(0, "regime_R", "R"), (1, "Embryonic_program_activation", "Embryonic axis")]:
        y0 = trace_top + block * 270
        draw.rectangle([trace_left, y0, trace_left + tw, y0 + th], outline=(30, 41, 59), width=2)
        draw.text((trace_left, y0 - 28), ylab, fill=(30, 41, 59), font=font)
        for df, color in [(mammal, (221, 139, 40)), (salamander, (44, 127, 184))]:
            vals = df[axis_name].to_numpy()
            ts = df["time"].to_numpy()
            pts = [
                (
                    int(trace_left + (t - ts.min()) / (ts.max() - ts.min()) * tw),
                    int(y0 + th - v * th),
                )
                for t, v in zip(ts, vals)
            ]
            draw.line(pts, fill=color, width=3)
    draw.rectangle([735, 660, 755, 680], fill=(221, 139, 40))
    draw.text((765, 658), "mammalian inflammatory repair", fill=(30, 41, 59), font=small)
    draw.rectangle([735, 690, 755, 710], fill=(44, 127, 184))
    draw.text((765, 688), "salamander embryonic reactivation", fill=(30, 41, 59), font=small)
    img.save(OUT / "mammal_vs_salamander_trajectory_comparison.png")


def build_regime_grid() -> pd.DataFrame:
    rows = []
    developmental_vals = np.linspace(0, 1, 31)
    adult_lock_vals = np.linspace(0, 1, 31)
    for dev in developmental_vals:
        for lock in adult_lock_vals:
            U = {
                "WNT": dev,
                "FGF": dev,
                "SHH": dev,
                "RA_balance": dev,
                "BMP": lock,
                "NOTCH": 0.55,
                "inflammation": lock,
            }
            S = np.array([0.35 + 0.25 * dev, 0.40, 0.15 + 0.65 * lock, 0.10 + 0.55 * dev])
            R = regime_switch(U, S)
            rows.append(
                {
                    "developmental_drive": round(float(dev), 4),
                    "adult_lock_pressure": round(float(lock), 4),
                    "Stemness": S[0],
                    "Transitional": S[1],
                    "Fate_lock": S[2],
                    "Embryonic_program_activation": S[3],
                    "R": R,
                    "dominant_regime": "embryonic_reactivation_E" if R >= 0.5 else "adult_repair_A",
                }
            )
    return pd.DataFrame(rows)


def write_model_docs(mammal: pd.DataFrame, salamander: pd.DataFrame) -> None:
    mammal_final = mammal.iloc[-1]
    salamander_final = salamander.iloc[-1]
    md = f"""# 胚胎程序再激活动力学

## 核心区分

当前模型将“再生”拆分为两个不同吸引子机制，而不是把所有再生都解释成炎症驱动的命运恢复：

- **成人修复机制 A**：对应哺乳动物炎症依赖性组织修复。其特征是高 `Fate_lock`、短暂 `Transitional` 可塑性、低 `Embryonic_program_activation`，并倾向于瘢痕形成或不完全结构恢复。
- **胚胎再激活机制 E**：对应蝾螈样发育程序重入。其特征是高 `Embryonic_program_activation`、WNT/FGF/SHH 与 RA 平衡驱动的发育信号、blastema 可达性，以及完整模式恢复潜力。

## 状态空间

```text
S = [Stemness, Transitional, Fate_lock, Embryonic_program_activation]
```

`Embryonic_program_activation` 是独立吸引子轴，不等同于炎症诱导的局部可塑性。

## 机制切换

```text
R(U,S) in [0,1]
R ~= 0: 成人修复盆地 A 主导
R ~= 1: 胚胎再激活盆地 E 主导
```

切换函数随 WNT、FGF、SHH 和 RA 平衡驱动增强而升高，随 BMP、炎症压力和 `Fate_lock` 增强而降低。

## 蝾螈特异机制

blastema 形成被表示为对胚胎再激活盆地 E 的瞬时可达，而不是炎症恢复的加强版：

```text
Embryonic_program_activation = f(WNT, FGF, SHH, RA balance)
```

损伤后可以存在炎症，但蝾螈真性表观再生的定义性机制是发育状态重入与位置信息恢复。

## 仿真摘要

哺乳动物成人修复模拟终态：

- R = {mammal_final['regime_R']:.3f}
- Fate_lock = {mammal_final['Fate_lock']:.3f}
- Embryonic_program_activation = {mammal_final['Embryonic_program_activation']:.3f}

蝾螈胚胎再激活模拟终态：

- R = {salamander_final['regime_R']:.3f}
- Fate_lock = {salamander_final['Fate_lock']:.3f}
- Embryonic_program_activation = {salamander_final['Embryonic_program_activation']:.3f}

## 证据边界

这些结果完成的是多机制吸引子架构与机制约束仿真。参数值是机制约束下的示意参数，不是从哺乳动物与蝾螈联合实测数据中拟合得到的物种特异动力学常数。
"""
    (OUT / "embryonic_reactivation_dynamics.md").write_text(md, encoding="utf-8")

    eq = """# 更新后的多机制发育动力学方程

状态向量为：

```text
S = [Stemness, Transitional, Fate_lock, Embryonic_program_activation]
```

系统包含两个不可合并的调控机制：

```text
W_total(U,S) = (1 - R(U,S)) W_A(U) + R(U,S) W_E(U)
```

动力学为：

```text
dS/dt = W_total(U,S) · S + B_total(U,S) + feedback_regime(S,U) + xi(S)
```

其中：

- `W_A(U)` 表示哺乳动物成人修复机制：BMP / p53 / 炎症 / 衰老偏置动力学。
- `W_E(U)` 表示蝾螈胚胎再激活机制：WNT / FGF / SHH / HOX / RA 平衡驱动的发育程序重入。
- `R(U,S)` 是机制切换变量；`R≈0` 表示成人修复，`R≈1` 表示胚胎再激活。
- `xi(S)` 表示状态依赖的生物噪声，只调制转移概率，不消除两个机制之间的结构差异。

成人哺乳动物修复和蝾螈真性表观再生不是同一过程的两个标签，而是同一个切换动力学系统中的两个不同吸引子机制。
"""
    (OUT / "multi_regime_dynamical_system_equation.md").write_text(eq, encoding="utf-8")


def main() -> int:
    mammal_U = {"WNT": 0.25, "FGF": 0.18, "SHH": 0.12, "RA_balance": 0.22, "BMP": 0.78, "NOTCH": 0.62, "inflammation": 0.88}
    salamander_U = {"WNT": 0.78, "FGF": 0.84, "SHH": 0.72, "RA_balance": 0.76, "BMP": 0.32, "NOTCH": 0.58, "inflammation": 0.38}
    S0 = np.array([0.28, 0.34, 0.62, 0.08])
    mammal = simulate(mammal_U, S0, seed=11)
    salamander = simulate(salamander_U, S0, seed=17)
    mammal.insert(1, "system", "mammalian_adult_repair")
    salamander.insert(1, "system", "salamander_embryonic_reactivation")
    traj = pd.concat([mammal, salamander], ignore_index=True)
    traj.to_csv(OUT / "mammal_vs_salamander_trajectory_comparison.tsv", sep="\t", index=False)

    grid = build_regime_grid()
    grid.to_csv(OUT / "regime_switching_function.tsv", sep="\t", index=False)
    grid.to_csv(OUT / "phase_diagram_R_US.tsv", sep="\t", index=False)

    draw_dual_landscape()
    draw_phase_diagram(grid)
    draw_trajectory_comparison(mammal, salamander)
    write_model_docs(mammal, salamander)
    print("multi-regime attractor framework complete")
    print(f"mammal_final_R={mammal.iloc[-1]['regime_R']:.4f}")
    print(f"salamander_final_R={salamander.iloc[-1]['regime_R']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
