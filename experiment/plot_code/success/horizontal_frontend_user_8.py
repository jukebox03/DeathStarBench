import matplotlib.pyplot as plt

data = {
    1: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [79848.14, 89779.75, 99751.56, 109807.93, 119787.49, 128943.38, 134392.74, 138812.03, 139734.43],
        "p50":  [1.61, 4.11, 3.48, 5.48, 12.72, 129.60, 875.01, 1540, 2530],
        "p99":  [19.60, 27.71, 25.07, 28.67, 54.88, 671.23, 2200, 2970, 4670],
        "cpu":  "frontend CPU ~98% (≥130k)"
    },
    2: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [79604.67, 89670.05, 99607.47, 109646.77, 119530.24, 126191.35, 130375.40, 133246.77, 134781.59],
        "p50":  [1.80, 2.56, 3.05, 6.64, 44.29, 419.07, 1270, 2340, 3260],
        "p99":  [31.69, 35.04, 38.62, 49.50, 253.44, 2210, 4190, 4500, 5660],
        "cpu":  "frontend CPU ~98% (≥130k)"
    },
    4: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [79616.99, 89444.60, 99846.78, 109462.98, 119627.38, 124851.37, 128580.43, 130397.68, 132510.60],
        "p50":  [0.86, 1.20, 2.62, 5.12, 63.29, 631.29, 1660, 2500, 3470],
        "p99":  [30.50, 38.65, 53.73, 67.65, 339.45, 3420, 4780, 6290, 6890],
        "cpu":  "frontend CPU ~99% (≥120k)"
    },
    8: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [80677.62, 90234.80, 100643.24, 111563.79, 122290.72, 124295.81, 127336.36, 128671.25, 130070.01],
        "p50":  [0.638, 1.02, 1.71, 3.53, 10.10, 709.12, 1690, 2900, 3770],
        "p99":  [40.48, 54.40, 93.25, 104.00, 176.26, 4250, 6820, 7670, 8950],
        "cpu":  "frontend CPU ~100% (≥120k)"
    },
}

plt.figure(figsize=(10, 7))

offsets = {
    1: (10, 35),
    2: (10, 10),
    4: (10, -25),
    8: (10, -55),
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
plt.title("Throughput vs Rate (user replica=8, frontend replica sweep)")
plt.grid(True, alpha=0.3)
plt.legend(loc="upper left")
plt.tight_layout()
plt.savefig("throughput_vs_rate_frontend_scale_user_8.png", dpi=200)

print("Saved: throughput_vs_rate_frontend_scale_user_8.png")