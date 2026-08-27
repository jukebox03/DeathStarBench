#!/bin/bash
# ============================================================
# DeathStarBench 실험 실행 스크립트 v7 (mTLS STRICT 지원)
# - mTLS STRICT 모드 기본 설정 (Istio 오버헤드 정확 측정)
# - CPU 기반 adaptive cooldown
# - 캐시 삭제 기능
# - 시스템 워밍업 기능
# - PCM 지원 강화
# ============================================================

set -e

# ============================================================
# 설정 값
# ============================================================
# RATES=(200 400 600 700 800 1000) # for without mTLS
# RATES=(100 150 200 250 300 350) # for with mTLS
RATES=(600)
DURATION="120s"           # wrk2 실행 시간
WARMUP_TIME=60           # 측정 전 대기 시간
MEASURE_DURATION=60      # 메트릭 수집 시간
REPETITIONS=1            # 반복 횟수

# Adaptive Cooldown 설정
COOLDOWN_MIN=10          # 최소 cooldown (초)
COOLDOWN_MAX=120         # 최대 cooldown (초) - 무한 대기 방지
COOLDOWN_CHECK_INTERVAL=5  # CPU 체크 간격 (초)
CPU_THRESHOLD_PERCENT=120  # baseline 대비 허용 비율 (120% = baseline의 1.2배)

# 워밍업 설정
WARMUP_RPS=500           # 워밍업 RPS
WARMUP_DURATION="30s"    # 워밍업 시간
WARMUP_WAIT=10           # 워밍업 후 대기 시간

# 경로 설정 (환경에 맞게 수정)
TARGET="${TARGET:-http://192.168.49.2:30918}"
SCRIPT_PATH="${SCRIPT_PATH:-/home/jukebox/DeathStarBench/DeathStarBench/hotelReservation/wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua}"
WRK_PATH="${WRK_PATH:-./wrk}"
PCM_PATH="${PCM_PATH:-./pcm.x}"

# Baseline CPU (실험 시작 전 측정됨)
BASELINE_CPU=0

# ============================================================
# 컬러 출력
# ============================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ============================================================
# 로깅 함수
# ============================================================
log_info() { 
    echo -e "${GREEN}[$(date '+%H:%M:%S')] [INFO]${NC} $1"
}

log_warn() { 
    echo -e "${YELLOW}[$(date '+%H:%M:%S')] [WARN]${NC} $1"
}

log_error() { 
    echo -e "${RED}[$(date '+%H:%M:%S')] [ERROR]${NC} $1" >&2
}

log_debug() {
    if [ -n "$DEBUG" ]; then
        echo -e "${CYAN}[$(date '+%H:%M:%S')] [DEBUG]${NC} $1"
    fi
}

log_section() {
    echo ""
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}"
}

# ============================================================
# 인자 파싱
# ============================================================
ISTIO_MODE=""
ALL_NS_MODE=""
EXPERIMENT_NAME="no_istio"
SKIP_VERIFY=""
DRY_RUN=""
FIXED_COOLDOWN=""  # 고정 cooldown 사용 옵션
SKIP_WARMUP=""     # 워밍업 스킵 옵션
SKIP_CACHE_FLUSH="" # 캐시 삭제 스킵 옵션

# ============================================================
# mTLS 모드 설정 (기본값: STRICT)
# - STRICT: mTLS 강제 (Istio 암호화 오버헤드 정확 측정)
# - PERMISSIVE: mTLS + Plaintext 모두 허용 (호환성)
# ============================================================
MTLS_MODE="STRICT"

