import matplotlib.pyplot as plt

# Experiment 1: USER_CONN_POOL_SIZE Bottleneck Analysis
# Insight: Sidecar reduces per-connection RPS from ~90k to ~15k due to mTLS & L7 parsing.
data = {
    "USER_CONN_POOL_SIZE = 1": {
        "rate": [15000, 16000, 17000, 18000, 19000, 20000],
        "rps":  [14663.43, 15651.97, 16443.50, 16220.42, 16121.96, 16121.02],
        "p50":  [47.07, 57.63, 303.10, 1500.0, 2560.0, 3350.0],
        "p99":  [100.93, 116.54, 1660.0, 4710.0, 6300.0, 7410.0],
        "note": "Limit ~16.4k RPS"
    },
    "USER_CONN_POOL_SIZE = 2": {
        "rate": [26000, 27000, 28000, 29000, 30000, 31000],
        "rps":  [25570.25, 26683.66, 27626.67, 28654.44, 28840.98, 28553.69],
        "p50":  [20.94, 36.93, 50.88, 48.19, 407.04, 1040.0],
        "p99":  [48.61, 85.12, 110.40, 120.77, 2020.0, 3830.0],
        "note": "Limit ~28.8k RPS"
    },
    "USER_CONN_POOL_SIZE = 4": {
        "rate": [36000, 37000, 38000, 39000, 40000, 41000],
        "rps":  [35575.33, 36447.95, 37583.23, 37923.75, 37405.94, 37707.44],
        "p50":  [25.14, 45.85, 27.06, 372.48, 882.17, 1160.0],
        "p99":  [61.95, 156.03, 91.01, 2140.0, 3620.0, 4440.0],
        "note": "Limit ~37.9k RPS"
    },
    "USER_CONN_POOL_SIZE = 8": {
        "rate": [38000, 39000, 40000, 41000, 42000, 43000],
        "rps":  [37588.41, 38609.54, 39467.04, 39032.16, 39668.68, 39710.84],
        "p50":  [28.70, 19.90, 16.06, 491.01, 570.88, 1110.0],
        "p99":  [88.51, 67.71, 56.64, 3250.0, 3750.0, 4150.0],
        "note": "Limit ~39.7k RPS"
    },
    "USER_CONN_POOL_SIZE = 16": {
        "rate": [38000, 39000, 40000, 41000, 42000, 43000],
        "rps":  [37588.55, 38539.16, 39381.27, 39770.90, 39850.52, 40050.55],
        "p50":  [27.28, 15.30, 18.66, 161.54, 431.61, 857.09],
        "p99":  [86.91, 57.12, 69.76, 1800.0, 3740.0, 4840.0],
        "note": "Limit ~40k RPS (Max)"
    },
}

plt.figure(figsize=(10, 7))

# Offsets for annotation positioning
offsets = {
    "USER_CONN_POOL_SIZE = 1": (10, -10),
    "USER_CONN_POOL_SIZE = 2": (10, -20),
    "USER_CONN_POOL_SIZE = 4": (-80, 20),
    "USER_CONN_POOL_SIZE = 8": (-60, 30),
    "USER_CONN_POOL_SIZE = 16": (10, -5),
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
    "Insight: Sidecar Overhead\n"
    "• No Sidecar: ~90k RPS/conn\n"
    "• With Sidecar: ~15k RPS/conn\n"
    "  (Due to mTLS & L7 parsing)"
)
plt.text(0.02, 0.75, info_text, transform=ax.transAxes, fontsize=9,
         verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.2))

plt.xlabel("Target rate (RPS)")
plt.ylabel("Achieved throughput (RPS)")
# Title updated with Sidecar core info
plt.title("Connection Pool Saturation: Throughput vs Rate\n(Frontend, User & Sidecars fixed 4 cores, Varying Conn Pool Size)")
plt.grid(True, alpha=0.3)
plt.legend(loc="upper left")
plt.tight_layout()
plt.savefig("istio_throughput_vs_rate_conn_pool.png", dpi=200)

print("Saved: istio_throughput_vs_rate_conn_pool.png")