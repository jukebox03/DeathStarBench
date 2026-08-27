import matplotlib.pyplot as plt
import numpy as np

# ====== 데이터: Recommendation.GetRecommendations (기본 설정) ======
# (대략: -c=800, --connections=400 이었던 것으로 해석)
instances_base = np.array([1, 2, 4, 8, 16])
rps_base = np.array([38017, 55000, 74062, 83230, 88471])
lat_base = np.array([9.93, 14.16, 23.06, 45.67, 94.75])

# CPU 사용률(주석용, 숫자 라벨로만 사용)
cpu_base = ["84%", "90%", "93%", "95%", "97% (some cores 100%)"]

# ====== 데이터: 설정 최적화 후 (-c 800→400, --connections 400→50) ======
instances_opt = np.array([16, 32])
rps_opt = np.array([100991, 111290])
lat_opt = np.array([48.48, 89.49])

cpu_opt = ["95%", "97% (some cores 100%)"]
# ================================================================

fig, ax1 = plt.subplots(figsize=(9, 5.5))

# X축: instance 수 (log2가 보기 좋음)
ax1.set_xscale("log", base=2)
ax1.set_xlabel("ghz Instances (log2 scale)")
ax1.set_ylabel("Total RPS")

# ---- Left Y: RPS ----
ax1.plot(instances_base, rps_base, marker="o", linewidth=2, label="RPS (baseline: -c=800, --connections=400)")
ax1.plot(instances_opt, rps_opt, marker="o", linestyle="--", linewidth=2, label="RPS (tuned: -c=400, --connections=50)")

# 각 점에 RPS 라벨
for x, y in zip(instances_base, rps_base):
    ax1.text(x, y, f"{y:,}", ha="center", va="bottom")
for x, y in zip(instances_opt, rps_opt):
    ax1.text(x, y, f"{y:,}", ha="center", va="bottom")

ax1.grid(True, which="both", linestyle="--", linewidth=0.5)

# ---- Right Y: Avg Latency ----
ax2 = ax1.twinx()
ax2.set_ylabel("Avg Latency (ms)")
ax2.plot(instances_base, lat_base, marker="s", linewidth=2, label="Avg Latency (baseline)")
ax2.plot(instances_opt, lat_opt, marker="s", linestyle="--", linewidth=2, label="Avg Latency (tuned)")

# latency 라벨
for x, y in zip(instances_base, lat_base):
    ax2.text(x, y, f"{y:.2f}ms", ha="center", va="bottom")
for x, y in zip(instances_opt, lat_opt):
    ax2.text(x, y, f"{y:.2f}ms", ha="center", va="bottom")

# ---- "connections 최적화 의미"를 강조하는 주석 (16 instance 비교) ----
# 16에서 baseline vs tuned 개선을 화살표로 표시
x16 = 16
y16_base = rps_base[-1]
y16_opt = rps_opt[0]
ax1.annotate(
    f"Connection tuning matters\n16 inst: {y16_base:,} → {y16_opt:,} RPS\nLatency: {lat_base[-1]:.2f} → {lat_opt[0]:.2f} ms",
    (x16, y16_opt),
    textcoords="offset points",
    xytext=(20, -40),
    arrowprops=dict(arrowstyle="->")
)

# ---- 범례 합치기 ----
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

plt.title("Recommendation.GetRecommendations: Scaling vs Connection/Concurrency Tuning")
plt.tight_layout()

# ====== 이미지 저장 ======
plt.savefig("recommendation_instances_rps_latency.png", dpi=300)
plt.close()