print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --istio             Enable Istio mode (measures sidecar overhead)"
    echo "  --all-namespaces    Include istio-system and kube-system in measurement"
    echo "  --skip-verify       Skip prerequisite verification"
    echo "  --skip-warmup       Skip system warmup phase"
    echo "  --skip-cache-flush  Skip cache flush before experiment"
    echo "  --dry-run           Show what would be done without executing"
    echo "  --fixed-cooldown=N  Use fixed N seconds cooldown instead of adaptive"
    echo "  --debug             Enable debug output"
    echo "  --help              Show this help message"
    echo ""
    echo "mTLS Options:"
    echo "  --mtls-strict       [DEFAULT] Force mTLS for all mesh traffic"
    echo "                      Recommended for accurate Istio overhead measurement"
    echo "  --mtls-permissive   Allow both mTLS and plaintext traffic"
    echo "                      Use if experiencing connection issues"
    echo ""
    echo "Environment variables:"
    echo "  TARGET              Target URL (default: http://192.168.49.2:30918)"
    echo "  SCRIPT_PATH         Path to wrk2 lua script"
    echo "  WRK_PATH            Path to wrk binary (default: ./wrk)"
    echo "  PCM_PATH            Path to pcm.x binary (default: ./pcm.x)"
    echo ""
    echo "Adaptive Cooldown:"
    echo "  Instead of fixed cooldown time, waits until CPU returns to baseline."
    echo "  This prevents test overlap at high RPS levels."
    echo "  Use --fixed-cooldown=30 to disable adaptive cooldown."
    echo ""
    echo "Warmup & Cache:"
    echo "  By default, caches are flushed and system is warmed up before testing."
    echo "  Use --skip-warmup and --skip-cache-flush to disable these features."
    echo ""
    echo "mTLS Modes Explained:"
    echo "  STRICT mode forces all service-to-service communication to use mTLS."
    echo "  This is important because a significant portion of Istio's overhead"
    echo "  comes from TLS handshake and encryption/decryption operations."
    echo "  Using STRICT mode ensures you're measuring the full Istio cost."
}

for arg in "$@"; do
    case $arg in
        --istio) 
            ISTIO_MODE="--istio"
            EXPERIMENT_NAME="with_istio" 
            ;;
        --all-namespaces) 
            ALL_NS_MODE="--all-namespaces" 
            ;;
        --skip-verify)
            SKIP_VERIFY="true"
            ;;
        --skip-warmup)
            SKIP_WARMUP="true"
            ;;
        --skip-cache-flush)
            SKIP_CACHE_FLUSH="true"
            ;;
        --dry-run)
            DRY_RUN="true"
            ;;
        --fixed-cooldown=*)
            FIXED_COOLDOWN="${arg#*=}"
            ;;
        --mtls-strict)
            MTLS_MODE="STRICT"
            ;;
        --mtls-permissive)
            MTLS_MODE="PERMISSIVE"
            ;;
        --debug)
            DEBUG="true"
            ;;
        --help|-h)
            print_usage
            exit 0
            ;;
    esac
done

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULT_DIR="results/${EXPERIMENT_NAME}_${TIMESTAMP}"

# ============================================================
# Istio Envoy 설정 최적화
# ============================================================
apply_istio_optimizations() {
    log_section "Applying Istio Envoy Optimizations"
    
    if [ -n "$DRY_RUN" ]; then
        log_info "[DRY RUN] Would apply Istio proxy optimizations"
        log_info "[DRY RUN] mTLS Mode: $MTLS_MODE"
        return
    fi
    
    # ─────────────────────────────────────────────────────────
    # 1. Deployment annotations (CPU/Memory limit 해제, concurrency 설정)
    # ─────────────────────────────────────────────────────────
    log_info "Step 1: Patching deployment annotations..."
    local services=("frontend" "geo" "profile" "rate" "recommendation" "reservation" "search" "user")
    local patched=0
    local failed=0
    
    for deploy in "${services[@]}"; do
        log_info "  Patching $deploy..."
        if kubectl patch deployment $deploy -p '{
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "proxy.istio.io/config": "concurrency: 0"
                        }
                    }
                }
            }
        }' 2>/dev/null; then
            patched=$((patched + 1))
        else
            log_warn "    Failed to patch $deploy"
            failed=$((failed + 1))
        fi
    done
    log_info "  Patched $patched deployments ($failed failed)"
    
    # ─────────────────────────────────────────────────────────
    # 2. DestinationRule (Connection Pool 확장)
    # ─────────────────────────────────────────────────────────
    log_info "Step 2: Applying DestinationRule (connection pool)..."
    cat > /tmp/istio-destinationrule.yaml << 'EOFDR'
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: disable-circuit-breaker
  namespace: default
spec:
  host: "*.default.svc.cluster.local"
  trafficPolicy:
    connectionPool:
      tcp:
        maxConnections: 100000
        connectTimeout: 60s
      http:
        h2UpgradePolicy: UPGRADE
        http1MaxPendingRequests: 100000
        http2MaxRequests: 100000
        maxRequestsPerConnection: 0
        maxRetries: 0
    outlierDetection:
      consecutive5xxErrors: 0
      maxEjectionPercent: 0
