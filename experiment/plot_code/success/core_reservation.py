import matplotlib.pyplot as plt

data = {
    4: {
        "rate": [5000, 6000, 7000, 8000, 9000],
        "rps":  [4946.66, 5951.91, 6373.67, 6578.54, 6528.46],
        "cpu":  "Reservation CPU ~96% (≥6000 RPS)"
    },
    8: {
        "rate": [5000, 6000, 7000, 8000, 9000, 10000, 11000],
        "rps":  [4967.80, 5974.31, 6964.18, 7972.04, 8951.45, 9134.93, 9160.01],
        "cpu":  "MongoDB CPU ~100% (≥9000 RPS)"
    },
}

plt.figure(figsize=(10, 7))

offsets = {
    4: (10, 20),
    8: (10, -30),
}

for core, d in data.items():
    x = d["rate"]
    y = d["rps"]
    line, = plt.plot(x, y, marker="o", label=f"reservation core={core}")

    i = max(range(len(y)), key=lambda k: y[k])
    dx, dy = offsets.get(core, (8, 8))
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
plt.title("Throughput vs Rate (Reservation service scaling)")
plt.grid(True, alpha=0.3)
plt.legend(loc="upper left")
plt.tight_layout()
plt.savefig("reservation_throughput_vs_rate.png", dpi=200)

print("Saved: reservation_throughput_vs_rate.png")
