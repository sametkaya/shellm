import json, collections, math, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family": "DejaVu Sans", "pdf.fonttype": 42, "font.size": 8.5,
                     "axes.edgecolor": "#8a8984", "axes.linewidth": 0.6, "xtick.color": "#52514e",
                     "ytick.color": "#52514e", "axes.labelcolor": "#0b0b0b"})
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
R = os.path.join(ROOT, "tests", "results")
G = os.path.join(ROOT, "tests", "guard")
OUT = os.path.join(HERE, "output", "journal")
os.makedirs(OUT, exist_ok=True)
A = json.load(open(os.path.join(OUT, "analysis.json")))
models = [("Gemini", "Gemini 3.5 Flash-Lite"), ("Claude", "Claude Haiku 4.5"),
          ("GPT", "GPT-5.4 mini"), ("Qwen-local", "Qwen2.5-Coder 1.5B (local)")]
sets = [("A", "A: mistyped commands"), ("B", "B: Turkish requests"), ("E", "E: English requests")]

# ---------------- Figure: accuracy, faceted dot plot with 95% CIs
fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.35), sharey=True)
for ax, (s, title) in zip(axes, sets):
    for i, (key, lab) in enumerate(models):
        y = len(models) - 1 - i
        for cond, color, filled, dy in (("V1", ORANGE, False, 0.14), ("C1K1", BLUE, True, -0.14)):
            a = A["acc"]["%s|%s|%s" % (key, cond, s)]
            lo, hi = a["ci"]
            ax.plot([lo, hi], [y + dy, y + dy], color=color, lw=1.4, solid_capstyle="round", zorder=2)
            ax.scatter([a["pct"]], [y + dy], s=26, zorder=3, edgecolor=color, linewidth=1.4,
                       facecolor=color if filled else "white")
    if s == "A":
        ax.axvline(90, color=INK2, lw=0.8, ls=(0, (3, 2)), zorder=1)
        ax.text(89, -0.5, "zsh CORRECT (90%)", ha="right", va="center", fontsize=7, color=INK2)
    ax.set_title(title, fontsize=8.5, loc="left", color=INK)
    ax.set_xlim(0, 100); ax.set_xticks([0, 25, 50, 75, 100])
    ax.grid(axis="x", color=GRID, lw=0.6); ax.set_axisbelow(True)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("% of tasks solved", fontsize=8)
axes[0].set_yticks(range(len(models)))
axes[0].set_yticklabels([lab for _, lab in models][::-1], fontsize=8)
axes[0].set_ylim(-0.75, 3.45)
h1 = plt.Line2D([], [], marker="o", color=BLUE, markerfacecolor=BLUE, lw=1.4, label="SheLLM prompt")
h2 = plt.Line2D([], [], marker="o", color=ORANGE, markerfacecolor="white", lw=1.4, label="one-sentence baseline prompt")
fig.legend(handles=[h1, h2], loc="lower center", ncol=2, frameon=False, fontsize=8, bbox_to_anchor=(0.55, -0.03))
plt.subplots_adjust(left=0.235, right=0.985, top=0.88, bottom=0.3, wspace=0.12)
plt.savefig(os.path.join(OUT, "fig_accuracy.pdf")); plt.savefig(os.path.join(OUT, "fig_accuracy.png"), dpi=200)

# ---------------- Figure: latency ECDF (SheLLM prompt, all repetitions)
resp = {}
for l in open(R + "/llm2_responses.jsonl"):
    r = json.loads(l)
    k = (r["provider"], r["model"], r["id"], r["cond"], r["rep"])
    if k not in resp or r["status"] == "OK":
        resp[k] = r
prov = {"Gemini": "gemini", "Claude": "anthropic", "GPT": "openai", "Qwen-local": "local"}
colors = {"Gemini": BLUE, "Claude": ORANGE, "GPT": AQUA, "Qwen-local": YELLOW}
fig, ax = plt.subplots(figsize=(4.6, 2.4))
for key, lab in models:
    T = sorted(r["attempts"][-1]["t"] for k, r in resp.items()
               if k[0] == prov[key] and k[3] == "C1K1" and r["status"] == "OK" and r["attempts"])
    n = len(T)
    xs = T; ys = [(i + 1) / n * 100 for i in range(n)]
    ax.step(xs, ys, where="post", color=colors[key], lw=1.6)
    # direct labels at distinct percentiles so they do not collide
    target, dx = {"Claude": (88, -6), "Gemini": (62, 6), "GPT": (35, 6), "Qwen-local": (20, 6)}[key]
    xv = T[min(n - 1, int(target / 100 * n))]
    ax.annotate(lab.replace(" (local)", ", local"), xy=(xv, target), xytext=(dx, 0), textcoords="offset points",
                fontsize=7.2, color=INK, va="center", ha="right" if dx < 0 else "left")
ax.axvline(3, color=INK2, lw=0.8, ls=(0, (3, 2)))
ax.text(3.1, 3, "3 s", fontsize=7, color=INK2)
ax.set_xscale("log"); ax.set_xlim(0.3, 25)
ax.set_xticks([0.3, 0.5, 1, 2, 3, 5, 10, 20]); ax.set_xticklabels(["0.3", "0.5", "1", "2", "3", "5", "10", "20"])
ax.set_ylim(0, 101)
ax.set_xlabel("response time per suggestion (s, log scale)", fontsize=8)
ax.set_ylabel("% of requests", fontsize=8)
ax.grid(color=GRID, lw=0.6); ax.set_axisbelow(True)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
plt.tight_layout()
plt.savefig(os.path.join(OUT, "fig_latency.pdf")); plt.savefig(os.path.join(OUT, "fig_latency.png"), dpi=200)
print("ok")