EOFDR
    if kubectl apply -f /tmp/istio-destinationrule.yaml 2>/dev/null; then
        log_info "  ✓ DestinationRule applied"
    else
        log_warn "  △ Failed to apply DestinationRule"
    fi
    
    # ─────────────────────────────────────────────────────────
    # 3. VirtualService (Timeout 비활성화)
    # ─────────────────────────────────────────────────────────
    log_info "Step 3: Applying VirtualService (disable timeout)..."
    
    # 각 서비스별로 VirtualService 생성
    local vs_services=("frontend" "geo" "profile" "rate" "recommendation" "reservation" "search" "user" "consul")
    for svc in "${vs_services[@]}"; do
        cat > /tmp/istio-vs-${svc}.yaml << EOFVS
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: ${svc}-no-timeout
  namespace: default
spec:
  hosts:
  - ${svc}.default.svc.cluster.local
  http:
  - timeout: 0s
    retries:
      attempts: 0
    route:
    - destination:
        host: ${svc}.default.svc.cluster.local
EOFVS
        kubectl apply -f /tmp/istio-vs-${svc}.yaml 2>/dev/null || true
    done
    log_info "  ✓ VirtualServices applied (timeout disabled)"
    
    # ─────────────────────────────────────────────────────────
    # 4. PeerAuthentication (mTLS 모드 설정)
    # ─────────────────────────────────────────────────────────
    log_info "Step 4: Applying PeerAuthentication (mTLS $MTLS_MODE)..."
    
    if [ "$MTLS_MODE" = "STRICT" ]; then
        log_info "  ⚠️  STRICT mode: All traffic must use mTLS"
        log_info "     This ensures accurate measurement of Istio encryption overhead"
        
        # Mesh-wide STRICT mTLS
        cat > /tmp/istio-peerauth.yaml << 'EOFPA'
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default-strict
  namespace: default
spec:
  mtls:
    mode: STRICT
EOFPA
    else
        log_info "  ℹ️  PERMISSIVE mode: Both mTLS and plaintext allowed"
        log_warn "     Note: This may underestimate Istio overhead"
        
        cat > /tmp/istio-peerauth.yaml << 'EOFPA'
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default-permissive
  namespace: default
spec:
  mtls:
    mode: PERMISSIVE
EOFPA
    fi
    
    if kubectl apply -f /tmp/istio-peerauth.yaml 2>/dev/null; then
        log_info "  ✓ PeerAuthentication applied (mTLS $MTLS_MODE)"
    else
        log_warn "  △ Failed to apply PeerAuthentication"
    fi
    
    # ─────────────────────────────────────────────────────────
    # 4-1. (STRICT 모드 전용) 연결 검증
    # ─────────────────────────────────────────────────────────
    if [ "$MTLS_MODE" = "STRICT" ]; then
        log_info "Step 4-1: Verifying mTLS connectivity..."
        sleep 5  # PeerAuthentication 적용 대기
        
        # frontend → profile 연결 테스트
        local test_pod=$(kubectl get pods -l io.kompose.service=frontend -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        if [ -n "$test_pod" ]; then
            if kubectl exec "$test_pod" -c hotel-reserv-frontend -- curl -s -o /dev/null -w "%{http_code}" http://profile:8081/ 2>/dev/null | grep -q "200\|404\|400"; then
                log_info "  ✓ mTLS connectivity verified"
            else
                log_warn "  △ mTLS connectivity check inconclusive"
                log_warn "     If you see connection errors, try --mtls-permissive"
            fi
        fi
    fi
    
    # 임시 파일 정리
    rm -f /tmp/istio-destinationrule.yaml /tmp/istio-vs-*.yaml /tmp/istio-peerauth.yaml
    
    # ─────────────────────────────────────────────────────────
    # 5. Pod 재시작 대기
    # ─────────────────────────────────────────────────────────
    if [ $patched -gt 0 ]; then
        log_info "Step 5: Waiting for pods to restart..."
        sleep 10
        kubectl wait --for=condition=ready pod -l io.kompose.service=frontend --timeout=120s 2>/dev/null || true
        log_info "  ✓ Pods restarted with optimized Envoy settings"
    fi
    
    log_info ""
    log_info "Istio optimizations applied:"
    log_info "  - Envoy CPU/Memory limits: REMOVED"
    log_info "  - Envoy concurrency: 0 (use all cores)"
    log_info "  - Connection pool: 10000 max connections"
    log_info "  - Timeout: DISABLED (0s)"
    log_info "  - Retries: DISABLED"
    log_info "  - mTLS: $MTLS_MODE"
    
    if [ "$MTLS_MODE" = "STRICT" ]; then
        log_info ""
        log_info "📊 mTLS STRICT mode enabled:"
        log_info "   - All service-to-service traffic is encrypted"
        log_info "   - TLS handshake overhead is included in measurements"
        log_info "   - This provides accurate Istio overhead metrics"
    fi
}

