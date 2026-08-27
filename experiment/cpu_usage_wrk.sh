#!/bin/bash

# =============================================================================
# CPU 측정 스크립트 (Baseline 선형성 검증 + Per-request)
# 1. Baseline 선형성 검증 (5초 간격, 60초)
# 2. Load 측정 (wrk 실행 중)
# 3. Per-request CPU = (Load - Baseline) / requests
# =============================================================================

NAMESPACE="hotel-res"
CGROUP_BASE="/sys/fs/cgroup/kubepods.slice/kubepods-burstable.slice"

# 서비스 목록
SERVICES_WITH_SIDECAR="frontend geo profile rate recommendation reservation search user"
SERVICES_WITHOUT_SIDECAR="memcached-profile memcached-rate memcached-reserve mongodb-geo mongodb-profile mongodb-rate mongodb-recommendation mongodb-reservation mongodb-user"

# Baseline 측정 설정
BASELINE_INTERVAL=5
BASELINE_TOTAL_DURATION=60
BASELINE_NUM_SAMPLES=$((BASELINE_TOTAL_DURATION / BASELINE_INTERVAL))

# 측정 데이터 저장
declare -A BASELINE_START_APP
declare -A BASELINE_START_PROXY
declare -A LOAD_START_APP
declare -A LOAD_START_PROXY
declare -A LOAD_END_APP
declare -A LOAD_END_PROXY

# 서비스별 baseline rate 저장
declare -A BASELINE_RATE_APP
declare -A BASELINE_RATE_PROXY

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

measure_service_cpu() {
    local service="$1"
    
    local total_app=0
    local total_proxy=0
    
    local pods
    if [[ "$service" == memcached-* ]] || [[ "$service" == mongodb-* ]]; then
        pods=$(kubectl get pods -n "$NAMESPACE" -o custom-columns='NAME:.metadata.name,UID:.metadata.uid' --no-headers | grep "^${service}-")
    else
        pods=$(kubectl get pods -n "$NAMESPACE" -o custom-columns='NAME:.metadata.name,UID:.metadata.uid' --no-headers | grep "^${service}-" | grep -v "mongodb-\|memcached-" || true)
    fi
    
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
    
    echo "${total_app}:${total_proxy}"
}

measure_all_services() {
    local result=""
    for svc in $SERVICES_WITH_SIDECAR $SERVICES_WITHOUT_SIDECAR; do
        local cpu=$(measure_service_cpu "$svc")
        result+="${svc}=${cpu} "
    done
    echo "$result"
}

get_pod_count() {
    local service="$1"
    if [[ "$service" == memcached-* ]] || [[ "$service" == mongodb-* ]]; then
        kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep "^${service}-" | wc -l
    else
        kubectl get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep "^${service}-" | grep -v "mongodb-\|memcached-" | wc -l
    fi
}

# =============================================================================
# Main
# =============================================================================

echo "=============================================="
echo "  CPU 측정 스크립트 (Baseline 검증 + Per-request)"
echo "=============================================="
echo ""
echo "측정 대상 서비스 (with sidecar): $SERVICES_WITH_SIDECAR"
echo "측정 대상 서비스 (without sidecar): $SERVICES_WITHOUT_SIDECAR"
echo ""

# 현재 Pod 개수 출력
echo "--- 현재 Pod 개수 ---"
for svc in $SERVICES_WITH_SIDECAR; do
    count=$(get_pod_count "$svc")
    echo "  $svc: $count"
done
echo ""

# =============================================================================
# Phase 1: Baseline 선형성 검증
# =============================================================================
echo "=============================================="
echo "  Phase 1: Baseline 선형성 검증"
echo "=============================================="
echo ""
echo "측정: ${BASELINE_INTERVAL}초 간격, 총 ${BASELINE_TOTAL_DURATION}초 (${BASELINE_NUM_SAMPLES}개 샘플)"
echo "주의: 측정 중 요청 보내지 마세요!"
echo ""

read -p "Baseline 측정 시작하려면 Enter..."
echo ""

# 초기 측정
declare -A PREV_APP
declare -A PREV_PROXY
declare -A SVC_DELTAS_APP
declare -A SVC_DELTAS_PROXY

echo ">>> Baseline 측정 시작..."
echo ""

