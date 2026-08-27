import matplotlib.pyplot as plt
import numpy as np

# ==========================================
# 1. 데이터 입력 (User Provided Data)
# ==========================================

# X축: Reservation Core Limit
cores = [1, 2, 4, 8, 12, 14]

# Y축: Actual RPS (Requests Per Second)
# Column 2: Random Request (search_only.lua)
rps_random = [350, 478, 715, 982, 1114, 1164]

# Column 3: Fixed Request (fixed.lua)
rps_fixed = [337, 470, 678, 836, 929, 949]

# ==========================================
# 2. 그래프 그리기
# ==========================================

fig, ax = plt.subplots(figsize=(12, 7))

# 1. Random Request Line (Blue)
ax.plot(cores, rps_random, marker='o', markersize=8, color='tab:blue', linewidth=2.5, label='Random Requests (Standard)')

# 2. Fixed Request Line (Red, Dashed)
ax.plot(cores, rps_fixed, marker='^', markersize=8, color='tab:red', linewidth=2.5, linestyle='--', label='Fixed Requests (High I/O)')


# 4. 그래프 스타일 설정
ax.set_xlabel('Reservation CPU Core Limit', fontsize=12, fontweight='bold')
ax.set_ylabel('Throughput (Requests Per Second)', fontsize=12, fontweight='bold')
ax.set_title('RPS Analysis: The Impact of Request Patterns on Scalability', fontsize=14, pad=20)
ax.grid(True, linestyle='--', alpha=0.6)
ax.set_xticks(cores)
ax.legend(loc='upper left', fontsize=11)

# 값 표시 (선택 사항)
for i, txt in enumerate(rps_random):
    ax.annotate(f'{txt}', (cores[i], rps_random[i]), textcoords="offset points", xytext=(0,8), ha='center', fontsize=9, color='tab:blue')

for i, txt in enumerate(rps_fixed):
    ax.annotate(f'{txt}', (cores[i], rps_fixed[i]), textcoords="offset points", xytext=(0,-15), ha='center', fontsize=9, color='tab:red')

# 저장 및 출력
plt.savefig('rps_comparison_graph.png', dpi=300)
print("✅ 그래프 저장 완료: rps_comparison_graph.png")
plt.show()