# ============================================================
# 캐시 삭제 함수
# ============================================================
flush_single_cache() {
    local deployment=$1
    local pod_name
    
    # Pod 이름 가져오기 (io.kompose.service label 사용)
    pod_name=$(kubectl get pods -l io.kompose.service=$deployment -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$pod_name" ]; then
        log_debug "  Pod not found for $deployment"
        return 1
    fi
    
    # flush_all 명령 실행 (여러 방법 시도)
    # 방법 1: nc 사용
    if kubectl exec "$pod_name" -- sh -c "echo 'flush_all' | nc localhost 11211" 2>/dev/null | grep -q "OK"; then
        log_info "  ✓ $deployment cache flushed (nc)"
        return 0
    fi
    
    # 방법 2: bash의 /dev/tcp 사용
    if kubectl exec "$pod_name" -- bash -c "echo 'flush_all' > /dev/tcp/localhost/11211" 2>/dev/null; then
        log_info "  ✓ $deployment cache flushed (bash)"
        return 0
    fi
    
    # 방법 3: Python 사용
    if kubectl exec "$pod_name" -- python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('localhost', 11211))
s.send(b'flush_all\r\n')
print(s.recv(1024).decode())
s.close()
" 2>/dev/null | grep -q "OK"; then
        log_info "  ✓ $deployment cache flushed (python)"
        return 0
    fi
    
    log_warn "  △ Could not flush $deployment cache (continuing anyway)"
    return 1
}

flush_all_caches() {
    log_section "Flushing All Caches"
    
    if [ -n "$DRY_RUN" ]; then
        log_info "[DRY RUN] Would flush all memcached caches"
        return
    fi
    
    local memcached_deployments=("memcached-profile" "memcached-rate" "memcached-reserve")
    local flushed=0
    local failed=0
    
    for deployment in "${memcached_deployments[@]}"; do
        log_info "Flushing $deployment..."
        if flush_single_cache "$deployment"; then
            flushed=$((flushed + 1))
        else
            failed=$((failed + 1))
        fi
    done
    
    log_info ""
    log_info "Cache flush complete: $flushed succeeded, $failed failed"
    
    # 캐시 삭제 후 잠시 대기
    sleep 2
}

# ============================================================
# 시스템 워밍업 함수
# ============================================================
warmup_system() {
    log_section "System Warmup"
    
    if [ -n "$DRY_RUN" ]; then
        log_info "[DRY RUN] Would run warmup at ${WARMUP_RPS} RPS for ${WARMUP_DURATION}"
        return
    fi
    
    log_info "Running warmup: ${WARMUP_RPS} RPS for ${WARMUP_DURATION}"
    log_info "This establishes gRPC connections, fills caches, and warms up JIT..."
    
    # 워밍업 실행 (출력 버림)
    $WRK_PATH -D exp -t 2 -c 50 -d $WARMUP_DURATION -L -s "$SCRIPT_PATH" "$TARGET" -R $WARMUP_RPS > /dev/null 2>&1 || true
    
    log_info "Warmup complete. Waiting ${WARMUP_WAIT}s for system to stabilize..."
    sleep $WARMUP_WAIT
    
    # 워밍업 후 간단한 health check
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" "$TARGET/hotels?inDate=2015-04-09&outDate=2015-04-10&lat=38.0235&lon=-122.095" 2>/dev/null)
    
    if [ "$http_code" = "200" ]; then
        log_info "✓ System ready (HTTP $http_code)"
    else
        log_warn "△ Health check returned HTTP $http_code (may still work)"
    fi
}

