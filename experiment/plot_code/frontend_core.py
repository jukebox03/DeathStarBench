import pandas as pd
import matplotlib.pyplot as plt

# 입력 데이터 (user core 0-5 고정 / frontend core 변화)
data = [
    {"cores": 6,  "rps": 22000,  "user_cpu_pct": 15},
    {"cores": 7,  "rps": 43000,  "user_cpu_pct": 30},
    {"cores": 9,  "rps": 77000,  "user_cpu_pct": 50},
    {"cores": 13, "rps": 113000, "user_cpu_pct": 72},
    {"cores": 17, "rps": 114000, "user_cpu_pct": 73},
    {"cores": 21, "rps": 114000, "user_cpu_pct": 73},  # 신뢰도 낮음 (주석)
]

df = pd.DataFrame(data)

# 한 그래프에 RPS(실선) + user CPU(점선)
fig, ax1 = plt.subplots()

# 왼쪽 y축: RPS
ax1.plot(df["cores"], df["rps"], marker="o", label="RPS")
ax1.set_xlabel("Number of cores")
ax1.set_ylabel("RPS")
ax1.grid(True)

# 오른쪽 y축: user CPU (%), 점선
ax2 = ax1.twinx()
ax2.plot(df["cores"], df["user_cpu_pct"], marker="o", linestyle="--", label="User CPU (%)")
ax2.set_ylabel("User CPU Usage (%)")

# 범례 합치기
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="best")

plt.title("RPS and User CPU Usage vs Number of Cores")

# 이미지 파일로 저장
out_path = "rps_usercpu_vs_cores.png"
plt.savefig(out_path, dpi=200, bbox_inches="tight")
plt.close()

print("Saved:", out_path)
