#!/bin/bash

# CPU 주파수 고정
sudo cpupower -c 0-35 frequency-set -g performance
sudo cpupower -c 0-35 frequency-set -d 2.5GHz -u 2.5GHz

# 모든 hotel-reserv + istio-proxy 컨테이너의 CPU 코어 할당을 초기화
TARGET_CONTAINERS=$(sudo crictl ps 2>/dev/null | grep -E "hotel-reserv|istio-proxy" | awk '{print $1}')

for CID in $TARGET_CONTAINERS; do
  PID=$(sudo crictl inspect "$CID" 2>/dev/null | jq -r '.info.pid')
  
  # PID가 유효한지 체크
  if [ ! -z "$PID" ] && [ "$PID" != "null" ]; then
    # 0-35 전체 코어를 쓰도록 설정 (Reset)
    sudo taskset -apc 0-35 "$PID" > /dev/null 2>&1
    
    # 자식 프로세스(envoy)도 초기화
    for CHILD in $(pgrep -P "$PID" 2>/dev/null); do
      sudo taskset -apc 0-35 "$CHILD" > /dev/null 2>&1
    done
  fi
done

echo "모든 컨테이너 코어 고정 해제 완료 (0-35)"