initial=$(measure_all_services)
for item in $initial; do
    svc=$(echo "$item" | cut -d'=' -f1)
    vals=$(echo "$item" | cut -d'=' -f2)
    app=$(echo "$vals" | cut -d':' -f1)
    proxy=$(echo "$vals" | cut -d':' -f2)
    BASELINE_START_APP["$svc"]=$app
    BASELINE_START_PROXY["$svc"]=$proxy
    PREV_APP["$svc"]=$app
    PREV_PROXY["$svc"]=$proxy
    SVC_DELTAS_APP["$svc"]=""
    SVC_DELTAS_PROXY["$svc"]=""
done

echo "[0s] 초기 측정 완료"

# 샘플링 루프
for i in $(seq 1 $BASELINE_NUM_SAMPLES); do
    sleep $BASELINE_INTERVAL
    
    elapsed=$((i * BASELINE_INTERVAL))
    current=$(measure_all_services)
    
    echo ""
    echo "[${elapsed}s]"
    
    for item in $current; do
        svc=$(echo "$item" | cut -d'=' -f1)
        vals=$(echo "$item" | cut -d'=' -f2)
        app=$(echo "$vals" | cut -d':' -f1)
        proxy=$(echo "$vals" | cut -d':' -f2)
        
        delta_app=$((app - ${PREV_APP["$svc"]}))
        delta_proxy=$((proxy - ${PREV_PROXY["$svc"]}))
        rate_proxy=$(echo "scale=2; $delta_proxy / $BASELINE_INTERVAL" | bc)
        
        # sidecar 있는 서비스만 출력
        if [[ " $SERVICES_WITH_SIDECAR " =~ " $svc " ]]; then
            printf "  %-15s Proxy Delta: %8d usec | Rate: %10.2f usec/s\n" "$svc" "$delta_proxy" "$rate_proxy"
        fi
        
        # Delta 저장
        SVC_DELTAS_APP["$svc"]+="$delta_app "
        SVC_DELTAS_PROXY["$svc"]+="$delta_proxy "
        
        PREV_APP["$svc"]=$app
        PREV_PROXY["$svc"]=$proxy
    done
done

echo ""
echo ">>> Baseline 측정 완료"
echo ""

# =============================================================================
# Baseline 선형성 분석
# =============================================================================
echo "=============================================="
echo "  Baseline 선형성 분석"
echo "=============================================="
echo ""

printf "%-15s %6s %12s %12s %8s %10s\n" "Service" "Pods" "Total(usec)" "Rate(usec/s)" "StdDev" "CV(%)"
printf "%-15s %6s %12s %12s %8s %10s\n" "-------" "----" "-----------" "-----------" "------" "------"

TOTAL_BASELINE_PROXY=0
ALL_CV_OK=true

for svc in $SERVICES_WITH_SIDECAR; do
    pod_count=$(get_pod_count "$svc")
    deltas=(${SVC_DELTAS_PROXY["$svc"]})
    
    # 합계
    sum=0
    for d in "${deltas[@]}"; do
        sum=$((sum + d))
    done
    
    # 평균 rate
    avg_rate=$(echo "scale=2; $sum / $BASELINE_TOTAL_DURATION" | bc)
    
    # 표준편차
    sum_sq_diff=0
    interval_avg=$(echo "scale=4; $sum / $BASELINE_NUM_SAMPLES" | bc)
    for d in "${deltas[@]}"; do
        diff=$(echo "$d - $interval_avg" | bc)
        sq_diff=$(echo "scale=4; $diff * $diff" | bc)
        sum_sq_diff=$(echo "$sum_sq_diff + $sq_diff" | bc)
    done
    variance=$(echo "scale=4; $sum_sq_diff / $BASELINE_NUM_SAMPLES" | bc)
    stddev=$(echo "scale=2; sqrt($variance)" | bc)
    
    # CV
    if (( $(echo "$interval_avg > 0" | bc -l) )); then
        cv=$(echo "scale=2; ($stddev / $interval_avg) * 100" | bc)
    else
        cv="0"
    fi
    
    # CV 체크
    if (( $(echo "$cv > 20" | bc -l) )); then
        ALL_CV_OK=false
    fi
    
    TOTAL_BASELINE_PROXY=$((TOTAL_BASELINE_PROXY + sum))
    BASELINE_RATE_PROXY["$svc"]=$avg_rate
    
    printf "%-15s %6d %12d %12.2f %8.2f %10.2f\n" "$svc" "$pod_count" "$sum" "$avg_rate" "$stddev" "$cv"
