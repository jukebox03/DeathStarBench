import matplotlib.pyplot as plt
import numpy as np

# ====== 실험 데이터 (단일 ghz instance) ======
connections = np.array([50, 100, 200, 400, 800])
rps = np.array([25660, 30767, 34343, 36449, 38086])
avg_latency = np.array([1.21, 1.83, 2.98, 5.02, 9.91])
# ===========================================

fig, ax1 = plt.subplots(figsize=(8, 5))

# ---- Left Y-axis: RPS ----
ax1.plot(connections, rps, marker="o", linewidth=2, label="Total RPS")
ax1.set_xlabel("Concurrency (-c, log2 scale)")
ax1.set_ylabel("Total RPS")
ax1.set_xscale("log", base=2)
ax1.grid(True, which="both", linestyle="--", linewidth=0.5)

# 포화 지점 (RPS 최대)
sat_idx = np.argmax(rps)
ax1.scatter(connections[sat_idx], rps[sat_idx], s=120, zorder=5)
ax1.annotate(
    f"Throughput saturation\n~{rps[sat_idx]:,} RPS",
    (connections[sat_idx], rps[sat_idx]),
    textcoords="offset points",
    xytext=(10, -25),
    arrowprops=dict(arrowstyle="->")
)

# ---- Right Y-axis: Avg Latency ----
ax2 = ax1.twinx()
ax2.plot(connections, avg_latency, marker="s", linestyle="--", linewidth=2, label="Avg Latency")
ax2.set_ylabel("Avg Latency (ms)")

# ---- Combined legend ----
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

plt.title("Single ghz Instance: Throughput Saturation vs Latency Growth")
plt.tight_layout()

# ====== 이미지로 저장 ======
plt.savefig("single_instance_concurrency_rps_latency.png", dpi=300)
plt.close()
