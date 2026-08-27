#!/usr/bin/env python3
"""
DeathStarBench User Service 성능 분석 그래프
Phase 1: Connection 수 vs RPS
Phase 2: ghz 인스턴스 수 vs RPS (Scaling Efficiency)
"""

import matplotlib.pyplot as plt
import numpy as np

# 스타일 설정
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.size'] = 12
plt.rcParams['axes.labelsize'] = 14
plt.rcParams['axes.titlesize'] = 16
plt.rcParams['figure.figsize'] = (10, 6)

# =============================================================================
# Phase 1: Connection 수 실험 데이터
# =============================================================================
phase1_data = {
    'connections': [1, 10, 50, 100, 200, 400],
    'rps': [74737.38, 95327.52, 89923.73, 85849.69, 80795.13, 76218.40],
    'avg_latency': [18.05, 7.99, 6.74, 6.36, 6.64, 7.54],
    'tcp_conns': [4, 40, 200, 400, 800, 1600]
}

# =============================================================================
# Phase 2: ghz 인스턴스 수 실험 데이터
# =============================================================================
phase2_data = {
    'instances': [1, 2, 4, 8, 16],
    'total_rps': [40800, 60000, 83300, 100422, 107679],
}
# 계산된 값
phase2_data['per_instance_rps'] = [r/i for r, i in zip(phase2_data['total_rps'], phase2_data['instances'])]
phase2_data['ideal_rps'] = [40800 * i for i in phase2_data['instances']]
phase2_data['efficiency'] = [r/ideal * 100 for r, ideal in zip(phase2_data['total_rps'], phase2_data['ideal_rps'])]


def plot_phase1_rps():
    """Phase 1: Connection 수 vs RPS"""
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    x = phase1_data['connections']
    rps = phase1_data['rps']
    latency = phase1_data['avg_latency']
    
    # RPS (왼쪽 축)
    color1 = '#2E86AB'
    ax1.set_xlabel('Number of Connections (per ghz instance)')
    ax1.set_ylabel('Total RPS', color=color1)
    line1 = ax1.plot(x, rps, 'o-', color=color1, linewidth=2, markersize=10, label='RPS')
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.set_xscale('log')
    
    # 최적점 강조
    optimal_idx = rps.index(max(rps))
    ax1.scatter([x[optimal_idx]], [rps[optimal_idx]], color='red', s=200, zorder=5, marker='*')
    ax1.annotate(f'Optimal: {x[optimal_idx]} conns\n{rps[optimal_idx]:,.0f} RPS', 
                 xy=(x[optimal_idx], rps[optimal_idx]),
                 xytext=(x[optimal_idx]*2, rps[optimal_idx]+5000),
                 fontsize=11, ha='left',
                 arrowprops=dict(arrowstyle='->', color='red'))
    
    # Latency (오른쪽 축)
    ax2 = ax1.twinx()
    color2 = '#E94F37'
    ax2.set_ylabel('Average Latency (ms)', color=color2)
    line2 = ax2.plot(x, latency, 's--', color=color2, linewidth=2, markersize=8, label='Latency')
    ax2.tick_params(axis='y', labelcolor=color2)
    
    # 범례
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper right')
    
    ax1.set_title('Phase 1: gRPC Connection Count vs Performance\n(4 ghz instances, User service direct call)')
    ax1.grid(True, alpha=0.3)
    
    # X축 틱 설정
    ax1.set_xticks(x)
    ax1.set_xticklabels(x)
    
    plt.tight_layout()
    plt.savefig('phase1_connections_vs_rps.png', dpi=150, bbox_inches='tight')
    plt.savefig('phase1_connections_vs_rps.pdf', bbox_inches='tight')
    print("✅ Phase 1 그래프 저장: phase1_connections_vs_rps.png/pdf")
    plt.close()


def plot_phase2_scaling():
    """Phase 2: ghz 인스턴스 수 vs RPS (Scaling)"""
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    x = phase2_data['instances']
    actual = phase2_data['total_rps']
    ideal = phase2_data['ideal_rps']
    
    # Actual vs Ideal RPS
    ax1.plot(x, ideal, 'o--', color='gray', linewidth=2, markersize=8, label='Ideal (Linear Scaling)', alpha=0.7)
    ax1.plot(x, actual, 's-', color='#2E86AB', linewidth=2, markersize=10, label='Actual RPS')
    
    # 차이 영역 채우기
    ax1.fill_between(x, actual, ideal, alpha=0.2, color='red', label='Scaling Loss')
    
    ax1.set_xlabel('Number of ghz Instances')
    ax1.set_ylabel('Total RPS')
    ax1.set_title('Phase 2: Client Scaling Efficiency\n(gRPC load generator instances vs throughput)')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # 값 표시
    for i, (xi, yi) in enumerate(zip(x, actual)):
        eff = phase2_data['efficiency'][i]
        ax1.annotate(f'{yi:,.0f}\n({eff:.0f}%)', 
                     xy=(xi, yi), xytext=(0, 10),
                     textcoords='offset points', ha='center', fontsize=9)
    
    ax1.set_xticks(x)
    ax1.set_ylim(0, max(ideal) * 1.1)
    
    plt.tight_layout()
    plt.savefig('phase2_scaling_efficiency.png', dpi=150, bbox_inches='tight')
    plt.savefig('phase2_scaling_efficiency.pdf', bbox_inches='tight')
    print("✅ Phase 2 그래프 저장: phase2_scaling_efficiency.png/pdf")
    plt.close()


