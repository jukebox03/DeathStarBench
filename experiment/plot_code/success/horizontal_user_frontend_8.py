import matplotlib.pyplot as plt

data = {
    1: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [80672.74, 90334.40, 100763.16, 111287.93, 121757.57, 131207.60, 134842.84, 137913.67, 139591.99],
        "p50":  [0.454, 0.745, 1.51, 2.83, 5.08, 17.34, 1050, 1930, 2870],
        "p99":  [24.24, 33.44, 44.10, 57.15, 70.72, 177.79, 2940, 4110, 4920],
        "frontend_cpu_note": "frontend CPU ~99% (≥130k)",
    },
    2: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [80382.25, 90343.03, 100592.26, 111308.75, 121773.74, 129045.32, 131880.14, 134961.31, 135496.08],
        "p50":  [0.467, 0.784, 1.42, 2.74, 5.77, 393.21, 1300, 2370, 3220],
        "p99":  [26.30, 39.94, 52.93, 73.54, 110.40, 1750, 4480, 5490, 6860],
        "frontend_cpu_note": "frontend CPU ~99% (≥130k)",
    },
    4: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [80615.42, 90155.12, 100758.21, 111051.62, 121723.14, 126722.07, 130491.87, 132209.76, 132321.72],
        "p50":  [0.531, 0.832, 1.53, 2.83, 7.09, 515.33, 1520, 2580, 3590],
        "p99":  [36.10, 42.81, 76.74, 87.74, 134.27, 3540, 4960, 6720, 7990],
        "frontend_cpu_note": "frontend CPU ~99% (≥130k)",
    },
    8: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [80473.37, 90101.07, 100650.98, 111230.86, 121958.69, 125619.57, 127216.66, 129048.33, 129021.05],
        "p50":  [0.616, 0.99, 1.71, 3.61, 11.80, 726.53, 1850, 2790, 3890],
        "p99":  [34.65, 49.85, 69.44, 105.86, 210.94, 3620, 6060, 7730, 9090],
        "frontend_cpu_note": "frontend CPU ~100% (≥120k)",
    },
}

plt.figure(figsize=(10, 7))

offsets = {
    1: (10, 35),
    2: (10, 10),
    4: (10, -25),
    8: (10, -55),
}

for repl, d in sorted(data.items()):
    x = d["rate"]
    y = d["rps"]
    line, = plt.plot(x, y, marker="o", label=f"user replica={repl}")
    
    max_idx = max(range(len(y)), key=lambda i: y[i])
    xm, ym = x[max_idx], y[max_idx]
    note = d["frontend_cpu_note"]
    dx, dy = offsets.get(repl, (10, 10))
    
    plt.annotate(
        note,
        xy=(xm, ym),
        xytext=(dx, dy),
        textcoords="offset points",
        fontsize=8,
        color=line.get_color(),
        arrowprops=dict(arrowstyle="->", linewidth=0.8, color=line.get_color()),
    )

ax = plt.gca()
lo = min(ax.get_xlim()[0], ax.get_ylim()[0])
hi = max(ax.get_xlim()[1], ax.get_ylim()[1])
plt.plot([lo, hi], [lo, hi], linestyle="--", linewidth=1, alpha=0.35, zorder=0)

plt.xlabel("Target rate (RPS)")
plt.ylabel("Achieved throughput (Requests/sec)")
plt.title("Throughput vs Rate (frontend replica=8, user replica sweep)")
plt.grid(True, alpha=0.3)
plt.legend(loc="upper left")
plt.tight_layout()
plt.savefig("throughput_vs_rate_user_scale_frontend_8.png", dpi=200)

print("Saved: throughput_vs_rate_user_scale_frontend_8.png")