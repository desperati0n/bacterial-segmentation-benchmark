"""Rebuild the full-set agreement chart from saved per-image results.

This script does not rerun inference. The reference masks include earlier
processing output, so the chart describes agreement rather than GT accuracy.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DETAIL = ROOT / "results" / "detailed" / "全量已处理图_参考mask一致性逐图.csv"
FIGURE = ROOT / "figures" / "metrics" / "全量结果总览_2902张.png"
SUMMARY = ROOT / "results" / "detailed" / "全量结果总览_按模态与权重.csv"

MODEL_ORDER = {
    "Brightfield/Phase": [
        "Cellpose-SAM_cpsam_v2",
        "MicroSAM_DeepBacs",
        "Omnipose_bact_phase_omnitorch_0",
    ],
    "Fluorescence": [
        "Cellpose-SAM_cpsam_v2",
        "MicroSAM_DeepBacs",
        "Omnipose_bact_fluor_omnitorch_0",
    ],
}
MODEL_LABELS = ["Cellpose-SAM", "MicroSAM\nDeepBacs", "Omnipose"]
COLORS = ["#3769B2", "#8156AE", "#D98428"]
METRICS = [("fg_dice", "前景 Dice"), ("boundary_f1", "Boundary F1")]


def load_results() -> pd.DataFrame:
    data = pd.read_csv(DETAIL, encoding="utf-8-sig")
    needed = {"sample_id", "modality", "model", "source_group", "fg_dice", "boundary_f1"}
    missing = needed.difference(data.columns)
    if missing:
        raise ValueError(f"Missing columns in {DETAIL.name}: {sorted(missing)}")
    if data.duplicated(["sample_id", "modality", "model"]).any():
        raise ValueError("Duplicate sample/modality/model rows in full-set results")
    if data[["fg_dice", "boundary_f1"]].isna().any().any():
        raise ValueError("Missing agreement values in full-set results")
    for modality, models in MODEL_ORDER.items():
        subset = data[data["modality"] == modality]
        expected_ids = set(subset["sample_id"])
        if not expected_ids or set(subset["model"]) != set(models):
            raise ValueError(f"Unexpected model coverage for {modality}")
        for model in models:
            ids = set(subset.loc[subset["model"] == model, "sample_id"])
            if ids != expected_ids:
                raise ValueError(f"Incomplete output for {modality} / {model}")
    if set(data["modality"]) != set(MODEL_ORDER):
        raise ValueError("Unexpected modality in full-set results")
    return data


def summarize(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for modality, models in MODEL_ORDER.items():
        for model in models:
            part = data[(data["modality"] == modality) & (data["model"] == model)]
            group_means = part.groupby("source_group")[["fg_dice", "boundary_f1"]].mean()
            rows.append({
                "modality": modality,
                "model": model,
                "n_images": part["sample_id"].nunique(),
                "n_source_groups": len(group_means),
                "image_mean_fg_dice": part["fg_dice"].mean(),
                "source_equal_fg_dice": group_means["fg_dice"].mean(),
                "image_mean_boundary_f1": part["boundary_f1"].mean(),
                "source_equal_boundary_f1": group_means["boundary_f1"].mean(),
            })
    return pd.DataFrame(rows)


def plot(summary: pd.DataFrame, n_images: int, n_outputs: int) -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "Noto Sans CJK SC", "WenQuanYi Micro Hei", "SimHei", "Arial"],
        "axes.unicode_minus": False,
        "savefig.dpi": 220,
    })
    fig, axes = plt.subplots(2, 2, figsize=(13.8, 8.8), layout="constrained")
    fig.suptitle(f"全量已处理图：{n_images:,} 张原图 · {n_outputs:,} 份模型结果",
                 fontsize=18, weight="bold")
    for col, (modality, models) in enumerate(MODEL_ORDER.items()):
        part = summary.set_index(["modality", "model"]).loc[[(modality, m) for m in models]]
        n = int(part["n_images"].iloc[0])
        groups = int(part["n_source_groups"].iloc[0])
        for row, (metric, label) in enumerate(METRICS):
            ax = axes[row, col]
            x = np.arange(len(models))
            weighted = part[f"image_mean_{metric}"].to_numpy()
            macro = part[f"source_equal_{metric}"].to_numpy()
            for i, color in enumerate(COLORS):
                ax.bar(x[i] - 0.17, weighted[i], width=0.32, color=color,
                       label="逐图平均" if i == 0 else None)
                ax.bar(x[i] + 0.17, macro[i], width=0.32, color="white",
                       edgecolor=color, hatch="///", linewidth=1.4,
                       label="资料目录等权平均" if i == 0 else None)
                ax.text(x[i] - 0.17, weighted[i] + 0.012, f"{weighted[i]:.3f}",
                        ha="center", va="bottom", fontsize=8)
                ax.text(x[i] + 0.17, macro[i] + 0.012, f"{macro[i]:.3f}",
                        ha="center", va="bottom", fontsize=8)
            ax.set_xticks(x, MODEL_LABELS)
            ax.set_ylim(0, max(0.12, float(max(weighted.max(), macro.max())) * 1.22))
            ax.set_ylabel(label)
            ax.set_title(f"{'明场 / 相差' if col == 0 else '荧光'} · {n:,} 张 · {groups} 个资料目录")
            ax.grid(axis="y", alpha=0.2)
            ax.set_axisbelow(True)
            ax.spines[["top", "right"]].set_visible(False)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.005), frameon=False)
    fig.text(0.5, -0.035,
             "参考对象含历史算法和既有处理 mask；数值表示与参考 mask 的一致性，不是人工真值准确率。",
             ha="center", fontsize=10, color="#4B5563")
    fig.savefig(FIGURE, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    data = load_results()
    summary = summarize(data)
    summary.to_csv(SUMMARY, index=False, encoding="utf-8-sig")
    plot(summary, data["sample_id"].nunique(), len(data))
    print(f"Saved {FIGURE} and {SUMMARY}; {data['sample_id'].nunique()} images, {len(data)} rows")


if __name__ == "__main__":
    main()
