import matplotlib.pyplot as plt
import numpy as np

# Istio Latency Comparison Data
# Without Istio vs With Istio @ closed loop (t=1, c=1), 0-17 cores
data = {
    "Without Istio": {
        "apis": ["POST /user", "GET /recommendations", "GET /hotels"],
        "avg": [0.178, 0.399, 1.30],
        "p50": [0.162, 0.370, 1.24],
        "p99": [0.599, 0.90, 2.19],
    },
    "With Istio": {
        "apis": ["POST /user", "GET /recommendations", "GET /hotels"],
        "avg": [0.607, 1.56, 3.53],
        "p50": [0.564, 1.52, 3.46],
        "p99": [1.21, 2.21, 4.67],
    },
}

# Calculate overhead percentages for annotations
overhead = {
    "POST /user": "+241%",
    "GET /recommendations": "+291%",
    "GET /hotels": "+172%",
}

plt.figure(figsize=(10, 7))

apis = data["Without Istio"]["apis"]
x = np.arange(len(apis))
width = 0.35

# Bar colors matching the reference image style
color_no_istio = '#1f77b4'  # Blue
color_with_istio = '#ff7f0e'  # Orange

bars1 = plt.bar(x - width/2, data["Without Istio"]["avg"], width, 
                label="Without Istio", color=color_no_istio, edgecolor='black', linewidth=0.5)
bars2 = plt.bar(x + width/2, data["With Istio"]["avg"], width, 
                label="With Istio", color=color_with_istio, edgecolor='black', linewidth=0.5)

# Add value labels on bars
for bar in bars1:
    height = bar.get_height()
    plt.annotate(f'{height:.2f}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=9)

for i, bar in enumerate(bars2):
    height = bar.get_height()
    api = apis[i]
    plt.annotate(f'{height:.2f}\n({overhead[api]})',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=9, color=color_with_istio)

# Add Insight Text Box
ax = plt.gca()
info_text = (
    "Insight: Istio Sidecar Overhead\n"
    "• POST /user (2 hops): +241%\n"
    "• GET /recommendations (3 hops): +291%\n"
    "• GET /hotels (5+ hops): +172%"
)
plt.text(0.01, 0.89, info_text, transform=ax.transAxes, fontsize=9,
         verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.2))

plt.xlabel("API Endpoint")
plt.ylabel("Average Latency (ms)")
plt.title("Istio Latency Overhead: Average Latency Comparison\n(DeathStarBench Hotel Reservation, closed loop t=1 c=1, 0-17 cores)")
plt.xticks(x, apis)
plt.grid(True, alpha=0.3, axis='y')
plt.legend(loc="upper left")
plt.tight_layout()
plt.savefig("istio_latency_comparison_wrk.png", dpi=200)

print("Saved: istio_latency_comparison_wrk.png")