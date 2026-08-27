#!/bin/bash
# istio_toggle.sh - Istio sidecar injection 켜기/끄기

NAMESPACE="hotel-res"
SERVICES="search geo rate profile recommendation reservation user frontend"

# Sidecar 끄기
disable_sidecar() {
    echo "=== Disabling Istio Sidecar Injection ==="
    echo ""
    
    # Step 1: Namespace label 변경
    echo "Step 1: Disabling injection on namespace..."
    kubectl label namespace $NAMESPACE istio-injection=disabled --overwrite
    echo "Done."
    
    # Step 2: 서비스 pod만 재시작 (mongodb, memcached 제외)
    echo ""
    echo "Step 2: Restarting service pods..."
    for svc in $SERVICES; do
        kubectl rollout restart deployment $svc -n $NAMESPACE 2>/dev/null || true
    done
    
    # Step 3: Terminating 대기
    echo ""
    echo "Step 3: Waiting for old pods to terminate..."
    sleep 5
    while kubectl get pods -n $NAMESPACE 2>/dev/null | grep -q Terminating; do
        echo "  Still terminating..."
        sleep 2
    done
    
    # Step 4: Ready 대기
    echo ""
    echo "Step 4: Waiting for new pods to be ready..."
    for svc in $SERVICES; do
        echo "  Waiting for $svc..."
        kubectl rollout status deployment $svc -n $NAMESPACE --timeout=180s 2>/dev/null || true
    done
    
    # Step 5: 확인
    echo ""
    echo "Step 5: Verifying..."
    echo ""
    echo "Pod status (should be 1/1 for services):"
    kubectl get pods -n $NAMESPACE | grep -E "^(NAME|frontend|search|geo|rate|profile|recommendation|reservation|user)-" | head -15
    
    echo ""
    echo "=== Sidecar Disabled ==="
}

# Sidecar 켜기
enable_sidecar() {
    echo "=== Enabling Istio Sidecar Injection ==="
    echo ""
    
    # Step 1: Namespace label 변경
    echo "Step 1: Enabling injection on namespace..."
    kubectl label namespace $NAMESPACE istio-injection=enabled --overwrite
    echo "Done."
    
    # Step 2: 서비스 pod만 재시작
    echo ""
    echo "Step 2: Restarting service pods..."
    for svc in $SERVICES; do
        kubectl rollout restart deployment $svc -n $NAMESPACE 2>/dev/null || true
    done
    
    # Step 3: Terminating 대기
    echo ""
    echo "Step 3: Waiting for old pods to terminate..."
    sleep 5
    while kubectl get pods -n $NAMESPACE 2>/dev/null | grep -q Terminating; do
        echo "  Still terminating..."
        sleep 2
    done
    
    # Step 4: Ready 대기
    echo ""
    echo "Step 4: Waiting for new pods to be ready..."
    for svc in $SERVICES; do
        echo "  Waiting for $svc..."
        kubectl rollout status deployment $svc -n $NAMESPACE --timeout=180s 2>/dev/null || true
    done
    
    # Step 5: 확인
    echo ""
    echo "Step 5: Verifying..."
    echo ""
    echo "Pod status (should be 2/2 for services):"
    kubectl get pods -n $NAMESPACE | grep -E "^(NAME|frontend|search|geo|rate|profile|recommendation|reservation|user)-" | head -15
    
    echo ""
    echo "=== Sidecar Enabled ==="
}

# 상태 확인
check_status() {
    echo "=== Istio Sidecar Status ==="
    echo ""
    
    # Namespace injection 상태
    injection=$(kubectl get namespace $NAMESPACE -o jsonpath='{.metadata.labels.istio-injection}' 2>/dev/null)
    echo "Namespace injection: ${injection:-not set}"
    echo ""
    
    # Pod 상태 요약
    echo "Pod status summary:"
    echo ""
    printf "%-15s %s\n" "Service" "READY"
    printf "%-15s %s\n" "-------" "-----"
    
    for svc in $SERVICES; do
        ready=$(kubectl get pods -n $NAMESPACE -l io.kompose.service=$svc --no-headers 2>/dev/null | head -1 | awk '{print $2}')
        printf "%-15s %s\n" "$svc" "${ready:-N/A}"
    done
    
    echo ""
    echo "Expected:"
    echo "  - 2/2: Sidecar enabled"
    echo "  - 1/1: Sidecar disabled"
}

# 사용법
usage() {
    echo "Usage: $0 [on|off|status]"
    echo ""
    echo "  on     - Enable Istio sidecar injection"
    echo "  off    - Disable Istio sidecar injection"
    echo "  status - Check current status"
}

# 메인
case "$1" in
    off)
        read -p "This will disable Istio sidecar and restart pods. Continue? (y/N): " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            disable_sidecar
        else
            echo "Cancelled."
        fi
        ;;
    on)
        read -p "This will enable Istio sidecar and restart pods. Continue? (y/N): " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            enable_sidecar
        else
            echo "Cancelled."
        fi
        ;;
    status)
        check_status
        ;;
    *)
        usage
        exit 1
        ;;
esac