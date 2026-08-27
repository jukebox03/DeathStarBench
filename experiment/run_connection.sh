#!/bin/bash

TARGET="10.244.0.111:8086"
PROTO="$HOME/DeathStarBench_k8s/DeathStarBench/hotelReservation/services/user/proto/user.proto"
INSTANCES=8

mkdir -p results_conn_8ghz

for conn in 1; do
  echo "📊 Testing --connections $conn with $INSTANCES ghz..."
  
  rm -f results_conn_8ghz/result_conn${conn}_*.txt
  
  for i in $(seq 1 $INSTANCES); do
    ghz --insecure \
      --proto $PROTO \
      --call user.User.CheckUser \
      -d '{"username": "Cornell_1", "password": "1111111111"}' \
      -c 400 --connections $conn -z 30s \
      $TARGET > results_conn_8ghz/result_conn${conn}_inst${i}.txt 2>&1 &
  done
  
  sleep 10
  netstat -an | grep $TARGET | grep ESTABLISHED | wc -l > results_conn_8ghz/tcp_$conn.txt
  
  wait
  
  # RPS: 마지막 필드
  TOTAL_RPS=$(grep -h "Requests/sec" results_conn_8ghz/result_conn${conn}_inst*.txt | awk '{sum+=$NF} END {printf "%.2f", sum}')
  
  # Latency: 마지막에서 두 번째 필드 (숫자)
  AVG_LAT=$(grep -h "Average:" results_conn_8ghz/result_conn${conn}_inst*.txt | awk '{sum+=$(NF-1); count++} END {printf "%.2f", sum/count}')
  
  TCP=$(cat results_conn_8ghz/tcp_$conn.txt)
  
  echo "✅ conn=$conn: RPS=$TOTAL_RPS, Avg=$AVG_LAT ms, TCP=$TCP"
  
  sleep 15
done