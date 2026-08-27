#!/bin/bash

# CPU 주파수 고정
sudo cpupower -c 0-35 frequency-set -g performance
sudo cpupower -c 0-35 frequency-set -d 2.5GHz -u 2.5GHz

# 모든 hotel-reserv 컨테이너의 CPU 코어 할당을 초기화
TARGET_CONTAINERS=$(sudo crictl ps | grep -E "hotel-reserv" | awk '{print $1}')

for CID in $TARGET_CONTAINERS; do
  PID=$(sudo crictl inspect "$CID" | jq -r '.info.pid')
  
  # PID가 유효한지 체크
  if [ ! -z "$PID" ] && [ "$PID" != "null" ]; then
    # 0-35 전체 코어를 쓰도록 설정 (Reset)
    sudo taskset -apc 0-35 "$PID" > /dev/null
  fi
done

# user 고정
for CID in $(sudo crictl ps --name hotel-reserv-user -q); do
  PID=$(sudo crictl inspect "$CID" | jq -r '.info.pid')
  sudo taskset -apc 0-5 "$PID"
done

# frontend 고정
for CID in $(sudo crictl ps --name frontend -q); do
  PID=$(sudo crictl inspect "$CID" | jq -r '.info.pid')
  sudo taskset -apc 6-17 "$PID"
done
