import matplotlib.pyplot as plt

data = {
    1: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000],
        "rps":  [79805.40, 89742.36, 99421.07, 105258.50, 106374.34, 106720.11, 106556.78],
        "p50":  [7.57, 32.83, 65.73, 957.44, 2330, 3560, 4720],
        "p99":  [45.73, 66.88, 143.87, 1300, 3360, 5260, 7020],
        "frontend_cpu_note": "frontend CPU ~77% (≥100k)",
    },
    2: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [79808.36, 89784.40, 99836.47, 109897.47, 119620.56, 128061.49, 133635.28, 137050.05, 137020.22],
        "p50":  [3.08, 5.11, 7.47, 9.06, 29.42, 301.57, 955.39, 1760, 2840],
        "p99":  [57.06, 65.54, 76.61, 85.95, 129.34, 1590, 3130, 3440, 5270],
        "frontend_cpu_note": "frontend CPU ~95% (≥130k)",
    },
    4: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [79803.78, 89822.89, 99819.93, 109844.84, 119682.22, 128770.58, 134392.74, 137773.34, 137838.31],
        "p50":  [3.54, 3.84, 5.78, 5.27, 19.82, 182.40, 907.26, 1740, 2800],
        "p99":  [23.92, 23.69, 27.97, 25.33, 65.66, 858.11, 2180, 3460, 4940],
        "frontend_cpu_note": "frontend CPU ~96% (≥130k)",
    },
    8: {
        "rate": [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000, 160000],
        "rps":  [79758.27, 89844.11, 99681.46, 109968.78, 119723.21, 127858.80, 134140.18, 136316.06, 135425.90],
        "p50":  [3.55, 4.26, 7.14, 10.61, 12.01, 262.91, 965.12, 1890, 3040],
        "p99":  [24.96, 24.99, 31.65, 38.46, 56.96, 1150, 2150, 3360, 5090],
        "frontend_cpu_note": "frontend CPU ~95% (≥130k)",
    },
}

plt.figure(figsize=(10, 7))

offsets = {
    1: (-130, -20),
    2: (10, -45),
    4: (10, 10),
    8: (10, 35),
}

for conn, d in sorted(data.items()):
    x = d["rate"]
    y = d["rps"]
    line, = plt.plot(x, y, marker="o", label=f"ClientConn={conn}")
    
    max_idx = max(range(len(y)), key=lambda i: y[i])
    xm, ym = x[max_idx], y[max_idx]
    note = d["frontend_cpu_note"]
    dx, dy = offsets.get(conn, (10, 10))
    
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
plt.title("Throughput vs Rate (frontend=1, user=1, ClientConn sweep)")
plt.grid(True, alpha=0.3)
plt.legend(loc="upper left")
plt.tight_layout()
plt.savefig("throughput_vs_rate_clientconn_scale.png", dpi=200)

print("Saved: throughput_vs_rate_clientconn_scale.png")