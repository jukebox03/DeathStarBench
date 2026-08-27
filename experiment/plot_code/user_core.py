import pandas as pd
import matplotlib.pyplot as plt

# 입력 데이터
data = [
    {"cores": 1,  "frontend_cpu_pct": 27, "wrk_rps": 39000,  "wrk_user_cpu_pct": 98, "ghz_rps": 37000,  "ghz_user_cpu_pct": 100},
    {"cores": 2,  "frontend_cpu_pct": 50, "wrk_rps": 68000,  "wrk_user_cpu_pct": 91, "ghz_rps": 67000,  "ghz_user_cpu_pct": 96},
    {"cores": 4,  "frontend_cpu_pct": 73, "wrk_rps": 105000, "wrk_user_cpu_pct": 88, "ghz_rps": 107000, "ghz_user_cpu_pct": 90},
    {"cores": 8,  "frontend_cpu_pct": 75, "wrk_rps": 111000, "wrk_user_cpu_pct": 60, "ghz_rps": 132000, "ghz_user_cpu_pct": 71},
    {"cores": 10, "frontend_cpu_pct": 75, "wrk_rps": 110000, "wrk_user_cpu_pct": 52, "ghz_rps": 135000, "ghz_user_cpu_pct": 63},
]
df = pd.DataFrame(data)

# 1) RPS vs cores
plt.figure()
plt.plot(df["cores"], df["wrk_rps"], marker="o", label="wrk RPS")
plt.plot(df["cores"], df["ghz_rps"], marker="o", label="ghz RPS")
plt.xlabel("Number of cores")
plt.ylabel("RPS")
plt.title("RPS vs Number of Cores")
plt.legend()
plt.grid(True)
plt.savefig("rps_vs_cores.png", dpi=200, bbox_inches="tight")
plt.close()

# 2) user CPU(%) vs cores  (괄호 안 % 값)
plt.figure()
plt.plot(df["cores"], df["wrk_user_cpu_pct"], marker="o", label="wrk user CPU (%)")
plt.plot(df["cores"], df["ghz_user_cpu_pct"], marker="o", label="ghz user CPU (%)")
plt.xlabel("Number of cores")
plt.ylabel("User CPU Usage (%)")
plt.title("User CPU Usage vs Number of Cores")
plt.legend()
plt.grid(True)
plt.savefig("user_cpu_vs_cores.png", dpi=200, bbox_inches="tight")
plt.close()

print("Saved:", "rps_vs_cores.png", "user_cpu_vs_cores.png")
