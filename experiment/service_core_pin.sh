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

# search 고정
for CID in $(sudo crictl ps --name hotel-reserv-search -q); do
  PID=$(sudo crictl inspect "$CID" | jq -r '.info.pid')
  sudo taskset -apc 0-3 "$PID"
done

# rate 고정
for CID in $(sudo crictl ps --name hotel-reserv-rate -q); do
  PID=$(sudo crictl inspect "$CID" | jq -r '.info.pid')
  sudo taskset -apc 4-7 "$PID"
done

# reservation 고정
for CID in $(sudo crictl ps --name hotel-reserv-reservation -q); do
  PID=$(sudo crictl inspect "$CID" | jq -r '.info.pid')
  sudo taskset -apc 8-11 "$PID"
done

# recommendation 고정
for CID in $(sudo crictl ps --name hotel-reserv-recommendation -q); do
  PID=$(sudo crictl inspect "$CID" | jq -r '.info.pid')
  sudo taskset -apc 12-15 "$PID"
done

# profile 고정
for CID in $(sudo crictl ps --name hotel-reserv-profile -q); do
  PID=$(sudo crictl inspect "$CID" | jq -r '.info.pid')
  sudo taskset -apc 18-21 "$PID"
done

# frontend 고정
for CID in $(sudo crictl ps --name frontend -q); do
  PID=$(sudo crictl inspect "$CID" | jq -r '.info.pid')
  sudo taskset -apc 22-25 "$PID"
done

# memcached-profile 고정
for CID in $(sudo crictl ps --name hotel-reserv-profile-mmc -q); do
  PID=$(sudo crictl inspect "$CID" | jq -r '.info.pid')
  sudo taskset -apc 26-29 "$PID"
done

# memcached-rate 고정
for CID in $(sudo crictl ps --name hotel-reserv-rate-mmc -q); do
  PID=$(sudo crictl inspect "$CID" | jq -r '.info.pid')
  sudo taskset -apc 30-33 "$PID"
done