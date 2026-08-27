import matplotlib.pyplot as plt
import pandas as pd

# 1. 최신 데이터 정의 (All Verified)
# 단위: 초 (Total Seconds)
raw_data = {
    "20k": { # Verified
        "Requests": 591646,
        "gRPC Control Buffer": 33.68,
        "gRPC Picker (Connection)": 10.68,
        "Context Cancellation": 2.07,
        "Tracing (Jaeger)": 6.00,
        "Others": 5.00
    },
    "40k": { # Verified
        "Requests": 1183412,
        "gRPC Control Buffer": 81.88,
        "gRPC Picker (Connection)": 12.01,
        "Context Cancellation": 2.60,
        "Tracing (Jaeger)": 5.71,
        "Others": 15.00
    },
    "60k": { # Verified
        "Requests": 1780074,
        "gRPC Control Buffer": 490.00, 
        "gRPC Picker (Connection)": 35.00,
        "Context Cancellation": 20.61,
        "Tracing (Jaeger)": 10.00,
        "Others": 1.41
    },
    "80k": { # Verified
        "Requests": 2367398,
        "gRPC Control Buffer": 2070.00, 
        "gRPC Picker (Connection)": 63.00,
        "Context Cancellation": 2.77,
        "Tracing (Jaeger)": 15.00,
        "Others": 143.00
    },
    "100k": { # Verified
        "Requests": 2964333,
        "gRPC Control Buffer": 2070.00, 
        "gRPC Picker (Connection)": 62.79,
        "Context Cancellation": 153.82,
        "Tracing (Jaeger)": 15.00,
        "Others": 200.00 
    },
    "120k": { # NEW VERIFIED DATA (3,195,451 reqs)
        "Requests": 3195451,
        # Trace 합산: NewStream(158.33) + Write(113.08) + get(2.81) + ...
        "gRPC Control Buffer": 280.00, 
        # Trace 합산: getReadyTransport(91.60) + pick(79.16)
        "gRPC Picker (Connection)": 170.76,
        # Trace 합산: Context Err(13.34)
        "Context Cancellation": 13.34,
        # Trace 합산: Tracing 관련
        "Tracing (Jaeger)": 10.00,
        # Trace 합산: 기타
        "Others": 239.78 
    }
}

# 2. 데이터 가공
processed_rows = []
for label, data in raw_data.items():
    req_count = data["Requests"]
    for component, time_sec in data.items():
        if component == "Requests": continue
        time_us = (time_sec / req_count) * 1_000_000
        processed_rows.append({
            "Load": label,
            "Component": component,
            "Time_us": time_us
        })

df = pd.DataFrame(processed_rows)
df_pivot = df.pivot(index='Load', columns='Component', values='Time_us')
df_pivot = df_pivot.reindex(["20k", "40k", "60k", "80k", "100k", "120k"])
column_order = ["gRPC Control Buffer", "gRPC Picker (Connection)", "Context Cancellation", "Tracing (Jaeger)", "Others"]
df_pivot = df_pivot[column_order]

# 3. 그래프 그리기
plt.figure(figsize=(12, 7))
colors = ['#d62728', '#ff7f0e', '#2ca02c', '#1f77b4', '#7f7f7f']

ax = df_pivot.plot(kind='bar', stacked=True, color=colors, figsize=(12, 7), width=0.6)

plt.title('Mutex Lock Wait Time per Request (Frontend)', fontsize=15, pad=20)
plt.xlabel('Request Load Scenario', fontsize=12)
plt.ylabel('Wait Time per Request (µs)', fontsize=12)
plt.xticks(rotation=0)
plt.grid(axis='y', linestyle='--', alpha=0.5)
plt.legend(title='Component', bbox_to_anchor=(1.02, 1), loc='upper left')

for c in ax.containers:
    labels = [f'{v.get_height():.1f}' if v.get_height() > 5 else '' for v in c]
    ax.bar_label(c, labels=labels, label_type='center', color='white', fontsize=8, weight='bold')

plt.tight_layout()
plt.savefig('mutex_frontend.png')
print("Saved: 'mutex_frontend.png'")