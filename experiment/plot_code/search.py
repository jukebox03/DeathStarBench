import matplotlib.pyplot as plt
import numpy as np

# ---------------------------------------------------------
# 1. 데이터 정의 (지금까지 수집된 실험 결과)
# ---------------------------------------------------------
# 실험 차수: [1코어, 2코어, 4코어, 8코어, 12코어, 14코어]
cores_assigned = np.array([1, 2, 4, 8, 12, 14])

# Reservation 서비스 실제 사용량 (단위: m -> Cores로 변환 예정)
res_usage_m = np.array([999, 1991, 3926, 7551, 10636, 11856])

# 병목 현상이 전이된 다른 서비스들 사용량 (Rate, Memcached)
rate_usage_m = np.array([1756, 2701, 3895, 5151, 5364, 5525])
memc_usage_m = np.array([367, 544, 798, 1022, 1167, 1249])

# 단위 변환 (m -> Cores)
res_usage = res_usage_m / 1000.0
rate_usage = rate_usage_m / 1000.0
memc_usage = memc_usage_m / 1000.0

# 효율 계산 (실제 사용량 / 할당량 * 100)
efficiency = (res_usage / cores_assigned) * 100

# ---------------------------------------------------------
# 2. 첫 번째 그래프: Scalability & Efficiency (확장성 분석)
# ---------------------------------------------------------
fig1, ax1 = plt.subplots(figsize=(12, 7))

# 이상적인 선형 확장선 (Ideal Linear Scaling)
ax1.plot(cores_assigned, cores_assigned, 'k--', label='Ideal Linear Scaling (100%)', alpha=0.5)

# 실제 Reservation 성능 (Actual Performance)
line1 = ax1.plot(cores_assigned, res_usage, marker='o', color='tab:blue', linewidth=3, label='Reservation Actual Usage')

# 효율성(Efficiency) 텍스트 표기
for i, txt in enumerate(efficiency):
    ax1.annotate(f'{txt:.1f}%', 
                 (cores_assigned[i], res_usage[i]), 
                 textcoords="offset points", 
                 xytext=(0,10), 
                 ha='center', 
                 fontsize=10, 
                 fontweight='bold',
                 color='tab:blue')

# 그래프 꾸미기
ax1.set_xlabel('Assigned CPU Cores (Limit)', fontsize=12, fontweight='bold')
ax1.set_ylabel('Actual CPU Usage (Cores)', fontsize=12, fontweight='bold')
ax1.set_title('Scalability Analysis: Diminishing Returns at High Cores', fontsize=14, pad=20)
ax1.grid(True, linestyle='--', alpha=0.7)
ax1.set_xticks(cores_assigned)
ax1.legend(loc='upper left')

# 변곡점(Knee Point) 강조 (12코어부터 꺾임)
ax1.axvspan(8, 14, color='red', alpha=0.1)
ax1.text(11, 2, 'Efficiency Drop\n(Overhead & Contention)', color='red', fontsize=12, fontweight='bold')

plt.savefig('scalability_efficiency.png', dpi=300)
print("✅ 그래프 1 저장 완료: scalability_efficiency.png")

# ---------------------------------------------------------
# 3. 두 번째 그래프: System Impact (병목 전이 분석)
# ---------------------------------------------------------
fig2, ax2 = plt.subplots(figsize=(12, 7))

# Reservation (주인공)
ax2.plot(cores_assigned, res_usage, marker='o', color='tab:blue', linewidth=2, label='Reservation (Target)')

# Rate (피해자 1)
ax2.plot(cores_assigned, rate_usage, marker='s', color='tab:orange', linewidth=2, linestyle='--', label='Rate Service (Dependency)')

# Memcached (피해자 2 - 작지만 치명적)
ax2.plot(cores_assigned, memc_usage, marker='^', color='tab:red', linewidth=2, linestyle='-', label='Memcached (Bottleneck)')

# Memcached 한계선 표시 (1 Core)
ax2.axhline(y=1.0, color='tab:red', linestyle=':', linewidth=2)
ax2.text(1, 1.1, 'Single Core Saturation Limit', color='tab:red', fontsize=10)

# 그래프 꾸미기
ax2.set_xlabel('Reservation CPU Limit Increase', fontsize=12, fontweight='bold')
ax2.set_ylabel('CPU Usage (Cores)', fontsize=12, fontweight='bold')
ax2.set_title('Chain Reaction: How Reservation Scaling Impacts Others', fontsize=14, pad=20)
ax2.grid(True, linestyle='--', alpha=0.7)
ax2.set_xticks(cores_assigned)
ax2.legend()

plt.savefig('system_impact.png', dpi=300)
print("✅ 그래프 2 저장 완료: system_impact.png")