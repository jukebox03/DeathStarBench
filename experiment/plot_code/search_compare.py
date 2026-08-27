import matplotlib.pyplot as plt
import numpy as np

# ==========================================
# 1. 실험 데이터 입력 (Raw Data)
# ==========================================

# X축: 할당된 CPU Limit (Cores)
x_random = np.array([1, 2, 4, 8, 12, 14])
x_fixed  = np.array([1, 2, 8, 12, 14]) # (4코어 Fixed 데이터는 실험 생략으로 제외)

# Y축: Reservation CPU 사용량 (m unit -> Core conversion)
y_res_random = np.array([999, 1991, 3926, 7551, 10636, 11856]) / 1000.0
y_res_fixed  = np.array([999, 1984, 7204, 9629, 10333]) / 1000.0

# Y축: Rate 서비스 CPU 사용량 (Fixed 모드에서 폭발)
# (Random 모드 데이터는 일부 추정치나 기록된 것 사용, 여기서는 Fixed 위주 비교)
y_rate_fixed = np.array([1765, 4809, 7842, 8257, 8337]) / 1000.0

# Y축: Memcached CPU 사용량 (Random vs Fixed)
# Random: 1~14코어 실험 중 기록된 데이터
y_memc_random = np.array([367, 544, 798, 1022, 1167, 1249]) / 1000.0
# Fixed: 1, 2, 8, 12, 14코어 데이터
y_memc_fixed  = np.array([179, 491, 649, 871, 927]) / 1000.0

# ==========================================
# 2. 그래프 그리기
# ==========================================

# -------------------------------------------------------
# Graph 1: Scalability & Efficiency Paradox
# 설명: I/O가 빠른 Fixed 모드가 고부하(High Core)에서 오히려 느려지는 현상
# -------------------------------------------------------
fig1, ax1 = plt.subplots(figsize=(10, 6))

ax1.plot(x_random, x_random, 'k--', alpha=0.2, label='Ideal Linear (100% Efficiency)')
ax1.plot(x_random, y_res_random, marker='o', color='tab:blue', linewidth=2, label='Random Requests (Standard)')
ax1.plot(x_fixed, y_res_fixed, marker='^', color='tab:red', linewidth=2, linestyle='--', label='Fixed Requests (High I/O)')

# 주석: 효율 저하 구간
ax1.annotate('Bottlenecked by Rate Service\n(Efficiency Drop)', 
             xy=(14, 10.333), xytext=(8, 12),
             arrowprops=dict(facecolor='black', shrink=0.05),
             fontsize=10, fontweight='bold', color='darkred')

ax1.set_xlabel('Assigned CPU Limit (Cores)', fontweight='bold')
ax1.set_ylabel('Actual CPU Usage (Cores)', fontweight='bold')
ax1.set_title('Scalability Paradox: Why High I/O Lowered CPU Efficiency', fontsize=14, pad=15)
ax1.grid(True, linestyle='--', alpha=0.5)
ax1.legend()
plt.savefig('1_scalability_paradox.png', dpi=300)
print("saved: 1_scalability_paradox.png")


# -------------------------------------------------------
# Graph 2: The Bottleneck Shift (Reservation -> Rate)
# 설명: Reservation의 제한을 풀자 Rate 서비스가 폭발하며 새로운 병목이 됨
# -------------------------------------------------------
fig2, ax2 = plt.subplots(figsize=(10, 6))

indices = np.arange(len(x_fixed))
width = 0.35

ax2.bar(indices - width/2, y_res_fixed, width, label='Reservation (Target)', color='tab:blue', alpha=0.8)
ax2.bar(indices + width/2, y_rate_fixed, width, label='Rate Service (Victim)', color='tab:orange', hatch='//', alpha=0.8)

ax2.set_xlabel('CPU Core Limit (Fixed Scenario)', fontweight='bold')
ax2.set_ylabel('CPU Usage (Cores)', fontweight='bold')
ax2.set_title('Bottleneck Shift: Rate Service Saturation', fontsize=14, pad=15)
ax2.set_xticks(indices)
ax2.set_xticklabels(x_fixed)
ax2.legend()
ax2.grid(True, axis='y', linestyle='--', alpha=0.5)

# Rate 포화 선 표시
ax2.axhline(y=8.3, color='red', linestyle=':', linewidth=2)
ax2.text(0, 8.5, 'Rate Service Limit (~8.3 Cores)', color='red', fontweight='bold')

plt.savefig('2_bottleneck_shift.png', dpi=300)
print("saved: 2_bottleneck_shift.png")


# -------------------------------------------------------
# Graph 3: Memcached Load Analysis
# 설명: Fixed Request가 어떻게 캐시 부하를 줄였는가?
# -------------------------------------------------------
fig3, ax3 = plt.subplots(figsize=(10, 6))

ax3.plot(x_random, y_memc_random, marker='o', color='tab:purple', linewidth=2, label='Random (Cache Miss/Contention)')
ax3.plot(x_fixed, y_memc_fixed, marker='s', color='tab:green', linewidth=2, linestyle='--', label='Fixed (100% Hit)')

ax3.set_xlabel('System Load Increase (Core Limit)', fontweight='bold')
ax3.set_ylabel('Memcached CPU Usage (Cores)', fontweight='bold')
ax3.set_title('Impact of Request Pattern on Memcached', fontsize=14, pad=15)
ax3.grid(True, linestyle='--', alpha=0.5)
ax3.legend()

plt.savefig('3_memcached_impact.png', dpi=300)
print("saved: 3_memcached_impact.png")