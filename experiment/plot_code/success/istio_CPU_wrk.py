import matplotlib.pyplot as plt
import numpy as np

# Data from measurements
# Format: {API: {service: (app_usec_per_req, proxy_usec_per_req, replica)}}

data = {
    "POST /user": {
        "frontend": (161.57, 102.03, 12),
        "user": (139.25, 244.29, 6),
    },
    "GET /recommendations": {
        "frontend": (274.37, 145.38, 6),
        "recommendation": (205.17, 278.72, 6),
        "profile": (242.90, 338.37, 6),
    },
    "GET /hotels": {
        "frontend": (539.12, 284.76, 4),
        "geo": (207.19, 294.12, 1),
        "profile": (342.68, 377.36, 2),
        "rate": (341.86, 378.27, 3),
        "reservation": (369.33, 411.29, 3),
        "search": (494.14, 469.14, 3),
    },
}

# Calculate totals for each API
results = {}
for api, services in data.items():
    total_app = 0
    total_proxy = 0
    total_replicas = 0
    
    for service, (app, proxy, replica) in services.items():
        total_app += app
        total_proxy += proxy
        total_replicas += replica
    
    results[api] = {
        "app": total_app,
        "proxy": total_proxy,
        "total": total_app + total_proxy,
        "replicas": total_replicas,
        "proxy_ratio": total_proxy / (total_app + total_proxy) * 100,
    }

# Plotting
fig, ax = plt.subplots(figsize=(10, 7))

apis = list(results.keys())
x = np.arange(len(apis))
width = 0.35

# Bar data
app_values = [results[api]["app"] for api in apis]
proxy_values = [results[api]["proxy"] for api in apis]

# Create stacked bars
bars1 = ax.bar(x, app_values, width, label='App', color='#2ecc71', edgecolor='black')
bars2 = ax.bar(x, proxy_values, width, bottom=app_values, label='Sidecar (Proxy)', color='#e74c3c', edgecolor='black')

# Add value labels
for i, api in enumerate(apis):
    app_val = results[api]["app"]
    proxy_val = results[api]["proxy"]
    total_val = results[api]["total"]
    proxy_ratio = results[api]["proxy_ratio"]
    
    # App label (middle of app bar)
    ax.annotate(f'{app_val:.0f}',
                xy=(x[i], app_val / 2),
                ha='center', va='center', fontsize=9, color='white', fontweight='bold')
    
    # Proxy label (middle of proxy bar)
    ax.annotate(f'{proxy_val:.0f}',
                xy=(x[i], app_val + proxy_val / 2),
                ha='center', va='center', fontsize=9, color='white', fontweight='bold')
    
    # Total label (top)
    ax.annotate(f'Total: {total_val:.0f}\n({proxy_ratio:.0f}% proxy)',
                xy=(x[i], total_val),
                xytext=(0, 5),
                textcoords="offset points",
                ha='center', va='bottom', fontsize=9)

# Formatting
ax.set_xlabel('API Endpoint', fontsize=12)
ax.set_ylabel('CPU Usage (usec/req)', fontsize=12)
ax.set_title('Istio Sidecar CPU Overhead per Request\n(Baseline Corrected, Closed-Loop Measurement)', fontsize=12)
ax.set_xticks(x)
ax.set_xticklabels(apis, fontsize=10)
ax.legend(loc='upper left', fontsize=10)
ax.grid(True, alpha=0.3, axis='y')

# Add insight text box
info_text = (
    "Key Findings:\n"
    f"• POST /user: {results['POST /user']['proxy_ratio']:.0f}% sidecar overhead\n"
    f"• GET /recommendations: {results['GET /recommendations']['proxy_ratio']:.0f}% sidecar overhead\n"
    f"• GET /hotels: {results['GET /hotels']['proxy_ratio']:.0f}% sidecar overhead\n"
    "• More hops → higher total CPU"
)
ax.text(0.02, 0.75, info_text, transform=ax.transAxes, fontsize=9,
        verticalalignment='top', horizontalalignment='left',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

plt.tight_layout()
plt.savefig("istio_cpu_overhead_per_request_wrk.png", dpi=200)
print("Saved: istio_cpu_overhead_per_request_wrk.png")

# Print summary table
print("\n=== Summary Table ===")
print(f"{'API':<25} {'App':>10} {'Proxy':>10} {'Total':>10} {'Proxy %':>10} {'Replicas':>10}")
print("-" * 80)
for api in apis:
    r = results[api]
    print(f"{api:<25} {r['app']:>10.2f} {r['proxy']:>10.2f} {r['total']:>10.2f} {r['proxy_ratio']:>9.1f}% {r['replicas']:>10}")

# Print per-service breakdown
print("\n=== Per-Service Breakdown ===")
for api, services in data.items():
    print(f"\n{api}:")
    print(f"  {'Service':<20} {'App':>10} {'Proxy':>10} {'Total':>10} {'Replicas':>10}")
    print(f"  {'-'*60}")
    for service, (app, proxy, replica) in services.items():
        total = app + proxy
        print(f"  {service:<20} {app:>10.2f} {proxy:>10.2f} {total:>10.2f} {replica:>10}")