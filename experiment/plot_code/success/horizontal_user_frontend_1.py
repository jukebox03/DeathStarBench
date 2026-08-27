import matplotlib.pyplot as plt

data = {
    1: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000],
        "rps":  [79776.39, 89760.70, 99681.12, 108592.41, 111756.00, 112426.82, 112799.11],
        "p50":  [5.14, 23.34, 42.72, 303.10, 1430, 2680, 3870],
        "p99":  [24.74, 63.26, 82.62, 408.06, 1990, 3980, 5710],
        "frontend_cpu_note": "frontend CPU ~80% (≥110k)",
    },
    2: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [79770.57, 89915.61, 99732.19, 109767.99, 119770.90, 129135.44, 135491.97, 140151.97, 141995.64],
        "p50":  [4.65, 5.70, 8.40, 7.01, 24.08, 134.53, 734.72, 1450, 2310],
        "p99":  [26.42, 26.94, 34.08, 33.38, 78.85, 580.61, 1480, 2460, 3670],
        "frontend_cpu_note": "frontend CPU ~95% (≥130k)",
    },
    4: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [79811.17, 89811.02, 99811.26, 109773.09, 119757.35, 129036.09, 135005.23, 139855.55, 140532.84],
        "p50":  [2.84, 4.92, 3.34, 11.34, 9.98, 132.48, 745.47, 1460, 2480],
        "p99":  [24.19, 28.24, 23.68, 39.58, 57.34, 1150, 2220, 3600, 4870],
        "frontend_cpu_note": "frontend CPU ~97% (≥130k)",
    },
    8: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [79830.35, 89806.18, 99819.99, 109866.21, 119736.17, 128726.11, 133521.11, 138029.75, 139374.50],
        "p50":  [1.60, 4.03, 5.07, 7.35, 7.94, 186.62, 873.98, 1700, 2570],
        "p99":  [56.99, 56.10, 57.18, 58.05, 63.68, 1500, 3740, 3560, 5250],
        "frontend_cpu_note": "frontend CPU ~98% (≥130k)",
    },
}

plt.figure(figsize=(10, 7))

# 각 replica별로 다른 offset 지정
offsets = {
    1: (-120, -25),
    2: (10, -40),
    4: (10, 15),
    8: (10, 40),
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
plt.title("Throughput vs Rate (frontend replica=1, user replica sweep)")
plt.grid(True, alpha=0.3)
plt.legend(loc="upper left")
plt.tight_layout()
plt.savefig("throughput_vs_rate_user_scale_frontend_1.png", dpi=200)

print("Saved: throughput_vs_rate_user_scale_frontend_1.png")