done

TOTAL_BASELINE_RATE=$(echo "scale=2; $TOTAL_BASELINE_PROXY / $BASELINE_TOTAL_DURATION" | bc)
echo ""
printf "%-15s %6s %12d %12.2f\n" "=== TOTAL ===" "" "$TOTAL_BASELINE_PROXY" "$TOTAL_BASELINE_RATE"
echo ""

if $ALL_CV_OK; then
    echo "✓ 모든 서비스 CV < 20% → Baseline 선형성 OK"
else
    echo "⚠ 일부 서비스 CV >= 20% → Baseline 불안정 (결과 해석 주의)"
fi
echo ""

# =============================================================================
# Phase 2: Load 측정
# =============================================================================
echo "=============================================="
echo "  Phase 2: Load 측정"
echo "=============================================="
echo ""
echo ">>> Load 시작 측정 중..."

load_start=$(measure_all_services)
for item in $load_start; do
    svc=$(echo "$item" | cut -d'=' -f1)
    vals=$(echo "$item" | cut -d'=' -f2)
    app=$(echo "$vals" | cut -d':' -f1)
    proxy=$(echo "$vals" | cut -d':' -f2)
    LOAD_START_APP["$svc"]=$app
    LOAD_START_PROXY["$svc"]=$proxy
done

echo ""
echo "======================================"
echo "  지금 wrk를 실행하세요!"
echo "======================================"
echo ""
read -p "wrk 완료 후 Enter 누르세요..."
echo ""

echo ">>> Load 종료 측정 중..."

load_end=$(measure_all_services)
for item in $load_end; do
    svc=$(echo "$item" | cut -d'=' -f1)
    vals=$(echo "$item" | cut -d'=' -f2)
    app=$(echo "$vals" | cut -d':' -f1)
    proxy=$(echo "$vals" | cut -d':' -f2)
    LOAD_END_APP["$svc"]=$app
    LOAD_END_PROXY["$svc"]=$proxy
done

echo ">>> Load 측정 완료"
echo ""

# =============================================================================
# 입력
# =============================================================================
read -p "Total requests 수 입력 (wrk 결과에서 확인): " TOTAL_REQUESTS
read -p "Load 측정 시간(초) 입력 (wrk duration): " LOAD_DURATION

if [[ -z "$TOTAL_REQUESTS" ]] || [[ "$TOTAL_REQUESTS" -eq 0 ]]; then
    echo "Error: 유효한 requests 수를 입력하세요."
    exit 1
fi

if [[ -z "$LOAD_DURATION" ]] || [[ "$LOAD_DURATION" -eq 0 ]]; then
    LOAD_DURATION=10
fi

# =============================================================================
# 결과 계산 및 출력
# =============================================================================
echo ""
echo "=============================================="
echo "  결과"
echo "=============================================="
echo ""
echo "Total requests: $TOTAL_REQUESTS"
echo "Baseline duration: ${BASELINE_TOTAL_DURATION}s"
echo "Load duration: ${LOAD_DURATION}s"
echo ""

# --- Load CPU (Raw) ---
echo "--- Load CPU (raw, ${LOAD_DURATION}s) ---"
printf "%-20s %12s %12s %12s\n" "Service" "App(usec)" "Proxy(usec)" "Total(usec)"
printf "%-20s %12s %12s %12s\n" "-------" "---------" "-----------" "-----------"

TOTAL_LOAD_APP=0
TOTAL_LOAD_PROXY=0

for svc in $SERVICES_WITH_SIDECAR $SERVICES_WITHOUT_SIDECAR; do
    start_app=${LOAD_START_APP["$svc"]:-0}
    end_app=${LOAD_END_APP["$svc"]:-0}
    start_proxy=${LOAD_START_PROXY["$svc"]:-0}
    end_proxy=${LOAD_END_PROXY["$svc"]:-0}
    
    app_diff=$((end_app - start_app))
    proxy_diff=$((end_proxy - start_proxy))
    total_diff=$((app_diff + proxy_diff))
    
    TOTAL_LOAD_APP=$((TOTAL_LOAD_APP + app_diff))
    TOTAL_LOAD_PROXY=$((TOTAL_LOAD_PROXY + proxy_diff))
    
    printf "%-20s %12d %12d %12d\n" "$svc" "$app_diff" "$proxy_diff" "$total_diff"
