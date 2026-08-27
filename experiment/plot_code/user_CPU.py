import matplotlib.pyplot as plt
import numpy as np

# ====== 데이터 ======
cpu_limit = np.array([1, 2, 4, 8, 12, 18], dtype=float)
cpu_used  = np.array([1.0, 2.0, 3.990, 6.173, 6.47, 6.35], dtype=float)
# ====================

# 효율(%)
eff = (cpu_used / cpu_limit) * 100.0

# 그래프 범위
x_min = 0
x_max = cpu_limit.max()
y_max = max(cpu_used.max(), cpu_limit.max()) * 1.05

fig, ax = plt.subplots(figsize=(10.5, 6))

# 1) Ideal linear scaling (100%)
ax.plot(
    [x_min, x_max],
    [x_min, x_max],
    linestyle="--",
    linewidth=2,
    label="Ideal Linear Scaling (100%)",
)

# 2) Actual CPU usage
ax.plot(
    cpu_limit,
    cpu_used,
    marker="o",
    linewidth=3,
    label="User Actual CPU Usage",
)

# 축 설정
ax.set_title("Scalability Analysis: CPU Usage vs Limit")
ax.set_xlabel("Assigned CPU Cores (Limit)")
ax.set_ylabel("Actual CPU Usage (Cores)")
ax.set_xlim(x_min, x_max * 1.02)
ax.set_ylim(0, y_max)

# X축 눈금 = core limit (눈금선 효과)
ax.set_xticks(cpu_limit)

# Grid (세로 눈금선 강조)
ax.grid(True, axis="x", linestyle="--", linewidth=0.9)
ax.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.7)

# 3) High-core region 음영
shade_start = 8
ax.axvspan(shade_start, x_max, alpha=0.15)

# 효율(%) 라벨
for x, y, p in zip(cpu_limit, cpu_used, eff):
    ax.text(
        x,
        y,
        f"{p:.1f}%",
        ha="center",
        va="bottom",
        fontweight="bold",
    )

# 고코어 구간 설명
ax.text(
    (shade_start + x_max) / 2,
    y_max * 0.18,
    "High-core region\n(Non-CPU utilization saturates)",
    ha="center",
    va="center",
    fontweight="bold",
)

ax.legend(loc="upper left")

plt.tight_layout()
plt.savefig("user_scaling_cpu_only.png", dpi=300)
plt.close()