def plot_phase2_efficiency_bar():
    """Phase 2: Scaling Efficiency 바 차트"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    x = phase2_data['instances']
    efficiency = phase2_data['efficiency']
    
    bars = ax.bar(range(len(x)), efficiency, color='#2E86AB', edgecolor='black', alpha=0.8)
    
    # 100% 기준선
    ax.axhline(y=100, color='red', linestyle='--', linewidth=2, label='Ideal (100%)')
    
    # 값 표시
    for bar, eff in zip(bars, efficiency):
        height = bar.get_height()
        ax.annotate(f'{eff:.1f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    ax.set_xlabel('Number of ghz Instances')
    ax.set_ylabel('Scaling Efficiency (%)')
    ax.set_title('Phase 2: Scaling Efficiency Degradation\n(Efficiency = Actual RPS / Ideal RPS × 100)')
    ax.set_xticks(range(len(x)))
    ax.set_xticklabels(x)
    ax.set_ylim(0, 120)
    ax.legend()
    ax.grid(True, axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('phase2_efficiency_bar.png', dpi=150, bbox_inches='tight')
    plt.savefig('phase2_efficiency_bar.pdf', bbox_inches='tight')
    print("✅ Phase 2 효율 바 차트 저장: phase2_efficiency_bar.png/pdf")
    plt.close()


def plot_combined_summary():
    """종합 요약 그래프"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # (0,0) Phase 1: Connections vs RPS
    ax = axes[0, 0]
    x = phase1_data['connections']
    rps = phase1_data['rps']
    ax.plot(x, rps, 'o-', color='#2E86AB', linewidth=2, markersize=10)
    optimal_idx = rps.index(max(rps))
    ax.scatter([x[optimal_idx]], [rps[optimal_idx]], color='red', s=200, zorder=5, marker='*')
    ax.set_xlabel('Connections per ghz')
    ax.set_ylabel('Total RPS')
    ax.set_title('(A) Connection Count vs RPS')
    ax.set_xscale('log')
    ax.set_xticks(x)
    ax.set_xticklabels(x)
    ax.grid(True, alpha=0.3)
    
    # (0,1) Phase 1: Connections vs Latency
    ax = axes[0, 1]
    latency = phase1_data['avg_latency']
    ax.plot(x, latency, 's-', color='#E94F37', linewidth=2, markersize=10)
    ax.set_xlabel('Connections per ghz')
    ax.set_ylabel('Average Latency (ms)')
    ax.set_title('(B) Connection Count vs Latency')
    ax.set_xscale('log')
    ax.set_xticks(x)
    ax.set_xticklabels(x)
    ax.grid(True, alpha=0.3)
    
    # (1,0) Phase 2: Scaling
    ax = axes[1, 0]
    x2 = phase2_data['instances']
    actual = phase2_data['total_rps']
    ideal = phase2_data['ideal_rps']
    ax.plot(x2, ideal, 'o--', color='gray', linewidth=2, markersize=8, label='Ideal', alpha=0.7)
    ax.plot(x2, actual, 's-', color='#2E86AB', linewidth=2, markersize=10, label='Actual')
    ax.fill_between(x2, actual, ideal, alpha=0.2, color='red')
    ax.set_xlabel('ghz Instances')
    ax.set_ylabel('Total RPS')
    ax.set_title('(C) Client Scaling: Actual vs Ideal')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xticks(x2)
    
    # (1,1) Phase 2: Efficiency
    ax = axes[1, 1]
    efficiency = phase2_data['efficiency']
    bars = ax.bar(range(len(x2)), efficiency, color='#2E86AB', edgecolor='black', alpha=0.8)
    ax.axhline(y=100, color='red', linestyle='--', linewidth=2)
    for bar, eff in zip(bars, efficiency):
        ax.annotate(f'{eff:.0f}%', xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                    xytext=(0, 3), textcoords="offset points", ha='center', fontsize=10)
    ax.set_xlabel('ghz Instances')
    ax.set_ylabel('Efficiency (%)')
    ax.set_title('(D) Scaling Efficiency Degradation')
    ax.set_xticks(range(len(x2)))
    ax.set_xticklabels(x2)
    ax.set_ylim(0, 120)
    ax.grid(True, axis='y', alpha=0.3)
    
    plt.suptitle('DeathStarBench User Service: gRPC Performance Analysis', fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig('combined_summary.png', dpi=150, bbox_inches='tight')
    plt.savefig('combined_summary.pdf', bbox_inches='tight')
    print("✅ 종합 요약 그래프 저장: combined_summary.png/pdf")
    plt.close()


if __name__ == '__main__':
    print("🎨 그래프 생성 시작...")
    print()
    
    plot_phase1_rps()
    plot_phase2_scaling()
    plot_phase2_efficiency_bar()
    plot_combined_summary()
    
    print()
    print("=" * 50)
    print("📊 생성된 파일:")
    print("  - phase1_connections_vs_rps.png/pdf")
    print("  - phase2_scaling_efficiency.png/pdf")
    print("  - phase2_efficiency_bar.png/pdf")
    print("  - combined_summary.png/pdf")
    print("=" * 50)