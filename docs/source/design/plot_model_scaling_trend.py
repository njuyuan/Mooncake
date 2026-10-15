"""Regenerate the Qwen / Kimi / DeepSeek parameter and expert-count figure."""

from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D

font_manager.fontManager.addfont("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc")
plt.rcParams["font.family"] = "WenQuanYi Micro Hei"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42


def d(s):
    return datetime.strptime(s, "%Y-%m-%d")


def mag(params):
    return f"{params:g}T" if params >= 1 else f"{round(params * 1000):g}B"


# label, date, params (T), routed experts, label anchor (date, y), ha, va
qwen = "#1f4e79"
deepseek = "#c05621"
kimi = "#276749"
ink = "#1c1c1c"
muted = "#5e584f"

series = [
    (
        qwen,
        [
            (
                "Qwen-7B",
                d("2023-08-03"),
                0.007,
                0,
                d("2023-09-20"),
                0.011,
                "left",
                "bottom",
            ),
            (
                "Qwen-72B",
                d("2023-11-30"),
                0.072,
                0,
                d("2024-01-20"),
                0.115,
                "left",
                "bottom",
            ),
            (
                "Qwen2.5-72B",
                d("2024-09-19"),
                0.072,
                0,
                d("2024-10-15"),
                0.038,
                "left",
                "top",
            ),
            (
                "Qwen3-235B",
                d("2025-04-29"),
                0.235,
                128,
                d("2025-06-01"),
                0.145,
                "left",
                "top",
            ),
            (
                "Qwen3.5-397B",
                d("2026-02-16"),
                0.397,
                512,
                d("2026-05-01"),
                0.25,
                "left",
                "center",
            ),
            (
                "Qwen3.8-2.4T",
                d("2026-08-12"),
                2.4,
                512,
                d("2027-01-20"),
                1.55,
                "left",
                "center",
            ),
        ],
    ),
    (
        deepseek,
        [
            (
                "DeepSeek-67B",
                d("2023-11-29"),
                0.067,
                0,
                d("2024-01-15"),
                0.028,
                "left",
                "top",
            ),
            (
                "DeepSeek-V2",
                d("2024-05-06"),
                0.236,
                160,
                d("2024-06-15"),
                0.42,
                "left",
                "bottom",
            ),
            (
                "DeepSeek-V3",
                d("2024-12-26"),
                0.671,
                256,
                d("2024-09-01"),
                0.95,
                "left",
                "bottom",
            ),
            (
                "DeepSeek-V3.2",
                d("2025-12-01"),
                0.671,
                256,
                d("2026-03-01"),
                0.52,
                "left",
                "center",
            ),
            (
                "DeepSeek-V4-Pro",
                d("2026-04-24"),
                1.6,
                384,
                d("2027-01-20"),
                1.05,
                "left",
                "center",
            ),
        ],
    ),
    (
        kimi,
        [
            (
                "Kimi K2",
                d("2025-07-11"),
                1.04,
                384,
                d("2025-08-15"),
                1.7,
                "left",
                "bottom",
            ),
            (
                "Kimi K2.5",
                d("2026-01-27"),
                1.0,
                384,
                d("2026-04-15"),
                0.78,
                "left",
                "center",
            ),
            (
                "Kimi K3",
                d("2026-07-16"),
                2.78,
                896,
                d("2026-09-15"),
                4.6,
                "left",
                "bottom",
            ),
        ],
    ),
]


def msize(experts):
    return 28 if experts <= 0 else 36 + experts * 0.36


fig, ax = plt.subplots(figsize=(14.4, 8.15), dpi=170)
fig.patch.set_facecolor("white")
ax.set_facecolor("white")
ax.axvspan(d("2027-01-01"), d("2030-11-01"), color="#f4f1ea", zorder=0)

for color, pts in series:
    ax.plot(
        [p[1] for p in pts],
        [p[2] for p in pts],
        color=color,
        lw=1.9,
        zorder=2,
        solid_capstyle="round",
    )
    for label, dt, params, experts, lx, ly, ha, va in pts:
        ax.scatter(
            [dt],
            [params],
            s=msize(experts),
            zorder=3,
            facecolors="white" if experts == 0 else color,
            edgecolors=color,
            linewidths=1.35,
        )
        expert_txt = "稠密" if experts == 0 else f"{experts} experts"
        ax.annotate(
            f"{label}   {mag(params)} · {expert_txt}",
            xy=(dt, params),
            xytext=(lx, ly),
            textcoords="data",
            fontsize=8,
            color=ink,
            ha=ha,
            va=va,
            zorder=5,
            arrowprops={
                "arrowstyle": "-",
                "color": "#9a9388",
                "lw": 0.55,
                "shrinkA": 0,
                "shrinkB": 4,
            },
        )

