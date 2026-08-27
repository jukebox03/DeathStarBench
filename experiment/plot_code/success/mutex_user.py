import matplotlib.pyplot as plt
import pandas as pd

# 1. User Service 데이터 정의
# 단위: 초 (Total Seconds)
raw_data = {
    "20k": {
        "Requests": 595647,
        "gRPC Control Buffer": 1.7,
    },
    "40k": {
        "Requests": 1191500,
        "gRPC Control Buffer": 3.0,
    },
    "60k": {
        "Requests": 1787602,
        "gRPC Control Buffer": 9.83,
    },
    "80k": {
        "Requests": 2385588,
        "gRPC Control Buffer": 202.8,
    },
    "100k": {
        "Requests": 2981602,
        "gRPC Control Buffer": 154.6,
    },
    "120k": {
        "Requests": 3144218,
        "gRPC Control Buffer": 173.2,
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

# 3. 그래프 그리기
plt.figure(figsize=(12, 7))
colors = ['#d62728']

ax = df_pivot.plot(kind='bar', stacked=True, color=colors, figsize=(12, 7), width=0.6)

plt.title('Mutex Lock Wait Time per Request (User Service)', fontsize=15, pad=20)
plt.xlabel('Request Load Scenario', fontsize=12)
plt.ylabel('Wait Time per Request (µs)', fontsize=12)
plt.xticks(rotation=0)
plt.grid(axis='y', linestyle='--', alpha=0.5)
plt.legend(title='Component', bbox_to_anchor=(1.02, 1), loc='upper left')

for c in ax.containers:
    labels = [f'{v.get_height():.1f}' if v.get_height() > 1 else '' for v in c]
    ax.bar_label(c, labels=labels, label_type='center', color='white', fontsize=9, weight='bold')

plt.tight_layout()
plt.savefig('mutex_user.png')
print("Saved: 'mutex_user.png'")