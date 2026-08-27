import matplotlib.pyplot as plt

# New data provided by the user
data = {
    1: {
        "rate": [10000, 20000, 30000, 40000, 50000],
        "rps":  [9781.85, 19677.30, 29583.68, 35549.58, 36379.14],
        "p50":  [12.69, 15.83, 37.89, 2040.0, 5260.0], # Converted ms and s to ms
        "p99":  [56.45, 60.45, 98.82, 3250.0, 7970.0], # Converted ms and s to ms
        "cpu":  "frontend CPU ~90% (≥30k)"
    },
    2: {
        "rate": [10000, 20000, 30000, 40000, 50000],
        "rps":  [9737.10, 19647.77, 29728.40, 37530.18, 38796.42],
        "p50":  [12.88, 10.70, 18.66, 1110.0, 4360.0],
        "p99":  [51.97, 45.06, 69.63, 2310.0, 6840.0],
        "cpu":  "frontend CPU ~97% (≥30k)"
    },
    4: {
        "rate": [10000, 20000, 30000, 40000, 50000],
        "rps":  [9804.18, 19680.52, 29421.39, 38291.99, 40604.95],
        "p50":  [7.45, 9.73, 10.53, 737.28, 3700.0],
        "p99":  [35.55, 37.57, 47.29, 1930.0, 5930.0],
        "cpu":  "frontend CPU ~98% (≥30k)"
    },
    8: {
        "rate": [10000, 20000, 30000, 40000, 50000],
        "rps":  [9758.95, 19628.12, 29729.45, 38150.57, 41891.13],
        "p50":  [9.08, 8.56, 12.45, 635.90, 3320.0],
        "p99":  [58.40, 41.95, 58.91, 2840.0, 5920.0],
        "cpu":  "frontend CPU ~100% (≥30k)"
    },
}

plt.figure(figsize=(10, 7))

# Original offsets maintained 
offsets = {
    1: (-120, -30),
    2: (10, -45),
    4: (10, 10),
    8: (10, 35),
}

for repl, d in data.items():
    x = d["rate"]
    y = d["rps"]
    line, = plt.plot(x, y, marker="o", label=f"frontend replica={repl}")

    # Find the index of the maximum achieved RPS
    i = max(range(len(y)), key=lambda k: y[k])
    
    # Use the original offset logic
    dx, dy = offsets.get(repl, (8, 8))
    
    # Original annotation style
    plt.annotate(
        d["cpu"],
        xy=(x[i], y[i]),
        xytext=(dx, dy),
        textcoords="offset points",
        fontsize=8,
        color=line.get_color(),
        arrowprops=dict(arrowstyle="->", color=line.get_color())
    )

# Original diagonal line and plot style
ax = plt.gca()
lo = min(ax.get_xlim()[0], ax.get_ylim()[0])
hi = max(ax.get_xlim()[1], ax.get_ylim()[1])
plt.plot([lo, hi], [lo, hi], linestyle="--", linewidth=1, alpha=0.35, zorder=0)

plt.xlabel("Target rate (RPS)")
plt.ylabel("Achieved throughput (RPS)")
plt.title("Throughput vs Rate (other replica=1, frontend replica sweep)")
plt.grid(True, alpha=0.3)
plt.legend(loc="upper left")
plt.tight_layout()
plt.savefig("throughput_vs_rate_frontend_scale.png", dpi=200)

print("Saved: throughput_vs_rate_frontend_scale.png")