import matplotlib.pyplot as plt
import pandas as pd
import io

# 1. 사용자가 수집한 데이터 (collect_trend.sh 결과)
csv_data = """Duration(s),Avg_Latency,P99_Latency,Requests_Sec,Load_Average_1min
10,2.87s,6.16s,1259.26,8.09
20,8.59s,12.19s,1266.67,17.51
40,14.30s,23.54s,1245.82,24.15
80,26.45s,47.22s,1239.96,32.09
160,49.79s,1.56m,1240.92,38.35"""

# 2. 데이터 전처리 (단위 문자 's', 'm' 제거 및 초 단위 변환)
def parse_latency(val):
    if 'ms' in val:
        return float(val.replace('ms', '')) / 1000
    elif 'm' in val:
        return float(val.replace('m', '')) * 60
    elif 's' in val:
        return float(val.replace('s', ''))
    return float(val)

df = pd.read_csv(io.StringIO(csv_data))
df['Avg_Latency_Sec'] = df['Avg_Latency'].apply(parse_latency)
df['P99_Latency_Sec'] = df['P99_Latency'].apply(parse_latency)

# 3. 그래프 그리기 설정
fig, ax1 = plt.subplots(figsize=(12, 7))

# [왼쪽 Y축] Latency (선 그래프)
color_lat = 'tab:red'
ax1.set_xlabel('Test Duration (seconds)', fontsize=12, fontweight='bold')
ax1.set_ylabel('Latency (seconds)', color=color_lat, fontsize=12, fontweight='bold')
ax1.plot(df['Duration(s)'], df['Avg_Latency_Sec'], color=color_lat, marker='o', linewidth=2, label='Avg Latency')
ax1.plot(df['Duration(s)'], df['P99_Latency_Sec'], color='darkred', marker='x', linestyle='--', linewidth=1.5, label='P99 Latency')
ax1.tick_params(axis='y', labelcolor=color_lat)
ax1.grid(True, linestyle='--', alpha=0.5)
ax1.legend(loc='upper left', bbox_to_anchor=(0, 0.9))

# [오른쪽 Y축] Load Average (막대/선 그래프)
ax2 = ax1.twinx()
color_load = 'tab:blue'
ax2.set_ylabel('Load Average (1min)', color=color_load, fontsize=12, fontweight='bold')
ax2.plot(df['Duration(s)'], df['Load_Average_1min'], color=color_load, marker='s', linestyle='-', linewidth=2, label='Load Average')
ax2.tick_params(axis='y', labelcolor=color_load)

# [기준선] CPU 코어 개수 (36개) - Saturation 지점 표시
saturation_point = 36
ax2.axhline(y=saturation_point, color='green', linestyle=':', linewidth=3, label=f'CPU Cores ({saturation_point})')
ax2.text(df['Duration(s)'].min(), saturation_point + 1, '  Saturation Point (36 Cores)', color='green', fontweight='bold', va='bottom')

# 범례 및 타이틀
ax2.legend(loc='upper left', bbox_to_anchor=(0, 0.8))
plt.title('Proof of Saturation: Duration vs Latency & Load (Wait Time Explosion)', fontsize=14, pad=20)

# 4. [중요] 그래프 파일로 저장
filename = 'saturation_proof_graph.png'
plt.savefig(filename, dpi=300, bbox_inches='tight')
print(f"✅ 그래프가 '{filename}' 파일로 성공적으로 저장되었습니다.")

# 화면에 띄우기 (GUI 환경인 경우 주석 해제)
# plt.show()