done

TOTAL_LOAD=$((TOTAL_LOAD_APP + TOTAL_LOAD_PROXY))
echo ""
printf "%-20s %12d %12d %12d\n" "=== TOTAL ===" "$TOTAL_LOAD_APP" "$TOTAL_LOAD_PROXY" "$TOTAL_LOAD"
echo ""

# --- Per-request CPU (baseline 제외) ---
echo "--- Per-request CPU (baseline 제외) ---"
printf "%-20s %15s %15s %15s\n" "Service" "App(usec/req)" "Proxy(usec/req)" "Total(usec/req)"
printf "%-20s %15s %15s %15s\n" "-------" "-------------" "---------------" "---------------"

TOTAL_PERREQ_APP=0
TOTAL_PERREQ_PROXY=0

for svc in $SERVICES_WITH_SIDECAR $SERVICES_WITHOUT_SIDECAR; do
    # Baseline rate (usec/s)
    bl_rate_proxy=${BASELINE_RATE_PROXY["$svc"]:-0}
    
    # Baseline for app (calculate from total)
    bl_total_app=0
    deltas_app=(${SVC_DELTAS_APP["$svc"]})
    for d in "${deltas_app[@]}"; do
        bl_total_app=$((bl_total_app + d))
    done
    bl_rate_app=$(echo "scale=4; $bl_total_app / $BASELINE_TOTAL_DURATION" | bc)
    
    # Scaled baseline for load duration
    scaled_bl_app=$(echo "$bl_rate_app * $LOAD_DURATION" | bc | cut -d'.' -f1)
    scaled_bl_proxy=$(echo "$bl_rate_proxy * $LOAD_DURATION" | bc | cut -d'.' -f1)
    scaled_bl_app=${scaled_bl_app:-0}
    scaled_bl_proxy=${scaled_bl_proxy:-0}
    
    # Load
    start_app=${LOAD_START_APP["$svc"]:-0}
    end_app=${LOAD_END_APP["$svc"]:-0}
    start_proxy=${LOAD_START_PROXY["$svc"]:-0}
    end_proxy=${LOAD_END_PROXY["$svc"]:-0}
    ld_app=$((end_app - start_app))
    ld_proxy=$((end_proxy - start_proxy))
    
    # Per-request = (Load - Baseline_scaled) / requests
    net_app=$((ld_app - scaled_bl_app))
    net_proxy=$((ld_proxy - scaled_bl_proxy))
    
    # 음수 방지
    if [[ $net_app -lt 0 ]]; then net_app=0; fi
    if [[ $net_proxy -lt 0 ]]; then net_proxy=0; fi
    
    app_perreq=$(echo "scale=2; $net_app / $TOTAL_REQUESTS" | bc)
    proxy_perreq=$(echo "scale=2; $net_proxy / $TOTAL_REQUESTS" | bc)
    total_perreq=$(echo "scale=2; $app_perreq + $proxy_perreq" | bc)
    
    TOTAL_PERREQ_APP=$(echo "$TOTAL_PERREQ_APP + $app_perreq" | bc)
    TOTAL_PERREQ_PROXY=$(echo "$TOTAL_PERREQ_PROXY + $proxy_perreq" | bc)
    
    printf "%-20s %15.2f %15.2f %15.2f\n" "$svc" "$app_perreq" "$proxy_perreq" "$total_perreq"
done

TOTAL_PERREQ=$(echo "scale=2; $TOTAL_PERREQ_APP + $TOTAL_PERREQ_PROXY" | bc)
echo ""
printf "%-20s %15.2f %15.2f %15.2f\n" "=== TOTAL ===" "$TOTAL_PERREQ_APP" "$TOTAL_PERREQ_PROXY" "$TOTAL_PERREQ"
echo ""

# =============================================================================
# Baseline 신뢰성 검증
# =============================================================================
echo "--- Baseline 신뢰성 검증 ---"
echo ""

SCALED_BASELINE_PROXY=$(echo "$TOTAL_BASELINE_RATE * $LOAD_DURATION" | bc | cut -d'.' -f1)
if [[ $TOTAL_LOAD_PROXY -gt 0 ]]; then
    BASELINE_RATIO=$(echo "scale=2; $SCALED_BASELINE_PROXY * 100 / $TOTAL_LOAD_PROXY" | bc)