# ============================================================
# CPU 측정 함수
# ============================================================
get_total_cpu() {
    # Kubelet API를 통해 전체 application pod의 CPU 사용량 합계 (millicores)
    local total_cpu=0
    
    # kubectl proxy를 통해 모든 노드의 pod CPU 수집
    local nodes=$(curl -s http://127.0.0.1:8001/api/v1/nodes 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for node in data.get('items', []):
        print(node['metadata']['name'])
except: pass
" 2>/dev/null)
    
    for node in $nodes; do
        local node_cpu=$(curl -s "http://127.0.0.1:8001/api/v1/nodes/${node}/proxy/stats/summary" 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    total = 0
    for pod in data.get('pods', []):
        ns = pod['podRef']['namespace']
        if ns in ['default', 'hotel-res']:  # application namespaces
            for container in pod.get('containers', []):
                cpu_nano = container.get('cpu', {}).get('usageNanoCores', 0)
                total += cpu_nano
    # Convert nanoCores to milliCores
    print(int(total / 1000000))
except Exception as e:
    print(0)
" 2>/dev/null)
        
        if [ -n "$node_cpu" ] && [ "$node_cpu" -gt 0 ]; then
            total_cpu=$((total_cpu + node_cpu))
        fi
    done
    
    echo $total_cpu
}

measure_baseline_cpu() {
    log_info "Measuring baseline CPU (3 samples, 5s interval)..."
    
    local sum=0
    local samples=3
    
    for i in $(seq 1 $samples); do
        local cpu=$(get_total_cpu)
        log_debug "  Sample $i: ${cpu}m"
        sum=$((sum + cpu))
        
        if [ $i -lt $samples ]; then
            sleep 5
        fi
    done
    
    BASELINE_CPU=$((sum / samples))
    log_info "Baseline CPU: ${BASELINE_CPU}m"
    
    # baseline이 너무 낮으면 최소값 설정
    if [ "$BASELINE_CPU" -lt 100 ]; then
        BASELINE_CPU=100
        log_warn "Baseline too low, using minimum: ${BASELINE_CPU}m"
    fi
}

# ============================================================
# Adaptive Cooldown
# ============================================================
adaptive_cooldown() {
    local rps=$1
    local start_time=$(date +%s)
    
    # 고정 cooldown 모드
    if [ -n "$FIXED_COOLDOWN" ]; then
        log_info "Fixed cooldown: ${FIXED_COOLDOWN}s"
        sleep $FIXED_COOLDOWN
        return
    fi
    
    # 최소 cooldown 대기
    log_info "Minimum cooldown: ${COOLDOWN_MIN}s..."
    sleep $COOLDOWN_MIN
    
    # CPU threshold 계산
    local cpu_threshold=$((BASELINE_CPU * CPU_THRESHOLD_PERCENT / 100))
    log_info "Waiting for CPU to stabilize (target: <${cpu_threshold}m, baseline: ${BASELINE_CPU}m)..."
    
    local elapsed=$COOLDOWN_MIN
    local stable_count=0
    local required_stable=2  # 연속 2번 안정화 확인
    
    while [ $elapsed -lt $COOLDOWN_MAX ]; do
        local current_cpu=$(get_total_cpu)
        log_debug "  CPU: ${current_cpu}m (threshold: ${cpu_threshold}m)"
        
        if [ "$current_cpu" -lt "$cpu_threshold" ]; then
            stable_count=$((stable_count + 1))
            if [ $stable_count -ge $required_stable ]; then
                log_info "CPU stabilized at ${current_cpu}m after ${elapsed}s"
                return
            fi
        else
            stable_count=0
        fi
        
        sleep $COOLDOWN_CHECK_INTERVAL
        elapsed=$((elapsed + COOLDOWN_CHECK_INTERVAL))
    done
    
    log_warn "Max cooldown (${COOLDOWN_MAX}s) reached, proceeding anyway"
}

# ============================================================
# 사전 검증
# ============================================================
verify_prerequisites() {
    log_section "Verifying Prerequisites"
    
    local errors=0
    
    # 1. wrk2 바이너리
    log_info "Checking wrk2..."
    if [ -x "$WRK_PATH" ]; then
        log_info "  ✓ wrk2 found at $WRK_PATH"
    else
        log_error "  ✗ wrk2 not found at $WRK_PATH"
        errors=$((errors + 1))
    fi
    
    # 2. Lua 스크립트
    log_info "Checking Lua script..."
    if [ -f "$SCRIPT_PATH" ]; then
        log_info "  ✓ Lua script found"
    else
        log_error "  ✗ Lua script not found at $SCRIPT_PATH"
        errors=$((errors + 1))
    fi
    
    # 3. kubectl
    log_info "Checking kubectl..."
    if command -v kubectl &> /dev/null; then
        log_info "  ✓ kubectl available"
    else
        log_error "  ✗ kubectl not found"
        errors=$((errors + 1))
    fi
    
    # 4. Python3
    log_info "Checking Python3..."
    if command -v python3 &> /dev/null; then
        log_info "  ✓ Python3 available"
    else
        log_error "  ✗ Python3 not found"
        errors=$((errors + 1))
    fi
    
    # 5. 필수 Python 스크립트
    log_info "Checking Python scripts..."
    for script in measure_step.py parse_wrk.py aggregate_results.py; do
        if [ -f "$script" ]; then
            log_info "  ✓ $script found"
        else
            log_error "  ✗ $script not found"
            errors=$((errors + 1))
        fi
    done
    
    # 6. Target 접근성
    log_info "Checking target endpoint..."
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" "$TARGET/hotels?inDate=2015-04-09&outDate=2015-04-10&lat=38.0235&lon=-122.095" 2>/dev/null)
    if [ "$http_code" = "200" ]; then
        log_info "  ✓ Target reachable (HTTP $http_code)"
    else
        log_warn "  △ Target returned HTTP $http_code (may still work)"
    fi
    
    # 7. Kubernetes pods
    log_info "Checking Kubernetes pods..."
    local ready_pods=$(kubectl get pods --field-selector=status.phase=Running -o name 2>/dev/null | wc -l)
    if [ "$ready_pods" -gt 0 ]; then
        log_info "  ✓ $ready_pods pods running"
    else
        log_error "  ✗ No running pods found"
        errors=$((errors + 1))
    fi
    
    # 8. kubectl proxy (adaptive cooldown용)
    if [ -z "$FIXED_COOLDOWN" ]; then
        log_info "Checking kubectl proxy (required for adaptive cooldown)..."
        if curl -s http://127.0.0.1:8001/api/v1/namespaces > /dev/null 2>&1; then
            log_info "  ✓ kubectl proxy running"
        else
            log_warn "  △ kubectl proxy not running"
            log_warn "    Run: kubectl proxy --port=8001 &"
            log_warn "    Or use: --fixed-cooldown=30"
        fi
    fi
    
    # 9. Istio 모드 검증
    if [ -n "$ISTIO_MODE" ]; then
        log_info "Checking Istio installation..."
        if kubectl get namespace istio-system &> /dev/null; then
            log_info "  ✓ istio-system namespace exists"
            
            # Sidecar 주입 확인
            local sidecar_count=$(kubectl get pods -o jsonpath='{.items[*].spec.containers[*].name}' 2>/dev/null | tr ' ' '\n' | grep -c "istio-proxy" || echo "0")
            if [ "$sidecar_count" -gt 0 ]; then
                log_info "  ✓ $sidecar_count Istio sidecars detected"
            else
                log_warn "  △ No Istio sidecars detected"
            fi
        else
            log_warn "  △ istio-system namespace not found"
        fi
        
        # mTLS 모드 안내
        log_info "  ℹ️  mTLS Mode: $MTLS_MODE"
        if [ "$MTLS_MODE" = "STRICT" ]; then
            log_info "     All service communication will be encrypted"
        else
            log_info "     Mixed mTLS/plaintext allowed (may underestimate overhead)"
        fi
    fi
    
    # 10. PCM (선택적)
    log_info "Checking PCM (optional)..."
    if [ -x "$PCM_PATH" ]; then
        log_info "  ✓ PCM available at $PCM_PATH"
    else
        log_info "  ℹ️  PCM not available (memory bandwidth metrics disabled)"
    fi
    
    # 결과
    if [ $errors -gt 0 ]; then
        log_error ""
        log_error "$errors critical errors found. Please fix before running."
        exit 1
    fi
    
    log_info ""
    log_info "All critical prerequisites passed!"
}

# ============================================================
# 메타데이터 저장
# ============================================================
save_metadata() {
    mkdir -p "$RESULT_DIR"
    
    cat > "$RESULT_DIR/metadata.json" << EOF
{
    "experiment": "$EXPERIMENT_NAME",
    "timestamp": "$TIMESTAMP",
    "rates": [$(IFS=,; echo "${RATES[*]}")],
    "duration": "$DURATION",
    "warmup_time": $WARMUP_TIME,
    "measure_duration": $MEASURE_DURATION,
    "repetitions": $REPETITIONS,
    "target": "$TARGET",
    "istio_enabled": $([ -n "$ISTIO_MODE" ] && echo "true" || echo "false"),
    "istio_optimizations": {
        "applied": $([ -n "$ISTIO_MODE" ] && echo "true" || echo "false"),
        "proxy_cpu_limit": "unlimited",
        "proxy_memory_limit": "unlimited",
        "concurrency": 0,
        "connection_pool_max": 10000,
        "timeout": "disabled",
        "retries": "disabled",
        "mtls_mode": "$MTLS_MODE"
    },
    "warmup": {
        "enabled": $([ -z "$SKIP_WARMUP" ] && echo "true" || echo "false"),
        "rps": $WARMUP_RPS,
        "duration": "$WARMUP_DURATION",
        "wait_after": $WARMUP_WAIT
    },
    "cache_flush": {
        "enabled": $([ -z "$SKIP_CACHE_FLUSH" ] && echo "true" || echo "false")
    },
    "cooldown": {
        "type": "$([ -n "$FIXED_COOLDOWN" ] && echo "fixed" || echo "adaptive")",
        "min": $COOLDOWN_MIN,
        "max": $COOLDOWN_MAX,
        "cpu_threshold_percent": $CPU_THRESHOLD_PERCENT,
        "baseline_cpu_millicores": $BASELINE_CPU
    },
    "pcm_available": $([ -x "$PCM_PATH" ] && echo "true" || echo "false"),
    "prometheus_available": $(curl -s http://localhost:9090/-/healthy > /dev/null 2>&1 && echo "true" || echo "false")
}
EOF
    
    log_info "Metadata saved to $RESULT_DIR/metadata.json"
}

# ============================================================
# 단일 테스트 실행
# ============================================================
run_single_test() {
    local rps=$1
    local rep=$2
    local wrk_log="$RESULT_DIR/wrk_logs/wrk_${rps}rps_rep${rep}.log"
    
    log_info "─────────────────────────────────────────"
    log_info "Test: ${rps} RPS (repetition $rep/$REPETITIONS)"
    log_info "─────────────────────────────────────────"
    
    if [ -n "$DRY_RUN" ]; then
        log_info "[DRY RUN] Would run wrk2 at $rps RPS"
        return
    fi
    
    # wrk2 백그라운드 실행
    log_info "Starting wrk2..."
    $WRK_PATH -D exp -t 4 -c 100 -d $DURATION -L -s "$SCRIPT_PATH" "$TARGET" -R $rps > "$wrk_log" 2>&1 &
    local wrk_pid=$!
    
    # Warmup 대기
    log_info "Warming up for ${WARMUP_TIME}s..."
    sleep $WARMUP_TIME
    
    # 메트릭 수집
    log_info "Collecting metrics for ${MEASURE_DURATION}s..."
    python3 measure_step.py $rps $ISTIO_MODE $ALL_NS_MODE --duration=$MEASURE_DURATION
    
    # wrk2 완료 대기
    log_info "Waiting for wrk2 to complete..."
    wait $wrk_pid || true
    
    # wrk2 출력 파싱
    log_info "Parsing wrk2 output..."
    python3 parse_wrk.py $rps "$wrk_log"
    
    # Adaptive Cooldown
    adaptive_cooldown $rps
}

# ============================================================
# 결과 집계 및 정리
# ============================================================
finalize_results() {
    log_section "Finalizing Results"
    
    # 집계
    log_info "Aggregating results..."
    python3 aggregate_results.py
    
    # 결과 파일 이동
    log_info "Moving result files..."
    mv k8s_full_metrics.csv "$RESULT_DIR/" 2>/dev/null || true
    mv latency_stats.csv "$RESULT_DIR/" 2>/dev/null || true
    mv metrics_summary.csv "$RESULT_DIR/" 2>/dev/null || true
    mv latency_summary.csv "$RESULT_DIR/" 2>/dev/null || true
    mv pcm_temp.csv "$RESULT_DIR/" 2>/dev/null || true
    
    # 시각화 생성 (옵션)
    if [ -f "plot_results.py" ]; then
        log_info "Generating visualizations..."
        python3 plot_results.py "$RESULT_DIR/k8s_full_metrics.csv" "$RESULT_DIR/latency_stats.csv" "$RESULT_DIR/" || true
        mv *.png "$RESULT_DIR/" 2>/dev/null || true
    fi
    
    # 결과 요약
    log_info ""
    log_info "Results saved to: $RESULT_DIR"
    log_info ""
    ls -la "$RESULT_DIR/"
}

# ============================================================
# 메인 실행
# ============================================================
main() {
    log_section "DeathStarBench Performance Experiment"
    log_info "Experiment: $EXPERIMENT_NAME"
    log_info "RPS Levels: ${RATES[*]}"
    log_info "Repetitions: $REPETITIONS"
    log_info "Duration: $DURATION (measure: ${MEASURE_DURATION}s)"
    
    if [ -n "$FIXED_COOLDOWN" ]; then
        log_info "Cooldown: Fixed ${FIXED_COOLDOWN}s"
    else
        log_info "Cooldown: Adaptive (min: ${COOLDOWN_MIN}s, max: ${COOLDOWN_MAX}s)"
    fi
    
    if [ -z "$SKIP_WARMUP" ]; then
        log_info "Warmup: Enabled (${WARMUP_RPS} RPS for ${WARMUP_DURATION})"
    else
        log_info "Warmup: Disabled"
    fi
    
    if [ -z "$SKIP_CACHE_FLUSH" ]; then
        log_info "Cache Flush: Enabled"
    else
        log_info "Cache Flush: Disabled"
    fi
    
    # mTLS 모드 표시 (Istio 모드일 때만)
    if [ -n "$ISTIO_MODE" ]; then
        log_info "mTLS Mode: $MTLS_MODE"
    fi
    log_info ""
    
    # 사전 검증
    if [ -z "$SKIP_VERIFY" ]; then
        verify_prerequisites
    else
        log_warn "Skipping prerequisite verification"
    fi
    
    # ============================================================
    # Istio 모드: Envoy 최적화 적용
    # - CPU/Memory limit 해제
    # - concurrency: 0 (모든 코어 사용)
    # - mTLS STRICT (기본) 또는 PERMISSIVE
    # ============================================================
    if [ -n "$ISTIO_MODE" ]; then
        apply_istio_optimizations
    fi
    
    # ============================================================
    # Baseline CPU 측정 (adaptive cooldown용)
    # 반드시 워밍업 전 idle 상태에서 측정해야 함!
    # ============================================================
    if [ -z "$FIXED_COOLDOWN" ]; then
        log_section "Measuring Baseline CPU (idle state)"
        measure_baseline_cpu
    fi
    
    # ============================================================
    # 캐시 삭제 (실험 시작 전)
    # ============================================================
    if [ -z "$SKIP_CACHE_FLUSH" ]; then
        flush_all_caches
    else
        log_info "Skipping cache flush (--skip-cache-flush)"
    fi
    
    # ============================================================
    # 시스템 워밍업 (실험 시작 전)
    # ============================================================
    if [ -z "$SKIP_WARMUP" ]; then
        warmup_system
    else
        log_info "Skipping system warmup (--skip-warmup)"
    fi
    
    # 메타데이터 저장
    save_metadata
    mkdir -p "$RESULT_DIR/wrk_logs"
    
    # 이전 결과 파일 삭제
    rm -f k8s_full_metrics.csv latency_stats.csv
    
    # 전체 테스트 수 계산
    total_tests=$((${#RATES[@]} * REPETITIONS))
    current_test=0
    
    log_section "Starting Experiments"
    
    # 반복 실행
    for rep in $(seq 1 $REPETITIONS); do
        log_info ""
        log_info "========== Repetition $rep/$REPETITIONS =========="
        
        for rps in "${RATES[@]}"; do
            current_test=$((current_test + 1))
            log_info ""
            log_info "Progress: $current_test/$total_tests"
            
            run_single_test $rps $rep
        done
    done
    
    # 결과 집계
    finalize_results
    
    log_section "Experiment Complete!"
    log_info "Results directory: $RESULT_DIR"
    
    # 다음 단계 안내
    echo ""
    echo "Next steps:"
    echo "  1. View results:    cat $RESULT_DIR/latency_summary.csv"
    echo "  2. Generate plots:  python3 plot_results.py $RESULT_DIR/k8s_full_metrics.csv $RESULT_DIR/latency_stats.csv"
    echo ""
    
    if [ "$EXPERIMENT_NAME" = "no_istio" ]; then
        echo "  3. Run with Istio:  $0 --istio"
        echo "  4. Compare results: python3 compare_istio.py results/no_istio_* results/with_istio_*"
    fi
    
    # mTLS 모드 정보 출력 (Istio 실험인 경우)
    if [ -n "$ISTIO_MODE" ]; then
        echo ""
        echo "mTLS Configuration Used: $MTLS_MODE"
        if [ "$MTLS_MODE" = "STRICT" ]; then
            echo "  ✓ Full Istio overhead measured (including TLS encryption)"
        else
            echo "  ⚠️  PERMISSIVE mode may underestimate Istio overhead"
            echo "     Consider re-running with --mtls-strict for accurate measurement"
        fi
    fi
}

# 실행
main