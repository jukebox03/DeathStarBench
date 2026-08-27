import matplotlib.pyplot as plt

# 1. 데이터 설정 (원본 데이터)
target_rps = [2000, 4000, 8000, 10000, 10500, 11000, 12000, 16000]
actual_rps = [1989, 3981, 7995, 9991, 10485, 10470, 10537, 10393]
avg_latency_ms = [4.12, 3.58, 10.43, 27.82, 127.11, 1540, 4350, 12220]
p99_latency_ms = [10.32, 9.85, 23.18, 85.76, 394.49, 2790, 7320, 20820]

# --- 그래프 1: Throughput & Latency 종합 분석 ---
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

# 좌측: Throughput (Target vs Actual)
ax1.plot(target_rps, actual_rps, marker='o', linestyle='-', color='#1f77b4', linewidth=2, label='Actual Throughput')
ax1.plot(target_rps, target_rps, linestyle='--', color='gray', alpha=0.7, label='Ideal Scalability (1:1)')
ax1.set_title('Throughput Analysis', fontsize=14, fontweight='bold', pad=15)
ax1.set_xlabel('Targeted RPS (-R)', fontsize=12)
ax1.set_ylabel('Actual RPS', fontsize=12)
ax1.legend(loc='upper left')
ax1.grid(True, linestyle=':', alpha=0.6)

# 우측: Latency (Log Scale)
ax2.plot(target_rps, avg_latency_ms, marker='s', linestyle='-', color='#d62728', linewidth=2, label='Avg Latency')
ax2.plot(target_rps, p99_latency_ms, marker='^', linestyle='-', color='#ff7f0e', linewidth=2, label='p99 Latency')
ax2.set_yscale('log')
ax2.set_title('Latency vs Load (Log Scale)', fontsize=14, fontweight='bold', pad=15)
ax2.set_xlabel('Targeted RPS (-R)', fontsize=12)
ax2.set_ylabel('Latency (ms)', fontsize=12)
ax2.legend(loc='upper left')
ax2.grid(True, which='both', linestyle=':', alpha=0.6)

plt.tight_layout()
# 파일 저장 (고해상도)
plt.savefig('recommendation_performance_summary.png', dpi=300)
print("Saved: recommendation_performance_summary.png")
plt.show()


# --- 그래프 2: Hockey-Stick Curve (Latency vs Throughput) ---
plt.figure(figsize=(10, 7))
plt.plot(actual_rps, avg_latency_ms, marker='D', linestyle='-', color='#9467bd', linewidth=2.5, markersize=8)
plt.yscale('log')
plt.title('Hocky-stick Curve: System Saturation Point', fontsize=15, fontweight='bold', pad=20)
plt.xlabel('Actual Throughput (RPS)', fontsize=12)
plt.ylabel('Latency (ms - Log Scale)', fontsize=12)
plt.grid(True, which='both', linestyle='--', alpha=0.5)

# 임계점 표시 (Annotation)
plt.annotate('System Collapse Point\n(~10,500 RPS)', 
             xy=(10485, 127.11), 
             xytext=(5000, 1000),
             fontsize=11,
             color='red',
             fontweight='bold',
             arrowprops=dict(facecolor='red', shrink=0.05, width=2, headwidth=8))

plt.tight_layout()
# 파일 저장
plt.savefig('recommendation_hockey_stick.png', dpi=300)
print("Saved: recommendation_hockey_stick.png")
plt.show()