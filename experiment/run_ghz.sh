#!/bin/bash

# 설정
INSTANCES=4
TARGET_ADDR="10.244.0.42:8086" # user 서비스
#TARGET_ADDR="10.244.0.214:8081" # profile 서비스
#TARGET_ADDR="10.244.0.41:8085" # recommendation 서비스

echo "🚀 Starting $INSTANCES ghz instances targeting $TARGET_ADDR..."

# 이전 결과 삭제
rm -f result_*.txt

# user 서비스에 대한 ghz 테스트 실행
for i in $(seq 1 $INSTANCES); do
    taskset -c 18-35 ghz --insecure \
      --proto ~/DeathStarBench_k8s/DeathStarBench/hotelReservation/services/user/proto/user.proto \
      --call user.User.CheckUser \
      -d '{"username": "Cornell_1", "password": "1111111111"}' \
      -c 25 --connections 1 -z 30s \
      $TARGET_ADDR > "result_$i.txt" 2>&1 &
done


# # profile 서비스에 대한 ghz 테스트 실행
# for i in $(seq 1 $INSTANCES); do
#     ghz --insecure \
#       --proto ~/DeathStarBench_k8s/DeathStarBench/hotelReservation/services/profile/proto/profile.proto \
#       --call profile.Profile.GetProfiles \
#       -d '{"hotelIds":["1","2","3","4","5"],"locale":"en"}' \
#       -c 800 --connections 400 --rps 80000 -z 60s \
#       $TARGET_ADDR > "result_$i.txt" 2>&1 &
# done

# # recommendation 서비스에 대한 ghz 테스트 실행
# for i in $(seq 1 $INSTANCES); do
#     ghz --insecure \
#       --proto ~/DeathStarBench_k8s/DeathStarBench/hotelReservation/services/recommendation/proto/recommendation.proto \
#       --call recommendation.Recommendation.GetRecommendations \
#       -d '{"require":"dis","lat":37.7749,"lon":-122.4194}' \
#       -c 50 --connections 50 --rps 80000 -z 60s \
#       $TARGET_ADDR > "result_$i.txt" 2>&1 &
# done

wait

echo "✅ All tests finished! Aggregating results..."
echo "---------------------------------------------"

# 1. Total RPS 계산
TOTAL_RPS=$(grep -h "Requests/sec" result_*.txt | awk '{sum+=$2} END {printf "%.2f", sum}')

# 2. Avg Latency 계산
AVG_LATENCY=$(grep -h "Average:" result_*.txt | awk '{sum+=$2; count++; unit=$3} END { if (count > 0) printf "%.2f %s", sum/count, unit }')

echo "📊 Total RPS:   $TOTAL_RPS req/s"
echo "⏱️  Avg Latency: $AVG_LATENCY"
echo "---------------------------------------------"

# (선택) 임시 파일 삭제
# rm result_*.txt