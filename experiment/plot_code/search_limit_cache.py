import matplotlib.pyplot as plt
import numpy as np

# ==============================================================================
# DATA DEFINITION
# ==============================================================================
cores = np.array([1, 2, 4, 8, 12, 14])

# 1. RPS Comparison Data (Random vs Fixed vs Distributed)
rps_random = np.array([350, 478, 715, 982, 1114, 1164])
rps_fixed = np.array([337, 470, 678, 836, 929, 949])
rps_distributed = np.array([341, 476, 674, 818, 916, 975])

# 2. CPU Usage Data (Distributed 4-Keys Scenario) - Unit: Cores
cpu_reservation = np.array([999, 1984, 3877, 7122, 9436, 10413]) / 1000.0
cpu_rate = np.array([3513, 4969, 6728, 7881, 8133, 8293]) / 1000.0
cpu_memcached = np.array([368, 509, 692, 823, 874, 905]) / 1000.0


# ==============================================================================
# GRAPH 1: RPS Comparison (The "Paradox")
# ==============================================================================
def draw_rps_comparison():
    fig, ax = plt.subplots(figsize=(12, 7))

    # Plot Lines
    ax.plot(cores, rps_random, marker='o', markersize=9, color='tab:blue', linewidth=3, label='Random (Standard)')
    ax.plot(cores, rps_fixed, marker='^', markersize=9, color='tab:red', linewidth=2, linestyle='--', label='Fixed 1-Key (Lock Bottleneck)')
    ax.plot(cores, rps_distributed, marker='s', markersize=9, color='tab:green', linewidth=3, linestyle='-.', label='Distributed 4-Keys (Rate Saturation)')

    # Annotations
    # 1. 8-Core Divergence
    ax.annotate('Random wins!\n(Slower I/O protected Rate Service)', 
                xy=(14, 1164), xytext=(10, 1050),
                arrowprops=dict(facecolor='blue', shrink=0.05),
                fontsize=11, fontweight='bold', color='tab:blue', ha='center')

    # 2. Rate Wall
    ax.annotate('Rate Service Wall\n(Stuck at ~975 RPS)', 
                xy=(14, 975), xytext=(12, 850),
                arrowprops=dict(facecolor='red', shrink=0.05),
                fontsize=11, fontweight='bold', color='tab:red', ha='center')

    # Styling
    ax.set_title('RPS Analysis: Why "Optimal" Logic Failed to Scale', fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel('Reservation CPU Core Limit', fontsize=12, fontweight='bold')
    ax.set_ylabel('Throughput (Requests Per Second)', fontsize=12, fontweight='bold')
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.set_xticks(cores)
    ax.legend(loc='upper left', fontsize=11, framealpha=0.9, shadow=True)

    # Add Values (Selective)
    for i in [3, 5]: # 8, 14 cores
        ax.text(cores[i], rps_random[i]+25, f'{rps_random[i]}', ha='center', color='tab:blue', fontweight='bold')
        ax.text(cores[i], rps_distributed[i]-45, f'{rps_distributed[i]}', ha='center', color='tab:green', fontweight='bold')

    plt.tight_layout()
    plt.savefig('final_rps_comparison.png', dpi=300)
    print("✅ 그래프 1 저장 완료: final_rps_comparison.png")
    plt.close()


# ==============================================================================
# GRAPH 2: CPU Bottleneck Analysis (Why it failed)
# ==============================================================================
def draw_cpu_analysis():
    fig, ax = plt.subplots(figsize=(12, 7))

    # Plot Lines
    ax.plot(cores, cpu_reservation, marker='o', markersize=8, color='tab:blue', linewidth=2.5, label='Reservation (Target)')
    ax.plot(cores, cpu_rate, marker='s', markersize=8, color='tab:red', linewidth=3, linestyle='--', label='Rate Service (Bottleneck)')
    ax.plot(cores, cpu_memcached, marker='^', markersize=8, color='tab:green', linewidth=2, linestyle=':', label='Memcached')

    # Ideal Line
    ax.plot(cores, cores, color='gray', alpha=0.3, linestyle='-', label='Ideal Linear Scaling')

    # Annotations
    # 1. Rate Service Limit
    ax.axhline(y=8.3, color='red', linestyle=':', alpha=0.5)
    ax.text(1, 8.5, 'Physical Limit (~8.3 Cores)', color='red', fontsize=10, fontweight='bold')

    # 2. Reservation Divergence (Idle Time)
    ax.annotate('Reservation stops scaling\n(Waiting for Rate Service)', 
                xy=(12, 9.436), xytext=(8, 11),
                arrowprops=dict(facecolor='black', shrink=0.05),
                fontsize=10, fontweight='bold')

    # Styling
    ax.set_title('Resource Analysis: Identifying the "Rate" Bottleneck', fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel('Reservation CPU Core Limit', fontsize=12, fontweight='bold')
    ax.set_ylabel('CPU Usage (Cores)', fontsize=12, fontweight='bold')
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.set_xticks(cores)
    ax.legend(loc='upper left', fontsize=11, framealpha=0.9, shadow=True)

    plt.tight_layout()
    plt.savefig('final_cpu_bottleneck_analysis.png', dpi=300)
    print("✅ 그래프 2 저장 완료: final_cpu_bottleneck_analysis.png")
    plt.close()


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    draw_rps_comparison()
    draw_cpu_analysis()