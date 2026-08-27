import matplotlib.pyplot as plt
import numpy as np

# Data Extraction from user provided pprof analysis (Normalized Ratios)
loads = ['20k', '40k', '60k', '80k', '100k', '120k']

# Ratios (%) based on Total Block Time
# ControlBuffer: The initial bottleneck
control_buffer = [1.67, 1.31, 2.22, 2.81, 0.65, 0.07]

# Picker + Transport: The late-stage bottleneck (Connection Starvation)
# (Sum of getReadyTransport + pick + getTransport)
picker = [0.24, 0.14, 0.20, 0.02, 0.38, 0.14] 

# Context Cancellation: The symptom of failure
context_cancel = [0.19, 0.07, 0.05, 0.24, 0.08, 0.08]

x = np.arange(len(loads))
width = 0.6

fig, ax = plt.subplots(figsize=(12, 7))

# Plotting Stacked Bars
p1 = ax.bar(x, control_buffer, width, label='Control Buffer (Data Transfer)', color='#d62728', alpha=0.8) # Red
p2 = ax.bar(x, picker, width, bottom=control_buffer, label='Picker/Transport (Conn Selection)', color='#1f77b4', alpha=0.8) # Blue
p3 = ax.bar(x, context_cancel, width, bottom=np.array(control_buffer)+np.array(picker), label='Context Cancellation (Timeout)', color='#7f7f7f', alpha=0.8) # Grey

# Annotations
ax.set_ylabel('Ratio of Total Block Time (%)')
ax.set_title('Evolution of Mutex Bottlenecks: From "Congestion" to "Starvation"')
ax.set_xticks(x)
ax.set_xticklabels(loads)
ax.legend()
ax.grid(axis='y', linestyle='--', alpha=0.3)

# Adding trend arrows/text
ax.annotate('Buffer Contention\n(Traffic Jam)', xy=(3, 2.8), xytext=(1.5, 3.5),
            arrowprops=dict(facecolor='black', shrink=0.05, alpha=0.5), fontsize=10)

ax.annotate('Connection Starvation\n(Door Closed)', xy=(4, 0.8), xytext=(4.5, 2.0),
            arrowprops=dict(facecolor='black', shrink=0.05, alpha=0.5), fontsize=10)

plt.tight_layout()
plt.savefig('mutex_ratio_frontend.png')
print("Saved: 'mutex_ratio_frontend.png'")