else
    BASELINE_RATIO="N/A"
fi

echo "Baseline rate: ${TOTAL_BASELINE_RATE} usec/s"
echo "Scaled baseline (${LOAD_DURATION}s): ${SCALED_BASELINE_PROXY} usec"
echo "Load proxy total: ${TOTAL_LOAD_PROXY} usec"
echo "Baseline 비율: ${BASELINE_RATIO}%"
echo ""

if [[ "$BASELINE_RATIO" != "N/A" ]] && (( $(echo "$BASELINE_RATIO < 50" | bc -l) )); then
    echo "✓ Baseline 비율 적절 (<50%)"
    echo "  → Per-request 값 신뢰 가능"
else
    echo "⚠ Baseline 비율 높음 (>=50%) 또는 계산 불가"
    echo "  → 더 많은 request로 측정 권장"
fi
echo ""

# =============================================================================
# Summary
# =============================================================================
echo "=============================================="
echo "  Summary"
echo "=============================================="
echo ""
echo "Baseline (Istio sidecar idle overhead):"
echo "  Total proxy rate: ${TOTAL_BASELINE_RATE} usec/s"
echo ""
echo "Per-request (baseline 제외):"
echo "  App:   ${TOTAL_PERREQ_APP} usec/req"
echo "  Proxy: ${TOTAL_PERREQ_PROXY} usec/req"
echo "  Total: ${TOTAL_PERREQ} usec/req"
echo ""

# =============================================================================
# CSV 출력
# =============================================================================
echo "=== CSV 형식 ==="
echo "service,pods,baseline_rate_usec_s,load_app_usec,load_proxy_usec,perreq_app_usec,perreq_proxy_usec,perreq_total_usec"

for svc in $SERVICES_WITH_SIDECAR $SERVICES_WITHOUT_SIDECAR; do
    pod_count=$(get_pod_count "$svc")
    bl_rate=${BASELINE_RATE_PROXY["$svc"]:-0}
    
    start_app=${LOAD_START_APP["$svc"]:-0}
    end_app=${LOAD_END_APP["$svc"]:-0}
    start_proxy=${LOAD_START_PROXY["$svc"]:-0}
    end_proxy=${LOAD_END_PROXY["$svc"]:-0}
    ld_app=$((end_app - start_app))
    ld_proxy=$((end_proxy - start_proxy))
    
    # Recalculate per-request
    bl_rate_app_total=0
    deltas_app=(${SVC_DELTAS_APP["$svc"]})
    for d in "${deltas_app[@]}"; do
        bl_rate_app_total=$((bl_rate_app_total + d))
    done
    bl_rate_app=$(echo "scale=4; $bl_rate_app_total / $BASELINE_TOTAL_DURATION" | bc)
    
    scaled_bl_app=$(echo "$bl_rate_app * $LOAD_DURATION" | bc | cut -d'.' -f1)
    scaled_bl_proxy=$(echo "$bl_rate * $LOAD_DURATION" | bc | cut -d'.' -f1)
    scaled_bl_app=${scaled_bl_app:-0}
    scaled_bl_proxy=${scaled_bl_proxy:-0}
    
    net_app=$((ld_app - scaled_bl_app))
    net_proxy=$((ld_proxy - scaled_bl_proxy))
    if [[ $net_app -lt 0 ]]; then net_app=0; fi
    if [[ $net_proxy -lt 0 ]]; then net_proxy=0; fi
    
    app_perreq=$(echo "scale=2; $net_app / $TOTAL_REQUESTS" | bc)
    proxy_perreq=$(echo "scale=2; $net_proxy / $TOTAL_REQUESTS" | bc)
    total_perreq=$(echo "scale=2; $app_perreq + $proxy_perreq" | bc)
    
    echo "$svc,$pod_count,$bl_rate,$ld_app,$ld_proxy,$app_perreq,$proxy_perreq,$total_perreq"
done

echo "TOTAL,,$TOTAL_BASELINE_RATE,$TOTAL_LOAD_APP,$TOTAL_LOAD_PROXY,$TOTAL_PERREQ_APP,$TOTAL_PERREQ_PROXY,$TOTAL_PERREQ"