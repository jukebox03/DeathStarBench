#!/usr/bin/env python3
"""
Phase 3: TCP 메트릭 분석
Phase 4: CPU vs RPS 관계
"""

import matplotlib.pyplot as plt
import numpy as np

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.size'] = 12
plt.rcParams['axes.labelsize'] = 14
plt.rcParams['axes.titlesize'] = 16

# =============================================================================
# Phase 3: TCP 메트릭 데이터
# =============================================================================
phase3_data = {
    'metrics': [
        'Segments\nRetransmitted',
        'TCP Loss\nProbes', 
        'Delayed\nACKs Sent',
        'Resets\nSent',
        'Connection\nResets Recv',
        'Active Conn\nOpenings'
    ],
    'before': [2381654, 2332705, 18172133, 1173459, 1049877, 1974793],
    'after': [2486697, 2437746, 19026962, 1173956, 1050350, 1978528],
}
phase3_data['delta'] = [a - b for a, b in zip(phase3_data['after'], phase3_data['before'])]

# 핵심 에러 메트릭만 별도로
phase3_errors = {
    'metrics': ['Retransmissions', 'Loss Probes', 'Resets Sent', 'Resets Received'],
    'delta': [105043, 105041, 497, 473]
}


def plot_phase3_tcp_delta():
    """Phase 3: TCP 메트릭 변화량"""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    metrics = phase3_data['metrics']
    delta = phase3_data['delta']
    
    colors = ['#E94F37' if d > 10000 else '#2E86AB' for d in delta]
    bars = ax.bar(range(len(metrics)), delta, color=colors, edgecolor='black', alpha=0.8)
    
    # 값 표시
    for bar, d in zip(bars, delta):
        height = bar.get_height()
        ax.annotate(f'+{d:,}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    ax.set_xlabel('TCP Metric')
    ax.set_ylabel('Delta (After - Before)')
    ax.set_title('Phase 3: TCP Metrics Change During Load Test\n(8 ghz instances, 60s, ~100k RPS)')
    ax.set_xticks(range(len(metrics)))
    ax.set_xticklabels(metrics)
    ax.grid(True, axis='y', alpha=0.3)
    
    # 범례
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#E94F37', label='High impact (>10k)'),
        Patch(facecolor='#2E86AB', label='Low impact (<10k)')
    ]
    ax.legend(handles=legend_elements, loc='upper right')
    
    plt.tight_layout()
    plt.savefig('phase3_tcp_metrics.png', dpi=150, bbox_inches='tight')
    print("✅ Phase 3 그래프 저장: phase3_tcp_metrics.png")
    plt.close()


def plot_phase3_errors_focus():
    """Phase 3: TCP 에러 메트릭 집중 분석"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    metrics = phase3_errors['metrics']
    delta = phase3_errors['delta']
    
    colors = ['#E94F37', '#E94F37', '#F4A261', '#F4A261']
    bars = ax.barh(range(len(metrics)), delta, color=colors, edgecolor='black', alpha=0.8)
    
    # 값 표시
    for bar, d in zip(bars, delta):
        width = bar.get_width()
        ax.annotate(f'+{d:,}',
                    xy=(width, bar.get_y() + bar.get_height() / 2),
                    xytext=(5, 0), textcoords="offset points",
                    ha='left', va='center', fontsize=12, fontweight='bold')
    
    ax.set_xlabel('Count Increase During Test')
    ax.set_ylabel('TCP Error Metric')
    ax.set_title('Phase 3: TCP Errors During 60s Load Test\n(Evidence of network-level stress)')
    ax.set_yticks(range(len(metrics)))
    ax.set_yticklabels(metrics)
    ax.grid(True, axis='x', alpha=0.3)
    
    # 주석
    ax.text(0.95, 0.05, 
            '105k retransmissions in 60s\n= ~1,750 retrans/sec\n→ TCP layer under stress',
            transform=ax.transAxes, fontsize=10,
            verticalalignment='bottom', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig('phase3_tcp_errors.png', dpi=150, bbox_inches='tight')
    print("✅ Phase 3 에러 그래프 저장: phase3_tcp_errors.png")
    plt.close()



def plot_phase4_cpu_vs_rps():
    """Phase 4: CPU 사용량 vs RPS"""
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    rps = phase4_data['rps']
    cpu_cores = phase4_data['user_cpu_cores']
    cpu_percent = phase4_data['total_cpu_percent']
    
    # User CPU cores (왼쪽 축)
    color1 = '#2E86AB'
    ax1.set_xlabel('RPS (Requests per Second)')
    ax1.set_ylabel('User Service CPU (cores)', color=color1)
    line1 = ax1.plot(rps, cpu_cores, 'o-', color=color1, linewidth=2, markersize=10, label='User CPU')
    ax1.tick_params(axis='y', labelcolor=color1)
    
    # 포화 영역 표시
    ax1.axvspan(95000, 110000, alpha=0.2, color='red', label='Saturation Zone')
    
    # Total CPU percent (오른쪽 축)
    ax2 = ax1.twinx()
    color2 = '#E94F37'
    ax2.set_ylabel('Total System CPU (%)', color=color2)
    line2 = ax2.plot(rps, cpu_percent, 's--', color=color2, linewidth=2, markersize=8, label='Total CPU %')
    ax2.tick_params(axis='y', labelcolor=color2)
    ax2.set_ylim(0, 100)
    
    # 100% 기준선
    ax2.axhline(y=100, color='gray', linestyle=':', alpha=0.5)
    
    # 범례
    lines = line1 + line2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='upper left')
    
    ax1.set_title('Phase 4: CPU Usage vs Throughput\n(CPU not saturated at max RPS)')
    ax1.grid(True, alpha=0.3)
    
    # 주석
    ax1.annotate('CPU ~82% at max RPS\n→ Not CPU-bound!',
                 xy=(100000, 11.0), xytext=(70000, 9),
                 fontsize=11, ha='center',
                 arrowprops=dict(arrowstyle='->', color='black'),
                 bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))
    
    plt.tight_layout()
    plt.savefig('phase4_cpu_vs_rps.png', dpi=150, bbox_inches='tight')
    print("✅ Phase 4 그래프 저장: phase4_cpu_vs_rps.png")
    plt.close()

if __name__ == '__main__':
    print("🎨 Phase 3 그래프 생성...")
    print()
    
    plot_phase3_tcp_delta()
    plot_phase3_errors_focus()
    
    print()
    print("=" * 50)
    print("📊 생성된 파일:")
    print("  - phase3_tcp_metrics.png")
    print("  - phase3_tcp_errors.png")
    print("=" * 50)