ax.plot(
    [d("2026-07-16"), d("2028-07-01"), d("2030-07-01")],
    [2.78, 10, 100],
    color=muted,
    ls=(0, (4, 2.5)),
    lw=1.35,
    zorder=2,
)
for dt, params, text, lx, ly in [
    (d("2028-07-01"), 10, "10T 情景\n2–3K experts", d("2028-08-15"), 16),
    (d("2030-07-01"), 100, "100T 情景\n10K experts", d("2029-08-01"), 55),
]:
    ax.scatter(
        [dt],
        [params],
        s=160,
        marker="D",
        facecolors="white",
        edgecolors=muted,
        linewidths=1.55,
        zorder=4,
    )
    ax.annotate(
        text,
        xy=(dt, params),
        xytext=(lx, ly),
        textcoords="data",
        fontsize=9,
        color="#3c372f",
        ha="left",
        va="center",
        linespacing=1.3,
        zorder=5,
        arrowprops={
            "arrowstyle": "-",
            "color": "#9a9388",
            "lw": 0.55,
            "shrinkA": 0,
            "shrinkB": 6,
        },
    )

ax.set_yscale("log")
ax.set_ylim(0.0045, 220)
ax.set_xlim(d("2023-03-01"), d("2030-11-01"))
ax.yaxis.set_major_formatter(
    plt.FuncFormatter(lambda v, _p: f"{v:g}T" if v >= 1 else f"{v * 1000:g}B")
)
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax.set_xlabel("发布时间 / 架构情景年份", fontsize=12, labelpad=8)
ax.set_ylabel("模型总参数量（对数尺度）", fontsize=12, labelpad=8)
ax.set_title(
    "Qwen、DeepSeek、Kimi：总参数量与每层 routed expert 数",
    fontsize=15,
    loc="left",
    pad=12,
)
ax.tick_params(labelsize=10, colors="#333")
ax.grid(True, which="major", color="#e7e2d9", lw=0.8, zorder=0)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_color("#b7b1a6")
ax.spines["bottom"].set_color("#b7b1a6")
ax.text(
    d("2027-02-20"), 32, "架构情景区，不是发布日期预测", color="#6d655b", fontsize=10
)

handles = [
    Line2D([0], [0], color=qwen, lw=2.2, label="Qwen"),
    Line2D([0], [0], color=deepseek, lw=2.2, label="DeepSeek"),
    Line2D([0], [0], color=kimi, lw=2.2, label="Kimi"),
    Line2D([0], [0], color=muted, lw=1.4, ls=(0, (4, 2.5)), label="架构情景"),
    Line2D(
        [0],
        [0],
        marker="o",
        color="white",
        markeredgecolor="#444",
        markeredgewidth=1.2,
        markersize=5.5,
        lw=0,
        label="稠密",
    ),
    Line2D(
        [0], [0], marker="o", color="#777", markersize=8, lw=0, label="约 150 experts"
    ),
    Line2D(
        [0], [0], marker="o", color="#777", markersize=12, lw=0, label="约 500 experts"
    ),
    Line2D(
        [0], [0], marker="o", color="#777", markersize=16, lw=0, label="896 experts"
    ),
]
ax.legend(
    handles=handles,
    loc="upper left",
    frameon=False,
    fontsize=8.6,
    ncol=2,
    labelspacing=0.4,
)

fig.subplots_adjust(left=0.07, right=0.985, top=0.90, bottom=0.16)
fig.text(
    0.07,
    0.025,
    "来源：Qwen、DeepSeek、Moonshot 官方技术报告、模型卡与 config.json（2023-08 至 2026-08）。圆面积表示每个 MoE 层的 routed expert 数，不含 shared expert。\n"
    "10T 对应 2–3K experts、100T 对应 10K experts，是“保持细粒度专家，并允许层数和单 expert 宽度增加”的架构情景；不是幂律拟合，也不是发布时间预测。",
    fontsize=8,
    color="#4e4942",
    ha="left",
    va="bottom",
)
root = Path(__file__).resolve().parents[1] / "image"
png = root / "qwen-kimi-deepseek-scaling.png"
pdf = root / "qwen-kimi-deepseek-scaling.pdf"
fig.savefig(png, dpi=170)
fig.savefig(pdf)
print("wrote")
