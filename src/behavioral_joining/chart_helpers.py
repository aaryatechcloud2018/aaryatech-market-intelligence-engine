"""chart_helpers.py -- shared matplotlib helpers for Power BI-style client PDFs."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

NAVY = "#1F3864"
GOLD = "#9C6B1F"
RED = "#A6231A"
GREEN = "#2E7D32"
GRAY = "#6B6B6B"
LIGHT = "#EFF3FA"

plt.rcParams["font.family"] = "DejaVu Sans"


def new_page(figsize=(11, 8.5)):
    return plt.figure(figsize=figsize)


def title_block(fig, title, subtitle=None, demo_note=True):
    fig.text(0.06, 0.94, title, fontsize=20, fontweight="bold", color=NAVY)
    if subtitle:
        fig.text(0.06, 0.905, subtitle, fontsize=13, color=GOLD, fontweight="bold")
    if demo_note:
        fig.text(0.06, 0.875, "Demonstration dataset -- not real client historical data.",
                  fontsize=9, style="italic", color=RED)


def kpi_cards(fig, cards, y=0.78, height=0.10):
    n = len(cards)
    width = 0.9 / n
    for i, (label, value) in enumerate(cards):
        x = 0.06 + i * (width + 0.01)
        ax = fig.add_axes([x, y, width, height])
        ax.set_facecolor(LIGHT)
        ax.set_xticks([]); ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color("#C6D2EA")
        value_str = str(value)
        fsize = 20 if len(value_str) <= 6 else (15 if len(value_str) <= 14 else 12)
        ax.text(0.5, 0.62, value_str, ha="center", va="center", fontsize=fsize, fontweight="bold", color=NAVY, transform=ax.transAxes)
        ax.text(0.5, 0.22, label, ha="center", va="center", fontsize=9, color="#555555", transform=ax.transAxes, wrap=True)


def funnel_chart(ax, stages, entering, xlabel=True):
    y_pos = np.arange(len(stages))
    ax.barh(y_pos, entering, color=NAVY, height=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(stages, fontsize=9)
    ax.invert_yaxis()
    if xlabel:
        ax.set_xlabel("Applications Entering Stage", fontsize=9)
    for i, v in enumerate(entering):
        ax.text(v + max(entering) * 0.01, i, str(v), va="center", fontsize=8)
    ax.set_title("Candidate Funnel by Stage", fontsize=11, fontweight="bold", color=NAVY)


def dropoff_chart(ax, stages, dropoff_rate, xlabel=True):
    y_pos = np.arange(len(stages))
    colors = [RED if r >= 0.3 else (GOLD if r >= 0.1 else GREEN) for r in dropoff_rate]
    ax.barh(y_pos, [r * 100 for r in dropoff_rate], color=colors, height=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(stages, fontsize=9)
    ax.invert_yaxis()
    if xlabel:
        ax.set_xlabel("Drop-off %", fontsize=9)
    for i, v in enumerate(dropoff_rate):
        ax.text(v * 100 + 1, i, f"{v:.0%}", va="center", fontsize=8)
    ax.set_title("Drop-off % by Stage", fontsize=11, fontweight="bold", color=NAVY)


def heatmap(ax, matrix, row_labels, col_labels, title, cmap="YlOrRd", fmt="{:.0%}"):
    im = ax.imshow(matrix, cmap=cmap, aspect="auto")
    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_xticklabels(col_labels, fontsize=7, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=8)
    ax.set_title(title, fontsize=11, fontweight="bold", color=NAVY)
    vmax = np.nanmax(matrix) if matrix.size else 1
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            v = matrix[i, j]
            if v == v and v > 0:
                ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=6,
                         color="white" if v > vmax * 0.5 else "black")
    return im


def bar_chart(ax, labels, values, title, color=NAVY, horizontal=True, fmt="{:.0f}"):
    if horizontal:
        y_pos = np.arange(len(labels))
        ax.barh(y_pos, values, color=color, height=0.6)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=8)
        ax.invert_yaxis()
        mx = max(values) if len(values) and max(values) else 1
        for i, v in enumerate(values):
            ax.text(v + mx * 0.01, i, fmt.format(v), va="center", fontsize=7)
    else:
        x_pos = np.arange(len(labels))
        ax.bar(x_pos, values, color=color)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(labels, fontsize=8, rotation=30, ha="right")
    ax.set_title(title, fontsize=11, fontweight="bold", color=NAVY)


def quadrant_chart(ax, x, y, labels, title, xlabel, ylabel, quad_labels):
    ax.scatter(x, y, s=140, color=NAVY, zorder=3)
    for xi, yi, l in zip(x, y, labels):
        ax.annotate(l, (xi, yi), fontsize=7, xytext=(5, 5), textcoords="offset points")
    ax.axvline(0.5, color="gray", linestyle="--", linewidth=1)
    ax.axhline(0.5, color="gray", linestyle="--", linewidth=1)
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(title, fontsize=11, fontweight="bold", color=NAVY)
    positions = [(0.02, 0.98), (0.98, 0.98), (0.02, 0.02), (0.98, 0.02)]
    for (px, py), qt in zip(positions, quad_labels):
        ha = "left" if px < 0.5 else "right"
        va = "top" if py > 0.5 else "bottom"
        ax.text(px, py, qt, transform=ax.transAxes, fontsize=7, color=GRAY, ha=ha, va=va, style="italic")


def evidence_badge(ax, grade):
    colors = {"SUPPORTED": GREEN, "WEAK": GOLD, "INCONCLUSIVE": GRAY, "CONTRADICTED": RED}
    color = colors.get(grade, GRAY)
    ax.set_facecolor(color)
    ax.set_xticks([]); ax.set_yticks([])
    ax.text(0.5, 0.5, grade, ha="center", va="center", fontsize=13, fontweight="bold", color="white", transform=ax.transAxes)


def note_text(fig, text, y=0.05, color=GRAY, fontsize=8):
    fig.text(0.06, y, text, fontsize=fontsize, color=color, wrap=True, style="italic")


def footer(fig, page_label):
    fig.text(0.94, 0.02, page_label, fontsize=8, color="#999999", ha="right")
