import matplotlib.pyplot as plt
import pandas as pd

# 1. 원본 데이터 정의 (pprof 분석 결과)
# 단위: 초 (Total Seconds)
raw_data = {
    "20k": {
        "Requests": 593155,
        "gRPC Control Buffer": 85.48,
        "gRPC Picker (Connection)": 5.42,
        "Context Cancellation": 0.23,
        "Tracing (Jaeger)": 0.84,
        "Others": 1.31
    },
    "40k": { # CORRECTED DATA (1,183,412 reqs)
        "Requests": 1183412,
        # Trace 합산: NewStream(71.11) + Write(8.53) + get(2.24)
        "gRPC Control Buffer": 81.88,
        # Trace 합산: getReadyTransport(7.76) + pick(4.25)
        "gRPC Picker (Connection)": 12.01,
        # Trace 합산: Context Err(2.60)
        "Context Cancellation": 2.60,
        # Trace 합산: randomID(2.48) + Inject(1.54) + StartSpan(1.69)
        "Tracing (Jaeger)": 5.71,
        # Trace 합산: Sync.Pool 관련 등 나머지
        "Others": 15.00
    },
    "60k": {
        "Requests": 1777500,
        "gRPC Control Buffer": 563.33,
        "gRPC Picker (Connection)": 27.11,
        "Context Cancellation": 1.22,
        "Tracing (Jaeger)": 8.84,
        "Others": 20.16
    },
    "80k": {
        "Requests": 2371695,
        "gRPC Control Buffer": 773.04,
        "gRPC Picker (Connection)": 50.58,
        "Context Cancellation": 36.76,
        "Tracing (Jaeger)": 12.67,
        "Others": 25.96
    },
    "100k": {
        "Requests": 2960320,
        "gRPC Control Buffer": 414.38,
        "gRPC Picker (Connection)": 108.18,
        "Context Cancellation": 73.02,
        "Tracing (Jaeger)": 38.13,
        "Others": 14.92
    },
    "120k": {
        "Requests": 3327301,
        "gRPC Control Buffer": 110.95,
        "gRPC Picker (Connection)": 55.96,
        "Context Cancellation": 4.46,
        "Tracing (Jaeger)": 11.54,
        "Others": 1.75
    }
}

# 2. 데이터 가공: '초(Total Seconds)' -> '요청당 마이크로초(µs/Request)' 변환
processed_rows = []
for label, data in raw_data.items():
    req_count = data["Requests"]
    for component, time_sec in data.items():
        if component == "Requests": continue
        
        # 계산 공식: (총 시간 / 총 요청 수) * 1,000,000
        time_us = (time_sec / req_count) * 1_000_000
        processed_rows.append({
            "Load": label,
            "Component": component,
            "Time_us": time_us
        })

df = pd.DataFrame(processed_rows)

# 3. 그래프용 데이터 피벗
df_pivot = df.pivot(index='Load', columns='Component', values='Time_us')
load_order = ["20k", "40k", "60k", "80k", "100k", "120k"]
df_pivot = df_pivot.reindex(load_order)

# 스택 순서 정렬
column_order = [
    "gRPC Control Buffer", 
    "gRPC Picker (Connection)", 
    "Context Cancellation", 
    "Tracing (Jaeger)", 
    "Others"
]
df_pivot = df_pivot[column_order]

# 4. 그래프 그리기
plt.figure(figsize=(12, 7))
colors = ['#d62728', '#ff7f0e', '#2ca02c', '#1f77b4', '#7f7f7f']

ax = df_pivot.plot(kind='bar', stacked=True, color=colors, figsize=(12, 7), width=0.6)

plt.title('Mutex Lock Wait Time per Request (Baseline w/ Corrected 40k)', fontsize=15, pad=20)
plt.xlabel('Request Load Scenario', fontsize=12)
plt.ylabel('Wait Time per Request (µs)', fontsize=12)
plt.xticks(rotation=0)
plt.grid(axis='y', linestyle='--', alpha=0.5)
plt.legend(title='Component', bbox_to_anchor=(1.02, 1), loc='upper left')

# 수치 표시
for c in ax.containers:
    labels = [f'{v.get_height():.1f}' if v.get_height() > 5 else '' for v in c]
    ax.bar_label(c, labels=labels, label_type='center', color='white', fontsize=8, weight='bold')

plt.tight_layout()
plt.savefig('mutex_breakdown_final.png')
print("Saved: mutex_breakdown_final.png")