import matplotlib.pyplot as plt
import numpy as np

# ==============================================================================
# 1. DATA DEFINITION (Rate Service CPU Usage)
# ==============================================================================
# X축: Reservation Core Limit
cores = np.array([1, 2, 4, 8, 12, 14])

# Y축: Rate Service CPU Usage (Unit: Cores)
# 데이터 출처: 이전 실험 로그 기반 정리

# 1) Random (Standard)
# 특징: DB Latency 덕분에 Rate 호출 빈도가 낮음 -> CPU 사용량 낮음 (안전)
rate_random = np.array([1.756, 2.701, 3.895, 5.151, 5.364, 5.525])

# 2) Fixed 1-Key (High Contention)
# 특징: 4코어 데이터는 추세 기반 보간(Interpolation), 8코어부터 급격히 포화
rate_fixed = np.array([1.765, 4.809, 6.300, 7.842, 8.257, 8.337]) 
# (Note: 4코어 Fixed 데이터는 실험 누락으로 2코어와 8코어 사이 중간값 추정 적용)

# 3) Distributed 4-Keys (Max Pressure)
# 특징: 락이 풀리자마자 Rate를 미친듯이 호출 -> 가장 빠르게 8코어 도달
rate_distributed = np.array([3.513, 4.969, 6.728, 7.881, 8.133, 8.293])


# ==============================================================================
# 2. GRAPH DRAWING
# ==============================================================================
fig, ax = plt.subplots(figsize=(12, 7))

# Plot Lines
ax.plot(cores, rate_random, marker='o', markersize=9, color='tab:blue', linewidth=3, label='Random (Protected by DB Latency)')
ax.plot(cores, rate_fixed, marker='^', markersize=9, color='tab:red', linewidth=2, linestyle='--', label='Fixed 1-Key (High Load)')
ax.plot(cores, rate_distributed, marker='s', markersize=9, color='tab:green', linewidth=3, linestyle='-.', label='Distributed 4-Keys (Max Load)')

# -------------------------------------------------------
# Annotations & Storytelling
# -------------------------------------------------------

# 1. The Ceiling (Physical Limit)
ax.axhline(y=8.3, color='black', linestyle=':', linewidth=2)
ax.text(1, 8.5, 'Physical Limit (~8.3 Cores)', color='black', fontsize=11, fontweight='bold')

# 2. The Gap (Safety Margin)
ax.annotate('Safety Margin\n(DB Wait Time)', 
            xy=(14, 5.525), xytext=(14, 7),
            arrowprops=dict(arrowstyle='<->', color='blue', lw=2),
            fontsize=10, fontweight='bold', color='tab:blue', ha='center')

# 3. Early Saturation (Distributed)
ax.annotate('Rapid Saturation!', 
            xy=(4, 6.728), xytext=(2, 7.5),
            arrowprops=dict(facecolor='green', shrink=0.05),
            fontsize=11, fontweight='bold', color='tab:green')

# Styling
ax.set_title('Rate Service CPU Usage Comparison by Scenario', fontsize=15, fontweight='bold', pad=20)
ax.set_xlabel('Reservation CPU Core Limit', fontsize=12, fontweight='bold')
ax.set_ylabel('Rate Service CPU Usage (Cores)', fontsize=12, fontweight='bold')
ax.grid(True, linestyle='--', alpha=0.6)
ax.set_xticks(cores)
ax.legend(loc='lower right', fontsize=11, framealpha=0.9, shadow=True)

# Value Labels (Selective)
for i in [1, 3, 5]: # 2, 8, 14 cores
    ax.text(cores[i], rate_random[i]-0.4, f'{rate_random[i]:.1f}', ha='center', color='tab:blue', fontweight='bold')
    ax.text(cores[i], rate_distributed[i]+0.2, f'{rate_distributed[i]:.1f}', ha='center', color='tab:green', fontweight='bold')

plt.tight_layout()
plt.savefig('rate_service_cpu_comparison.png', dpi=300)
print("✅ 그래프 저장 완료: rate_service_cpu_comparison.png")
plt.show()