#!/bin/bash
# consul_manager.sh - Consul 서비스 상태 확인 및 정리 스크립트

NAMESPACE="hotel-res"
SERVICES="search geo rate profile recommendation reservation user frontend"

# Consul에서 서비스 상태 확인
check_consul() {
    echo "=== Consul Service Status ==="
    echo ""
    
    echo "Actual Pod IPs:"
    kubectl get pods -n $NAMESPACE -o wide | grep -v mongodb | grep -v memcached | grep -v consul | grep -v jaeger | grep -v netshoot | tail -n +2 | awk '{print "  "$1": "$6}'
    echo ""
    
    local all_clean=true
    for svc in $SERVICES; do
        registered=$(kubectl exec netshoot -n $NAMESPACE -- curl -s http://consul:8500/v1/catalog/service/srv-$svc 2>/dev/null | jq -r '.[].ServiceAddress' | sort -u | wc -l)
        
        # replica 수 확인
        replicas=$(kubectl get pods -n $NAMESPACE -l io.kompose.service=$svc --no-headers 2>/dev/null | wc -l)
        
        if [ "$registered" -eq "$replicas" ]; then
            echo "srv-$svc: $registered registered (expected: $replicas) ✓"
        else
            echo "srv-$svc: $registered registered (expected: $replicas) ✗ STALE"
            all_clean=false
        fi
    done
    
    echo ""
    if [ "$all_clean" = true ]; then
        echo "=== All services clean ==="
    else
        echo "=== Stale entries detected! Run './consul_manager.sh cleanup' ==="
    fi
}

# Consul 정리 (Consul 재시작 + 서비스 pod 재시작)
cleanup_consul() {
    echo "=== Cleaning Consul (Full Reset) ==="
    echo ""
    
    # Step 1: Consul pod 재시작
    echo "Step 1: Restarting Consul..."
    kubectl delete pod -n $NAMESPACE -l io.kompose.service=consul --wait=true
    kubectl wait --for=condition=ready pod -l io.kompose.service=consul -n $NAMESPACE --timeout=120s
    echo "Consul restarted."
    
    # Step 2: 모든 서비스 pod 재시작
    echo ""
    echo "Step 2: Restarting all service pods..."
    for svc in $SERVICES; do
        kubectl delete pod -n $NAMESPACE -l io.kompose.service=$svc --wait=false 2>/dev/null
    done
    
    # Step 3: 모든 pod ready 대기
    echo ""
    echo "Step 3: Waiting for old pods to terminate..."
    sleep 5

    # Terminating pod이 없어질 때까지 대기
    while kubectl get pods -n $NAMESPACE | grep -q Terminating; do
        echo "  Still terminating..."
        sleep 2
    done

    # Step 4: 새로운 pod ready 대기
    echo ""
    echo "Step 4: Waiting for new pods to be ready..."
    for svc in $SERVICES; do
        echo "  Waiting for $svc..."
        kubectl wait --for=condition=ready pod -l io.kompose.service=$svc -n $NAMESPACE --timeout=180s
    done
    
    # Step 5: 확인
    echo ""
    echo "Step 5: Verifying..."
    check_consul
    
    echo ""
    echo "=== Cleanup Complete ==="
}

# 사용법 출력
usage() {
    echo "Usage: $0 [check|cleanup]"
    echo ""
    echo "  check   - Check Consul service status"
    echo "  cleanup - Restart Consul and all service pods (clears all stale entries)"
}

# 메인
case "$1" in
    check)
        check_consul
        ;;
    cleanup)
        read -p "This will restart Consul and all service pods. Continue? (y/N): " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            cleanup_consul
        else
            echo "Cancelled."
        fi
        ;;
    *)
        usage
        exit 1
        ;;
esac