import matplotlib.pyplot as plt

# Horizontal scalability experiment data
data = {
    "(2,2,2,2,2)": {
        "rate": [12000, 13000, 14000, 15000, 16000, 17000],
        "rps":  [11730.61, 12792.07, 13192.59, 13443.46, 13511.32, 13647.41],
        "p50":  [85.57, 108.42, 834.05, 1810.0, 2800.0, 3600.0],
        "p99":  [242.82, 292.61, 2700.0, 4520.0, 5860.0, 6840.0],
        "cpu":  "frontend ~98% (≥13k)"
    },
    "(2,2,2,2,4)": {
        "rate": [16000, 17000, 18000, 19000, 20000, 21000],
        "rps":  [15762.79, 16677.18, 17656.74, 18367.24, 18108.78, 18000.19],
        "p50":  [70.97, 77.25, 114.56, 437.76, 1470.0, 2450.0],
        "p99":  [199.93, 252.29, 333.82, 1700.0, 3920.0, 5400.0],
        "cpu":  "search ~97% (≥18k)"
    },
    "(2,2,4,2,4)": {
        "rate": [18000, 19000, 20000, 21000, 22000, 23000],
        "rps":  [17778.31, 18726.52, 19765.06, 20690.90, 19723.55, 19571.83],
        "p50":  [52.54, 45.38, 59.65, 98.30, 1510.0, 2470.0],
        "p99":  [162.94, 159.10, 196.99, 370.69, 4670.0, 5850.0],
        "cpu":  "rate,reservation ~97% (≥19k)"
    },
    "(4,4,4,2,4)": {
        "rate": [22000, 23000, 24000, 25000, 26000, 27000, 28000],
        "rps":  [21718.06, 22602.90, 23603.44, 23881.61, 24203.55, 24337.66, 24295.13],
        "p50":  [56.70, 89.86, 158.21, 671.23, 1100.0, 1720.0, 2290.0],
        "p99":  [166.01, 285.95, 507.39, 2610.0, 3720.0, 4250.0, 4970.0],
        "cpu":  "frontend,profile ~97% (≥24k)"
    },
}

plt.figure(figsize=(10, 7))

# Offsets for annotation positioning
offsets = {
    "(2,2,2,2,2)": (-120, -30),
    "(2,2,2,2,4)": (10, -45),
    "(2,2,4,2,4)": (10, 10),
    "(4,4,4,2,4)": (10, 35),
}

for config, d in data.items():
    x = d["rate"]
    y = d["rps"]
    line, = plt.plot(x, y, marker="o", label=f"config={config}")

    # Find the index of the maximum achieved RPS
    i = max(range(len(y)), key=lambda k: y[k])
    
    # Use the original offset logic
    dx, dy = offsets.get(config, (8, 8))
    
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
plt.title("Horizontal Scalability: Throughput vs Rate\n(rate, reservation, search, profile, frontend) core allocation")
plt.grid(True, alpha=0.3)
plt.legend(loc="upper left")
plt.tight_layout()
plt.savefig("throughput_vs_rate_horizontal_scalability.png", dpi=200)

print("Saved: throughput_vs_rate_horizontal_scalability.png")