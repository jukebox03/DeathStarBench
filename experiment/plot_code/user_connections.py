import matplotlib.pyplot as plt
import numpy as np

# ====== 실험 데이터 ======
connections = np.array([1, 10, 50, 100, 200, 400])
rps = np.array([74737, 95328, 89924, 85850, 80795, 76218])
avg_latency = np.array([18.05, 7.99, 6.74, 6.36, 6.64, 7.54])
# ========================

# 최적점 계산
best_idx = np.argmax(rps)

plt.figure(figsize=(8, 5))

# RPS 곡선
plt.plot(connections, rps, marker="o", linewidth=2, label="Total RPS")

# 최적점 강조
plt.scatter(
    connections[best_idx],
    rps[best_idx],
    s=120,
    zorder=5,
    label=f"Optimal (conn={connections[best_idx]})"
)

# 주석
plt.annotate(
    f"Peak RPS\n{rps[best_idx]:,} RPS\nAvg Lat {avg_latency[best_idx]} ms",
    (connections[best_idx], rps[best_idx]),
    textcoords="offset points",
    xytext=(10, 15),
    arrowprops=dict(arrowstyle="->")
)

plt.xscale("log")
plt.xlabel("Connections (log scale)")
plt.ylabel("Total RPS")
plt.title("Effect of Connection Count on Throughput")
plt.grid(True, which="both", linestyle="--", linewidth=0.5)
plt.legend()
plt.tight_layout()

# ====== 이미지로 저장 ======
plt.savefig("connections_vs_rps.png", dpi=300)
plt.close()