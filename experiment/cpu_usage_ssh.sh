#!/bin/bash

NAMESPACE="hotel-res"
CGROUP_BASE="/sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice"

# 설정
REMOTE_HOST="jukebox@stream11.snu.ac.kr"
FRONTEND_URL="http://100.8.8.4:31643"
NUM_REQUESTS=30  # 반복 횟수
INTERVAL=1  # 요청 간 간격 (초)

# API 선택 (인자로 받음)
API=${1:-"user"}

case $API in
    "user")
        # POST /user - random user (Cornell_0 ~ Cornell_500)
        USER_ID=$((RANDOM % 501))
        USER_NAME="Cornell_${USER_ID}"
        PASSWORD=""
        for j in $(seq 1 10); do PASSWORD="${PASSWORD}${USER_ID}"; done
        ENDPOINT="/user?username=${USER_NAME}&password=${PASSWORD}"
        SERVICES="frontend user"
        ;;
    "recommendations")
        ENDPOINT="/recommendations?require=dis&lat=38.0235&lon=-122.095"
        SERVICES="frontend recommendation profile"
        ;;
    "hotels")
        ENDPOINT="/hotels?inDate=2015-04-10&outDate=2015-04-11&lat=38.0235&lon=-122.095"
        SERVICES="frontend geo profile rate reservation search"
        ;;
    *)
        echo "Usage: $0 [user|recommendations|hotels]"
        exit 1
        ;;
esac

declare -A START_APP
declare -A START_PROXY
declare -A RESULTS_APP
declare -A RESULTS_PROXY

get_cpu_usec() {
    local file="$1"
    if [[ -f "$file" ]]; then
        grep "^usage_usec" "$file" 2>/dev/null | awk '{print $2}'
    else
        echo "0"
    fi
}

get_container_ids() {
    local pod_name="$1"
    kubectl get pod -n "$NAMESPACE" "$pod_name" -o jsonpath='{range .status.containerStatuses[*]}{.name}={.containerID}{"\n"}{end}' 2>/dev/null
}

measure_service() {
    local service="$1"
    local phase="$2"
    
    local total_app=0
    local total_proxy=0
    
    local pods=$(kubectl get pods -n "$NAMESPACE" -o custom-columns='NAME:.metadata.name,UID:.metadata.uid' --no-headers | grep "^${service}-" | grep -v "mongodb-\|memcached-" || true)
    
    while read -r line; do
        [[ -z "$line" ]] && continue
        
        local pod_name=$(echo "$line" | awk '{print $1}')
        local pod_uid=$(echo "$line" | awk '{print $2}' | tr '-' '_')
        
        [[ -z "$pod_name" ]] && continue
        
        local pod_cgroup="${CGROUP_BASE}/kubepods-burstable-pod${pod_uid}.slice"
        local container_info=$(get_container_ids "$pod_name")
        
        while IFS= read -r cinfo; do
            [[ -z "$cinfo" ]] && continue
            local cname=$(echo "$cinfo" | cut -d'=' -f1)
            local cid=$(echo "$cinfo" | cut -d'=' -f2 | sed 's|containerd://||')
            
            [[ -z "$cid" ]] && continue
            
            local cpu_stat="${pod_cgroup}/cri-containerd-${cid}.scope/cpu.stat"
            local cpu_usec=$(get_cpu_usec "$cpu_stat")
            
            if [[ "$cname" == "istio-proxy" ]]; then
                total_proxy=$((total_proxy + cpu_usec))
            else
                total_app=$((total_app + cpu_usec))
            fi
        done <<< "$container_info"
        
    done <<< "$pods"
    
    if [[ "$phase" == "start" ]]; then
        START_APP["$service"]=$total_app
        START_PROXY["$service"]=$total_proxy
    else
        # 차이 계산
        local diff_app=$((total_app - START_APP["$service"]))
        local diff_proxy=$((total_proxy - START_PROXY["$service"]))
        echo "$diff_app $diff_proxy"
    fi
}

measure_all_start() {
    for svc in $SERVICES; do
        measure_service "$svc" "start"
    done
}

measure_all_end() {
    for svc in $SERVICES; do
        local result=$(measure_service "$svc" "end")
        local diff_app=$(echo "$result" | awk '{print $1}')
        local diff_proxy=$(echo "$result" | awk '{print $2}')
        
        RESULTS_APP["$svc"]="${RESULTS_APP[$svc]:-} $diff_app"
        RESULTS_PROXY["$svc"]="${RESULTS_PROXY[$svc]:-} $diff_proxy"
    done
}

echo "=== 단일 요청 CPU 측정 스크립트 ==="
echo "API: $API"
echo "Endpoint: $ENDPOINT"
echo "측정 서비스: $SERVICES"
echo "반복 횟수: $NUM_REQUESTS"
echo "원격 호스트: $REMOTE_HOST"
echo ""

