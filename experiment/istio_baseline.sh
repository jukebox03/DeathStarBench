#!/bin/bash

# =============================================================================
# Baseline CPU 선형성 검증 스크립트
# 5초 간격으로 60초 동안 측정 (서비스별 분리)
# =============================================================================

NAMESPACE="hotel-res"
CGROUP_BASE="/sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice"

SERVICES_WITH_SIDECAR="frontend geo profile rate recommendation reservation search user"

INTERVAL=5
TOTAL_DURATION=60
NUM_SAMPLES=$((TOTAL_DURATION / INTERVAL))

# =============================================================================
# Functions
# =============================================================================

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

measure_service_proxy_cpu() {
    local service="$1"
    local total_proxy=0
    
    local pods
    pods=$(kubectl get pods -n "$NAMESPACE" -o custom-columns='NAME:.metadata.name,UID:.metadata.uid' --no-headers | grep "^${service}-" | grep -v "mongodb-\|memcached-" || true)
    
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
            
            if [[ "$cname" == "istio-proxy" ]]; then
                local cpu_stat="${pod_cgroup}/cri-containerd-${cid}.scope/cpu.stat"
                local cpu_usec=$(get_cpu_usec "$cpu_stat")
                total_proxy=$((total_proxy + cpu_usec))
            fi
        done <<< "$container_info"
    done <<< "$pods"
    
    echo "$total_proxy"
}

measure_all_services() {
    local result=""
    for svc in $SERVICES_WITH_SIDECAR; do
        local cpu=$(measure_service_proxy_cpu "$svc")
        result+="${svc}:${cpu} "
    done
    echo "$result"
}

# =============================================================================
# Main
# =============================================================================

echo "=============================================="
echo "  Baseline CPU 선형성 검증 (서비스별)"
echo "=============================================="
echo ""
echo "목표: idle 상태에서 CPU 사용량이 시간에 비례하는지 확인"
echo "측정: ${INTERVAL}초 간격, 총 ${TOTAL_DURATION}초 (${NUM_SAMPLES}개 샘플)"
echo "서비스: $SERVICES_WITH_SIDECAR"
echo ""
echo "주의: 측정 중 요청 보내지 마세요!"
echo ""

read -p "시작하려면 Enter..."
echo ""

# 서비스별 시작 CPU 저장
declare -A START_CPU
declare -A PREV_CPU

# 초기 측정
echo ">>> 측정 시작..."
echo ""

initial=$(measure_all_services)
for item in $initial; do
    svc=$(echo "$item" | cut -d':' -f1)
    cpu=$(echo "$item" | cut -d':' -f2)
    START_CPU["$svc"]=$cpu
    PREV_CPU["$svc"]=$cpu
done

total_start=0
for svc in $SERVICES_WITH_SIDECAR; do
    total_start=$((total_start + ${START_CPU["$svc"]}))
done

echo "[0s] Total: ${total_start} usec"
for svc in $SERVICES_WITH_SIDECAR; do
    echo "     $svc: ${START_CPU["$svc"]} usec"
done
echo ""

# 서비스별 delta 합계 저장
declare -A SVC_TOTAL_DELTA

for svc in $SERVICES_WITH_SIDECAR; do
    SVC_TOTAL_DELTA["$svc"]=0
done

# 측정 루프
for i in $(seq 1 $NUM_SAMPLES); do
    sleep $INTERVAL
    
    elapsed=$((i * INTERVAL))
    
    current=$(measure_all_services)
    
    total_cpu=0
    total_delta=0
    
    echo "[${elapsed}s]"
    
    for item in $current; do
        svc=$(echo "$item" | cut -d':' -f1)
        cpu=$(echo "$item" | cut -d':' -f2)
        
        delta=$((cpu - ${PREV_CPU["$svc"]}))
        cumulative=$((cpu - ${START_CPU["$svc"]}))
        rate=$(echo "scale=2; $delta / $INTERVAL" | bc)
        
        SVC_TOTAL_DELTA["$svc"]=$((${SVC_TOTAL_DELTA["$svc"]} + delta))
        
        total_cpu=$((total_cpu + cpu))
        total_delta=$((total_delta + delta))
        
        PREV_CPU["$svc"]=$cpu
        
        printf "     %-15s Delta: %8d usec | Rate: %10.2f usec/s\n" "$svc" "$delta" "$rate"
    done
    
    total_rate=$(echo "scale=2; $total_delta / $INTERVAL" | bc)
    echo "     -------"
    printf "     %-15s Delta: %8d usec | Rate: %10.2f usec/s\n" "TOTAL" "$total_delta" "$total_rate"
    echo ""
done

echo ">>> 측정 완료"
echo ""

# =============================================================================
# 결과 분석
# =============================================================================

echo "=============================================="
echo "  서비스별 Baseline CPU (${TOTAL_DURATION}초 합계)"
echo "=============================================="
echo ""

printf "%-15s %15s %15s\n" "Service" "Total(usec)" "Rate(usec/s)"
printf "%-15s %15s %15s\n" "-------" "-----------" "-----------"

grand_total=0
for svc in $SERVICES_WITH_SIDECAR; do
    total=${SVC_TOTAL_DELTA["$svc"]}
    rate=$(echo "scale=2; $total / $TOTAL_DURATION" | bc)
    printf "%-15s %15d %15.2f\n" "$svc" "$total" "$rate"
    grand_total=$((grand_total + total))
done

echo ""
grand_rate=$(echo "scale=2; $grand_total / $TOTAL_DURATION" | bc)
printf "%-15s %15d %15.2f\n" "=== TOTAL ===" "$grand_total" "$grand_rate"

echo ""
echo "=============================================="
echo "  CSV (복사용)"
echo "=============================================="
echo ""
echo "service,total_usec,rate_usec_per_sec"
for svc in $SERVICES_WITH_SIDECAR; do
    total=${SVC_TOTAL_DELTA["$svc"]}
    rate=$(echo "scale=2; $total / $TOTAL_DURATION" | bc)
    echo "$svc,$total,$rate"
done
echo "TOTAL,$grand_total,$grand_rate"