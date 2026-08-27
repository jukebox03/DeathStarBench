import matplotlib.pyplot as plt

data = {
    1: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000],
        "rps":  [79776.39, 89760.70, 99681.12, 108592.41, 111756.00, 112426.82, 112799.11],
        "p50":  [5.14, 23.34, 42.72, 303.10, 1430, 2680, 3870],
        "p99":  [24.74, 63.26, 82.62, 408.06, 1990, 3980, 5710],
        "cpu":  "frontend CPU ~80% (≥110k)"
    },
    2: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [79683.44, 89660.24, 99473.15, 109666.66, 119396.91, 125683.94, 130866.60, 134606.79, 136898.63],
        "p50":  [2.95, 3.82, 2.69, 6.88, 74.69, 126.72, 335.10, 1750, 2620],
        "p99":  [24.96, 28.51, 26.27, 36.19, 145.41, 1940, 3550, 4370, 5550],
        "cpu":  "frontend CPU ~94% (≥130k)"
    },
    4: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [79720.57, 89408.30, 99890.58, 109681.23, 120108.36, 128125.07, 133849.65, 135737.66, 138492.93],
        "p50":  [0.776, 1.20, 2.50, 4.11, 8.34, 342.53, 1030, 1810, 2870],
        "p99":  [23.06, 26.72, 39.55, 45.63, 70.33, 834.56, 1990, 4030, 4430],
        "cpu":  "frontend CPU ~98% (≥130k)"
    },
    8: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [80584.41, 90059.12, 100661.25, 111279.05, 121934.57, 130197.80, 134753.94, 138231.18, 139408.23],
        "p50":  [0.450, 0.786, 1.49, 2.62, 4.46, 58.97, 1110, 1840, 2940],
        "p99":  [24.67, 32.62, 44.29, 56.99, 69.63, 570.37, 2240, 4210, 4830],
        "cpu":  "frontend CPU ~99% (≥130k)"
    },
}

plt.figure(figsize=(10, 7))

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

    i = max(range(len(y)), key=lambda k: y[k])
    dx, dy = offsets.get(repl, (8, 8))
    plt.annotate(
        d["cpu"],
        xy=(x[i], y[i]),
        xytext=(dx, dy),
        textcoords="offset points",
        fontsize=8,
        color=line.get_color(),
        arrowprops=dict(arrowstyle="->", color=line.get_color())
    )

ax = plt.gca()
lo = min(ax.get_xlim()[0], ax.get_ylim()[0])
hi = max(ax.get_xlim()[1], ax.get_ylim()[1])
plt.plot([lo, hi], [lo, hi], linestyle="--", linewidth=1, alpha=0.35, zorder=0)

plt.xlabel("Target rate (RPS)")
plt.ylabel("Achieved throughput (RPS)")
plt.title("Throughput vs Rate (user replica=1, frontend replica sweep)")
plt.grid(True, alpha=0.3)
plt.legend(loc="upper left")
plt.tight_layout()
plt.savefig("throughput_vs_rate_frontend_scale_user_1.png", dpi=200)

print("Saved: throughput_vs_rate_frontend_scale_user_1.png")