# Latency 결과 저장
LATENCIES=""

for i in $(seq 1 $NUM_REQUESTS); do
    echo -ne "요청 $i/$NUM_REQUESTS 처리 중...\r"
    
    # user API는 매번 다른 user 사용
    if [[ "$API" == "user" ]]; then
        USER_ID=$((RANDOM % 501))
        USER_NAME="Cornell_${USER_ID}"
        PASSWORD=""
        for j in $(seq 1 10); do PASSWORD="${PASSWORD}${USER_ID}"; done
        ENDPOINT="/user?username=${USER_NAME}&password=${PASSWORD}"
    fi
    
    # 시작 측정
    measure_all_start
    
    # SSH로 원격에서 curl 실행 (latency도 측정)
    LATENCY=$(ssh $REMOTE_HOST "curl -w '%{time_total}' -o /dev/null -s '${FRONTEND_URL}${ENDPOINT}'")
    LATENCIES="$LATENCIES $LATENCY"
    
    # 종료 측정
    measure_all_end
    
    # 요청 간 간격 (충분히 대기)
    sleep $INTERVAL
done

echo ""
echo ""
echo "=============================================="
echo "  결과 (${NUM_REQUESTS} requests)"
echo "=============================================="
echo ""

# 평균 계산 함수
calc_avg() {
    local values="$1"
    local sum=0
    local count=0
    for v in $values; do
        sum=$(echo "$sum + $v" | bc)
        count=$((count + 1))
    done
    if [[ $count -gt 0 ]]; then
        echo "scale=2; $sum / $count" | bc
    else
        echo "0"
    fi
}

# 표준편차 계산 함수
calc_stddev() {
    local values="$1"
    local avg="$2"
    local sum_sq=0
    local count=0
    for v in $values; do
        diff=$(echo "$v - $avg" | bc)
        sq=$(echo "$diff * $diff" | bc)
        sum_sq=$(echo "$sum_sq + $sq" | bc)
        count=$((count + 1))
    done
    if [[ $count -gt 1 ]]; then
        variance=$(echo "scale=4; $sum_sq / ($count - 1)" | bc)
        echo "scale=2; sqrt($variance)" | bc
    else
        echo "0"
    fi
}

printf "%-20s %15s %15s %15s %15s\n" "Service" "App(usec)" "App(std)" "Proxy(usec)" "Proxy(std)"
printf "%-20s %15s %15s %15s %15s\n" "-------" "--------" "--------" "----------" "----------"

TOTAL_APP=0
TOTAL_PROXY=0

for svc in $SERVICES; do
    app_values="${RESULTS_APP[$svc]}"
    proxy_values="${RESULTS_PROXY[$svc]}"
    
    app_avg=$(calc_avg "$app_values")
    app_std=$(calc_stddev "$app_values" "$app_avg")
    proxy_avg=$(calc_avg "$proxy_values")
    proxy_std=$(calc_stddev "$proxy_values" "$proxy_avg")
    
    TOTAL_APP=$(echo "$TOTAL_APP + $app_avg" | bc)
    TOTAL_PROXY=$(echo "$TOTAL_PROXY + $proxy_avg" | bc)
    
    printf "%-20s %15.2f %15.2f %15.2f %15.2f\n" "$svc" "$app_avg" "$app_std" "$proxy_avg" "$proxy_std"
done

echo ""
TOTAL=$(echo "$TOTAL_APP + $TOTAL_PROXY" | bc)
printf "%-20s %15.2f %15s %15.2f\n" "=== TOTAL ===" "$TOTAL_APP" "-" "$TOTAL_PROXY"
printf "%-20s %15.2f\n" "=== GRAND TOTAL ===" "$TOTAL"

# Latency 결과
echo ""
echo "=== Latency ==="
LAT_AVG=$(calc_avg "$LATENCIES")
LAT_STD=$(calc_stddev "$LATENCIES" "$LAT_AVG")
echo "Average: ${LAT_AVG} sec (std: ${LAT_STD})"

# CSV 출력
echo ""
echo "=== CSV 형식 ==="
echo "service,app_avg,app_std,proxy_avg,proxy_std"
for svc in $SERVICES; do
    app_values="${RESULTS_APP[$svc]}"
    proxy_values="${RESULTS_PROXY[$svc]}"
    
    app_avg=$(calc_avg "$app_values")
    app_std=$(calc_stddev "$app_values" "$app_avg")
    proxy_avg=$(calc_avg "$proxy_values")
    proxy_std=$(calc_stddev "$proxy_values" "$proxy_avg")
    
    echo "$svc,$app_avg,$app_std,$proxy_avg,$proxy_std"
done