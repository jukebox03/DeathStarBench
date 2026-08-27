#!/bin/bash

# 설정 변수
WRK_BIN="./wrk"
SCRIPT="./DeathStarBench/hotelReservation/wrk2/scripts/hotel-reservation/search_only.lua"
URL="http://localhost:31643"
RPS="3000"
THREADS="4"
CONNS="100"
OUTPUT_FILE="latency_trend.csv"

# 테스트할 Duration 목록 (단위: 초)
# 10초부터 160초까지 늘려가며 측정
DURATIONS=(10 20 40 80 160)

# CSV 헤더 작성
echo "Duration(s),Avg_Latency,P99_Latency,Requests_Sec,Load_Average_1min" > $OUTPUT_FILE
echo "========================================================"
echo " 실험 시작: RPS $RPS 고정, Duration 변화에 따른 Latency 측정"
echo " 결과 파일: $OUTPUT_FILE"
echo "========================================================"

for D in "${DURATIONS[@]}"; do
    echo "[Testing] Duration: ${D}s 진행 중..."

    # 1. wrk 실행 및 결과 저장
    # (awk를 사용하여 텍스트 처리를 쉽게 하기 위해 단위를 포함한 raw text를 잡습니다)
    RESULT=$($WRK_BIN -D exp -t $THREADS -c $CONNS -d ${D}s -L -s $SCRIPT $URL -R $RPS)

    # 2. 결과 파싱 (wrk 출력 포맷에 맞춰 추출)
    # Latency Avg 추출 (Thread Stats 행)
    LATENCY_AVG=$(echo "$RESULT" | grep "Latency" | head -1 | awk '{print $2}')
    
    # Latency P99 추출 (Detailed Percentile Spectrum 혹은 Distribution에서 99%)
    # wrk2의 경우 출력 포맷이 조금 다를 수 있어, 일반적인 99% 라인을 찾습니다.
    # (사용자 로그 기반: "99.000% 1.15m" 형태 혹은 Detailed spectrum 하단)
    # 여기서는 간단히 상단 요약본의 99% 값을 가져오도록 시도합니다.
    LATENCY_P99=$(echo "$RESULT" | grep "99.000%" | awk '{print $2}')
    
    # 만약 위 방식으로 안 잡히면 Thread Stats의 +/- Stdev 옆(Max) 등을 참고해야 할 수도 있음.
    # 사용자 로그 포맷인 "99% 1.15m" 형식을 기준으로 함.
    if [ -z "$LATENCY_P99" ]; then
         LATENCY_P99=$(echo "$RESULT" | grep "Latency" | head -1 | awk '{print $4}') # 대체: Max값 근사치
    fi

    # Actual RPS 추출
    REQ_SEC=$(echo "$RESULT" | grep "Requests/sec" | awk '{print $2}')

    # 3. 현재 시스템 Load Average 측정 (실험 직후 부하 상태)
    LOAD_AVG=$(uptime | awk -F'load average:' '{ print $2 }' | awk -F, '{ print $1 }' | xargs)

    # 4. 결과 출력 및 파일 저장
    echo "  -> 완료: Avg=${LATENCY_AVG}, P99=${LATENCY_P99}, Load=${LOAD_AVG}"
    echo "${D},${LATENCY_AVG},${LATENCY_P99},${REQ_SEC},${LOAD_AVG}" >> $OUTPUT_FILE

    # 5. Cool Down (큐 비우기)
    # 시스템이 이미 과부하 상태이므로, 다음 테스트를 위해 큐를 비울 시간을 줍니다.
    echo "  -> Cool down 30s..."
    sleep 30
    echo "--------------------------------------------------------"
done

echo "모든 실험 종료. 데이터가 $OUTPUT_FILE 에 저장되었습니다."