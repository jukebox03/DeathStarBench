import matplotlib.pyplot as plt
import numpy as np

# ====== 업데이트된 데이터 (MongoDB) ======
# (CPU limit cores, saturated RPS, observed CPU usage cores)
cpu_limit = np.array([4, 8, 12, 18, 36], dtype=float)
sat_rps   = np.array([5.32, 4.53, 33.19, 55.19, 243.29], dtype=float)
cpu_used  = np.array([3.972, 7.93, 11.97, 18.012, 35.021], dtype=float)
# =======================================

# 효율(%): used / limit
eff = (cpu_used / cpu_limit) * 100.0

# 그래프 범위 설정 (ideal line을 보기 좋게)
x_min = max(0, cpu_limit.min() - 1)
x_max = cpu_limit.max()
y_max = max(cpu_used.max(), cpu_limit.max()) * 1.05

fig, ax1 = plt.subplots(figsize=(10.5, 6))

# 1) Ideal linear scaling (100%): y = x
ax1.plot(
    [x_min, x_max],
    [x_min, x_max],
    linestyle="--",
    linewidth=2,
    label="Ideal Linear Scaling (100%)",
)

# 2) Actual CPU usage (메인)
ax1.plot(
    cpu_limit,
    cpu_used,
    marker="o",
    linewidth=3,
    label="MongoDB Actual CPU Usage",
)

# 축/그리드
ax1.set_title("Scalability Analysis: CPU Usage vs Limit (with RPS as Secondary)")
ax1.set_xlabel("Assigned CPU Cores (Limit)")
ax1.set_ylabel("Actual CPU Usage (Cores)")
ax1.set_xlim(x_min, x_max * 1.02)
ax1.set_ylim(0, y_max)

# x축 눈금은 limit 값들로 고정 (원하는 '눈금선' 효과)
ax1.set_xticks(cpu_limit)

# 세로 그리드(눈금선) 강조 + 기본 그리드
ax1.grid(True, axis="x", linestyle="--", linewidth=0.9)
ax1.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.7)

# 3) High cores region 음영 (drop이 크지 않아도 "고코어 구간" 강조용)
shade_start = 18  # 필요하면 12로 바꿔도 됨
ax1.axvspan(shade_start, x_max, alpha=0.15)

# 효율 라벨(%) 표시
for x, y, p in zip(cpu_limit, cpu_used, eff):
    ax1.text(x, y, f"{p:.1f}%", ha="center", va="bottom", fontweight="bold")

# 고코어 구간 텍스트 (drop이 '안 보일 수도' 있으니 표현을 중립적으로)
ax1.text(
    (shade_start + x_max) / 2,
    y_max * 0.15,
    "High-core region\n(less visible efficiency drop here)",
    ha="center",
    va="center",
    fontweight="bold",
)

# 4) 보조축: RPS (주황색 계열로 완전히 다르게)
ax2 = ax1.twinx()
ax2.plot(
    cpu_limit,
    sat_rps,
    marker="s",
    linestyle="--",
    linewidth=2.5,
    color="orange",
    label="Saturated RPS (secondary)",
)
ax2.set_ylabel("Saturated RPS")

# RPS 라벨(보조라서 작게)
for x, y in zip(cpu_limit, sat_rps):
    ax2.text(x, y, f"{y:.2f}", ha="center", va="bottom", color="orange")

# 범례 합치기
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

plt.tight_layout()
plt.savefig("mongodb_scaling_with_rps.png", dpi=300)
plt.close()
