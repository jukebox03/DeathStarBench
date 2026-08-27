import matplotlib.pyplot as plt
import numpy as np

# Data from measurements (averages of 3 runs)
# Format: {API: {service: (app, proxy, replica)}}

data = {
    "POST /user": {
        "frontend": (303, 1523, 12),
        "user": (201, 924, 6),
    },
    "GET /recommendations": {
        "frontend": (371, 841, 6),
        "recommendation": (250, 843, 6),
        "profile": (298, 895, 6),
    },
    "GET /hotels": {
        "frontend": (436, 813, 4),
        "geo": (142, 353, 1),
        "profile": (309, 459, 2),
        "rate": (346, 680, 3),
        "reservation": (356, 659, 3),
        "search": (376, 758, 3),
    },
}

# Health check baseline per replica (from idle services)
HEALTH_CHECK_PER_REPLICA = 117  # usec/req

# Calculate totals for each API
results = {}
for api, services in data.items():
    total_app = 0
    total_proxy = 0
    total_proxy_corrected = 0
    
    for service, (app, proxy, replica) in services.items():
        total_app += app
        total_proxy += proxy
        health_check = HEALTH_CHECK_PER_REPLICA * replica
        corrected_proxy = max(0, proxy - health_check)  # Ensure non-negative
        total_proxy_corrected += corrected_proxy
    
    results[api] = {
        "app": total_app,
        "proxy_corrected": total_proxy_corrected,
        "proxy": total_proxy,
    }

# Plotting
fig, ax = plt.subplots(figsize=(10, 7))

apis = list(results.keys())
x = np.arange(len(apis))
width = 0.25

# Bar data
app_only = [results[api]["app"] for api in apis]
app_plus_corrected = [results[api]["app"] + results[api]["proxy_corrected"] for api in apis]
app_plus_proxy = [results[api]["app"] + results[api]["proxy"] for api in apis]

# Create bars
bars1 = ax.bar(x - width, app_only, width, label='App Only', color='#2ecc71', edgecolor='black')
bars2 = ax.bar(x, app_plus_corrected, width, label='App + Sidecar (corrected)', color='#3498db', edgecolor='black')
bars3 = ax.bar(x + width, app_plus_proxy, width, label='App + Sidecar (raw)', color='#e74c3c', edgecolor='black')

# Add value labels on bars
def add_labels(bars):
    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{int(height)}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9)

add_labels(bars1)
add_labels(bars2)
add_labels(bars3)

# Formatting
ax.set_xlabel('API', fontsize=12)
ax.set_ylabel('CPU Usage (usec/req)', fontsize=12)
ax.set_title('CPU Usage per Request: App vs Sidecar Overhead\n(100 RPS, Health Check Corrected with 117 usec/replica)', fontsize=12)
ax.set_xticks(x)
ax.set_xticklabels(apis, fontsize=10)
ax.legend(loc='upper left', fontsize=10)
ax.grid(True, alpha=0.3, axis='y')

# Add insight text box (below legend on the left)
info_text = (
    "Correction Method:\n"
    "• Idle sidecar baseline: 117 usec/req per replica\n"
    "• Corrected = Raw Proxy - (117 × replica count)\n"
    "• High replica count → larger correction"
)
ax.text(0.02, 0.75, info_text, transform=ax.transAxes, fontsize=9,
        verticalalignment='top', horizontalalignment='left',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

plt.tight_layout()
plt.savefig("istio_cpu_usage_per_request_wrk2.png", dpi=200)
print("Saved: istio_cpu_usage_per_request_wrk2.png")

# Print summary table
print("\n=== Summary Table ===")
print(f"{'API':<25} {'App':>10} {'Corrected':>12} {'Raw Proxy':>12} {'Correction':>12}")
print("-" * 75)
for api in apis:
    r = results[api]
    correction = r["proxy"] - r["proxy_corrected"]
    print(f"{api:<25} {r['app']:>10} {r['proxy_corrected']:>12} {r['proxy']:>12} {correction:>12}")