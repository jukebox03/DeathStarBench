import matplotlib.pyplot as plt

# Experiment 2: Frontend Parallelism Analysis
# Setup: Frontend/User & Sidecars fixed 4 cores. User Replica = 1.
# Variable: Frontend Replicas (1, 2, 4, 8)
data = {
    "Frontend Replica = 1": {
        "rate": [15000, 16000, 17000, 18000, 19000, 20000],
        "rps":  [14663.43, 15651.97, 16443.50, 16220.42, 16121.96, 16121.02],
        "p50":  [47.07, 57.63, 303.10, 1500.0, 2560.0, 3350.0],
        "p99":  [100.93, 116.54, 1660.0, 4710.0, 6300.0, 7410.0],
        "note": "Limit ~16.4k RPS\n(SC CPU ~38%)"
    },
    "Frontend Replica = 2": {
        "rate": [27000, 28000, 29000, 30000, 31000, 32000],
        "rps":  [26571.62, 27668.88, 28580.06, 29481.31, 29585.29, 29433.96],
        "p50":  [21.01, 38.88, 28.96, 32.90, 591.36, 1190.0],
        "p99":  [57.47, 88.13, 63.26, 398.08, 2410.0, 3630.0],
        "note": "Limit ~29.5k RPS\n(SC CPU ~67%)"
    },
    "Frontend Replica = 4": {
        "rate": [42000, 43000, 44000, 45000, 46000, 47000, 48000],
        "rps":  [41403.59, 41750.54, 42453.71, 42623.54, 43428.51, 43394.63, 43689.54],
        "p50":  [55.65, 106.88, 160.26, 196.86, 230.53, 633.34, 975.36],
        "p99":  [743.42, 3630.0, 4060.0, 5360.0, 6190.0, 6160.0, 6570.0],
        "note": "Limit ~45k RPS\n(SC CPU ~99%)"
    },
    "Frontend Replica = 8": {
        "rate": [35000, 38000, 41000, 44000, 47000, 50000],
        "rps":  [34497.92, 37568.72, 40423.81, 42514.78, 43371.28, 44372.15],
        "p50":  [17.66, 22.19, 43.49, 142.08, 311.04, 1050.0],
        "p99":  [41.95, 67.46, 294.91, 5300.0, 7280.0, 8560.0],
        "note": "Limit ~45k RPS\n(SC CPU ~100%)\nSaturated"
    },
}

plt.figure(figsize=(10, 7))

# Offsets for annotation positioning
offsets = {
    "Frontend Replica = 1": (10, -20),
    "Frontend Replica = 2": (10, -20),
    "Frontend Replica = 4": (-90, 10),
    "Frontend Replica = 8": (10, -40),
}

for config, d in data.items():
    x = d["rate"]
    y = d["rps"]
    line, = plt.plot(x, y, marker="o", label=config)

    # Find the index of the maximum achieved RPS
    i = max(range(len(y)), key=lambda k: y[k])
    
    # Use the specific offset logic
    dx, dy = offsets.get(config, (10, -10))
    
    # Annotation style
    plt.annotate(
        d["note"],
        xy=(x[i], y[i]),
        xytext=(dx, dy),
        textcoords="offset points",
        fontsize=8,
        color=line.get_color(),
        arrowprops=dict(arrowstyle="->", color=line.get_color())
    )

# Diagonal line (Ideal)
ax = plt.gca()
lo = min(ax.get_xlim()[0], ax.get_ylim()[0])
hi = max(ax.get_xlim()[1], ax.get_ylim()[1])
plt.plot([lo, hi], [lo, hi], linestyle="--", linewidth=1, alpha=0.35, zorder=0, color="gray", label="Ideal")

# Add Insight Text Box
info_text = (
    "Insight: Frontend Parallelism\n"
    "• Rep 1~4: Linear growth\n"
    "• Rep 8: Diminishing returns\n"
    "  (Downstream bottleneck likely\n   at its Sidecar)"
)
plt.text(0.02, 0.75, info_text, transform=ax.transAxes, fontsize=9,
         verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.2))

plt.xlabel("Target rate (RPS)")
plt.ylabel("Achieved throughput (RPS)")
plt.title("Frontend Parallelism: Throughput vs Rate\n(Frontend/User & Sidecars fixed 4 cores, User Replica 1)")
plt.grid(True, alpha=0.3)
plt.legend(loc="upper left")
plt.tight_layout()
plt.savefig("istio_throughput_vs_rate_frontend_parallelism.png", dpi=200)

print("Saved: istio_throughput_vs_rate_frontend_parallelism.png")