import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# =========================
# Raw data
# =========================
data = {
    1: {
        "rate": [50000,60000,70000,80000,90000,100000,110000,120000],
        "rps":  [49900.02,59904.07,69615.90,79834.55,89381.64,90976.11,90960.41,91267.24],
        "p50":  ["1.20ms","2.02ms","3.42ms","6.14ms","46.01ms","1.71s","3.20s","4.67s"],
        "p99":  ["7.50ms","7.99ms","8.64ms","15.59ms","104.83ms","2.54s","4.89s","6.99s"],
    },
    2: {
        "rate": [50000,60000,70000,80000,90000,100000,110000,120000,130000,140000,150000,160000],
        "rps":  [49789.98,59743.86,69694.44,79852.55,89811.17,99687.42,109453.26,119094.73,
                 126033.05,128613.38,128602.47,129129.25],
        "p50":  ["1.15ms","1.18ms","2.29ms","2.29ms","3.86ms","7.26ms","22.90ms","91.46ms",
                 "494.33ms","1.50s","2.67s","3.85s"],
        "p99":  ["8.49ms","9.65ms","11.98ms","12.96ms","19.31ms","35.01ms","184.45ms","510.98ms",
                 "1.61s","3.06s","5.20s","6.06s"],
    },
    4: {
        "rate": [50000,60000,70000,80000,90000,100000,110000,120000,130000,140000,150000,160000,170000],
        "rps":  [49889.48,59955.86,69949.38,79949.97,89855.92,99900.84,109629.26,119127.76,
                 128348.62,136808.13,140067.42,141087.86,140208.70],
        "p50":  ["0.485ms","0.823ms","1.17ms","2.06ms","4.79ms","8.95ms","20.91ms","66.88ms",
                 "168.06ms","493.82ms","1.31s","2.03s","3.18s"],
        "p99":  ["10.68ms","12.06ms","15.20ms","19.68ms","29.63ms","49.50ms","115.01ms","528.38ms",
                 "1.15s","1.78s","3.38s","5.65s","6.48s"],
        "cpu_note": (140000, "frontend CPU ~94%"),
    },
    8: {
        "rate": [50000,60000,70000,80000,90000,100000,110000,120000,130000,140000,150000,160000,170000],
        "rps":  [49828.61,59786.77,69730.75,79812.12,89791.40,99532.04,109452.41,118909.95,
                 125129.64,129234.30,130099.20,132275.51,132568.83],
        "p50":  ["1.49ms","1.58ms","1.92ms","2.79ms","4.57ms","11.45ms","27.17ms","91.90ms",
                 "574.46ms","1.36s","2.62s","3.25s","4.07s"],
        "p99":  ["12.99ms","17.76ms","20.16ms","25.95ms","39.84ms","76.86ms","185.47ms","772.61ms",
                 "2.83s","4.24s","5.83s","6.73s","8.48s"],
        "cpu_note": (130000, "frontend CPU ~96–97%"),
    },
}

# =========================
# Helpers
# =========================
def latency_to_ms(v):
    return float(v[:-2]) if v.endswith("ms") else float(v[:-1]) * 1000

def fmt_latency(v, _):
    return f"{v/1000:.1f}s" if v >= 1000 else f"{v:.0f}ms"

lat_fmt = FuncFormatter(fmt_latency)

# =========================
# Throughput vs Rate
# =========================
plt.figure(figsize=(8,6))
colors = {}

for rep, d in data.items():
    (line,) = plt.plot(d["rate"], d["rps"], marker="o", label=f"replica {rep}")
    colors[rep] = line.get_color()

    if "cpu_note" in d:
        r, text = d["cpu_note"]
        y = d["rps"][d["rate"].index(r)]
        plt.annotate(
            text,
            xy=(r, y),
            xytext=(r, y * 1.07),
            arrowprops=dict(arrowstyle="->"),
        )

ax = plt.gca()
lo = min(ax.get_xlim()[0], ax.get_ylim()[0])
hi = max(ax.get_xlim()[1], ax.get_ylim()[1])
plt.plot([lo, hi], [lo, hi], linestyle="--", linewidth=1, alpha=0.35, zorder=0)

plt.xlabel("Rate (-R)")
plt.ylabel("Throughput (Requests/sec)")
plt.title("Throughput vs Rate (replica 1, 2, 4, 8)")
plt.legend()
plt.tight_layout()
plt.savefig("throughput_vs_rate.png", dpi=200)

print("Saved:")
print(" - throughput_vs_rate.png")
