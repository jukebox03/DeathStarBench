import matplotlib.pyplot as plt
import numpy as np

# ====== 실험 데이터 ======
instances = np.array([1, 2, 4, 8, 16])
total_rps = np.array([40800, 60000, 83300, 100422, 107679])
scale_eff = np.array([100.0, 73.5, 51.1, 30.8, 16.5])
# ========================

# 서버 한계점 (최대 RPS)
peak_idx = np.argmax(total_rps)

plt.figure(figsize=(8, 5))

# Total RPS 곡선
plt.plot(instances, total_rps, marker="o", linewidth=2, label="Total RPS")

# 한계점 강조
plt.scatter(
    instances[peak_idx],
    total_rps[peak_idx],
    s=120,
    zorder=5,
    label="Near Saturation"
)

# 주석 (scaling 한계 설명)
plt.annotate(
    f"Saturation region\n{total_rps[peak_idx]:,} RPS\nEfficiency {scale_eff[peak_idx]}%",
    (instances[peak_idx], total_rps[peak_idx]),
    textcoords="offset points",
    xytext=(10, -25),
    arrowprops=dict(arrowstyle="->")
)

plt.xscale("log", base=2)
plt.xlabel("ghz Instances (log2 scale)")
plt.ylabel("Total RPS")
plt.title("Sublinear Scaling of Throughput with ghz Instances")
plt.grid(True, which="both", linestyle="--", linewidth=0.5)
plt.legend()
plt.tight_layout()

# ====== 이미지로 저장 ======
plt.savefig("ghz_instances_vs_rps.png", dpi=300)
plt.close()
