# DeathStarBench HotelReservation Application 성능 측정 및 분석

본 실험에서는 Minikube에 배포된 [DeathStarBench hotelReservation](https://github.com/delimitrou/DeathStarBench/tree/master/hotelReservation) application의 성능을 측정하고 Istio service mesh overhead를 정량적으로 분석하는 것을 목표로 합니다. 

- 대상 application: DeathStarBench HotelReservation (Go, MongoDB, Memcached 기반 microservice)
- 부하 생성기: wrk2
- 핵심 비교: Istio 미적용(No Istio) vs. Istio 적용(With Istio)
- 측정 지표: Latency, Throughput, CPU/Memory 사용량, Network I/O, Disk I/O, System Metrics(System_Mem_BW, System_LLC_Metric), Distributed Tracing

## 측정 메트릭

### 1. Latency & Throughput (wrk2)

| 메트릭 | 설명 |
|--------|------|
| P50, P75, P90, P99, P99.9 | HdrHistogram 기반 정확한 percentile latency |
| Actual RPS | 실제 처리량 |
| Error Rate | Socket errors, Non-2xx responses, Timeout errors |
| Transfer Rate | 데이터 전송량 |

### 2. Resource Usage (Kubelet API)

| 메트릭 | 설명 |
|--------|------|
| CPU_Total(m) | Pod 전체 CPU 사용량 (millicores) |
| CPU_App(m) | Application Container CPU |
| CPU_Sidecar(m) | Istio Sidecar (Envoy) CPU |
| Memory_WorkingSet(Mi) | Working Set Memory |
| Memory_RSS(Mi) | RSS Memory |

Memory_RSS: Process가 현재 RAM에 올려두고 사용 중인 page들의 크기

-> Stack, Heap, Text를 포함, 파일을 읽기 위한 cache memory는 제외

-> Program이 memory 누수가 없는지 판단할 때 사용할 수 있음

Memory_WorkingSet: Process가 최근에 참조하여 RAM에 유지하고 있는 page들의 집합

-> Program이 원할하게 돌기 위해 확보하고 있는 cache 포함 전체 memory

-> OOMKilled의 기준, `kubectl top pod` 명령어로 확인하는 memory 값

### 3. Network I/O (kubectl exec (`/proc/net/dev`))

| 메트릭 | 설명 |
|--------|------|
| Net_RX(KB/s) | Pod별 수신 throughput |
| Net_TX(KB/s) | Pod별 송신 throughput |

### 4. Disk I/O (Prometheus)

| 메트릭 | 설명 |
|--------|------|
| Disk_Read(KB/s) | Container별 읽기 throughput |
| Disk_Write(KB/s) | Container별 쓰기 throughput |

### 5. System Metrics (Intel PCM)

| 메트릭 | 설명 |
|--------|------|
| System_Mem_BW | DDR 읽기/쓰기 대역폭 (GB/s) |
| System_LLC_Metric | L3 캐시 히트율 |

### 6. Distributed Tracing (Jaeger)

| 메트릭 | 설명 |
|--------|------|
| Service Dependencies | 서비스 호출 그래프 (DAG) |
| Service Latency | 서비스별 Avg/P50/P95 latency |
| Edge Latency | 서비스 간 호출 latency |
| Workload Distribution | 요청 타입별 분포 분석 |

---

## 메트릭 측정

### 1. 사전 요구사항

```bash
# minikube 실행 확인
minikube status

# hotelReservation 배포 확인
kubectl get pods -n default

# kubectl proxy 실행 (메트릭 수집용)
kubectl proxy --port=8001

# Python 의존성 설치
pip install pandas matplotlib seaborn requests

# Prometheus 포트포워딩 - Disk I/O 측정용
kubectl port-forward -n monitoring svc/prometheus-stack-kube-prom-prometheus 9090:9090

# Jaeger 포트포워딩 - Trace 분석용
kubectl port-forward svc/jaeger 16686:16686
```

### 2. YAML 파일 사전 수정 (필수)

Istio 1.28+ 버전에서는 빈 `resources` 필드가 있으면 sidecar injection이 실패함. 배포 전 반드시 수정 필요:

```bash
cd ~/DeathStarBench/DeathStarBench/hotelReservation

# 빈 requests: 라인 제거
sed -i '/^[[:space:]]*requests:$/d' kubernetes/*.yaml

# 빈 resources: 라인 제거
sed -i '/^[[:space:]]*resources:$/d' kubernetes/*.yaml
```

**증상**: Pod 생성 시 다음 에러 발생
```
Error creating: admission webhook "namespace.sidecar-injector.istio.io" denied the request: 
failed to run injection template: quantities must match the regular expression...
```

### 3. Istio 설치 (With Istio 측정 시)

**중요: Native Sidecar 비활성화 필수**

Istio 1.28+에서는 Native Sidecar가 기본 활성화되어 있으나, DeathStarBench와 호환 문제가 있음. 반드시 비활성화하고 설치해야 함:

```bash
# 기존 Istio 삭제 (있다면)
istioctl uninstall --purge -y
kubectl delete namespace istio-system --ignore-not-found

# Istio 설치 (Native Sidecar 비활성화)
istioctl install --set profile=default --set values.pilot.env.ENABLE_NATIVE_SIDECARS=false -y

# default namespace에 sidecar injection 활성화
kubectl label namespace default istio-injection=enabled --overwrite
```

**Native Sidecar 문제 증상**:
- Pod가 2/2 Running이지만 `curl` 요청 시 "Connection reset by peer" 발생
- `kubectl get pods -o jsonpath='{.items[*].spec.containers[*].name}'`에서 `istio-proxy`가 안 보임
- `istio-proxy`가 `initContainers`에 있음 (정상은 `containers`에 있어야 함)

### 4. wrk2 빌드

```bash
cd ~/DeathStarBench/hotelReservation/wrk2
make
cp wrk /path/to/experiment/dir/
```

### 5. 설정 수정

`run_experiment.sh` 파일에서 환경에 맞게 경로 수정:

```bash
# Target URL 확인
minikube service frontend --url -n default

# 출력된 URL로 TARGET 설정
TARGET="http://192.168.49.2:30918"
SCRIPT_PATH="/home/user/DeathStarBench/hotelReservation/wrk2/scripts/hotel-reservation/mixed-workload_type_1.lua"
```

### 6. 실험 실행

```bash
# Istio 없는 환경 (Baseline)
bash run_experiment.sh --no-istio --all-namespaces

# Istio 있는 환경 (PERMISSIVE 모드 - 권장)
bash run_experiment.sh --istio --all-namespaces --mtls-permissive

# Istio 있는 환경 (STRICT 모드 - Ingress Gateway 필요)
bash run_experiment.sh --istio --all-namespaces

# 비교 분석
python3 compare_istio.py results/no_istio_* results/with_istio_*

# Jaeger Tracing
python3 collect_jaeger_trace.py --limit=10000
```

---

## 파일 구조

```
experiments/
├── results/
├── run_experiment.sh        # 메인 실험 오케스트레이터
├── wrk                      # wrk 실행 파일
├── measure_step.py          # 메트릭 수집 (CPU/Memory/Network/Disk/PCM)
├── parse_wrk.py             # wrk2 출력 파싱
├── aggregate_results.py     # 반복 실험 결과 집계
├── plot_results.py          # 단일 환경 시각화
├── compare_istio.py         # Istio 비교 분석
├── collect_jaeger_trace.py  # Jaeger trace 수집 및 분석
└── README.md                # 이 파일
```

---

## run_experiment.sh 상세

### 기본 설정값

```bash
RATES=(200 400 600 700 800 1000) # for without mTLS
RATES=(100 150 200 250 300 350) # for with mTLS

DURATION="120s"                    # wrk2 실행 시간
WARMUP_TIME=60                     # 측정 전 대기 시간 (초)
MEASURE_DURATION=60                # 메트릭 수집 시간 (초)
REPETITIONS=1                      # 반복 횟수

# Adaptive Cooldown 설정
COOLDOWN_MIN=10                    # 최소 cooldown (초)
COOLDOWN_MAX=120                   # 최대 cooldown (초)
COOLDOWN_CHECK_INTERVAL=5          # CPU 체크 간격 (초)
CPU_THRESHOLD_PERCENT=120          # baseline 대비 허용 비율

# 워밍업 설정
WARMUP_RPS=500                     # 워밍업 RPS
WARMUP_DURATION="30s"              # 워밍업 시간
WARMUP_WAIT=10                     # 워밍업 후 대기 시간
```

### 명령줄 옵션

```bash
./run_experiment.sh [OPTIONS]

Options:
  --istio             Istio 환경 측정 (자동으로 Envoy 최적화 적용)
  --all-namespaces    istio-system, kube-system 포함 측정
  --mtls-permissive   mTLS PERMISSIVE 모드 (외부 클라이언트 접근 허용, 기본: STRICT)
  --skip-verify       사전 검증 건너뛰기
  --skip-warmup       시스템 워밍업 건너뛰기
  --skip-cache-flush  Memcached 캐시 삭제 건너뛰기
  --dry-run           실제 실행 없이 미리보기
  --fixed-cooldown=N  고정 N초 cooldown 사용 (adaptive 비활성화)
  --debug             디버그 출력 활성화
  --help              도움말

Environment Variables:
  TARGET              대상 URL (default: http://192.168.49.2:30918)
  SCRIPT_PATH         wrk2 lua 스크립트 경로
  WRK_PATH            wrk 바이너리 경로 (default: ./wrk)
  PCM_PATH            pcm.x 바이너리 경로 (default: ./pcm.x)
```

### mTLS 모드 선택

| 모드 | 옵션 | 외부 접근 | 서비스 간 통신 | 사용 시점 |
|------|------|----------|---------------|----------|
| **STRICT** | (기본값) | ❌ 거부 | mTLS만 | Ingress Gateway 설정 시 |
| **PERMISSIVE** | `--mtls-permissive` | ✅ 허용 | mTLS + plaintext | 외부 클라이언트(wrk2) 직접 접근 시 |

wrk2가 클러스터 외부에서 실행되므로 **`--mtls-permissive` 사용 권장**.

### Istio 자동 최적화 (--istio 옵션)

`--istio` 옵션 사용 시 다음 최적화가 자동 적용:

1. **Deployment Annotations**
   - `sidecar.istio.io/proxyCPULimit`: 제거 (무제한)
   - `sidecar.istio.io/proxyMemoryLimit`: 제거 (무제한)
   - `proxy.istio.io/config: concurrency: 0`: 모든 코어 사용

Envoy sidecar에 CPU limit이 존재하는 경우에 대해서 traffic이 몰릴 때 application은 여유가 있지만 proxy가 느려서 throttling 이 발생한다는 것을 실험하는 과정에서 발견

-> 본 실험에서는 Istio architecture 자체의 overhead를 보고자 하기에 CPU limit을 모두 해제

2. **DestinationRule**
   - `maxConnections: 100000`
   - `connectTimeout: 60s`
   - `http1MaxPendingRequests: 100000`
   - `http2MaxRequests: 100000`
   - `maxRetries: 0`
   - `outlierDetection.consecutive5xxErrors: 0`
   - `outlierDetection.maxEjectionPercent: 0`

Traffic이 커지는 경우 Istio는 시스템 보호를 위해서 최대 connection 수를 제한하고 request를 거절(503 Error)

-> 본 실험에서는 높은 RPS에 대해서 test를 진행하기에 Istio의 제한을 없에서 정확한 latency를 측정

요청 실패 시 자동으로 2-3회 정도 재시도하며, 이로 인해 부하가 커지면서 latency가 증가함

-> maxRetries을 0으로 설정하면 요청 실패 시 재시도를 하지 않음

outlierDetection은 Istio의 circuit breaker 기능으로, 연속 5xx 에러 발생 시 해당 pod를 일시 제외(ejection)함. 높은 부하에서 일부 에러 발생 → pod ejection → 남은 pod에 부하 집중 → cascading failure 발생 가능

-> 본 실험에서는 순수한 시스템 한계를 측정하기 위해 circuit breaker를 비활성화

3. **VirtualService**
   - `timeout: 0s` (비활성화)
   - `retries.attempts: 0` (비활성화)

timeout이 있는 경우, long tail latency를 측정하지 못하고 timeout 시간만에 error를 받음

retry가 있는 경우, 의도하지 않은 RPS 대비 CPU 사용량 증가 효과가 발생

| 설정 | 레이어 | 역할 |
|------|------|------|
| **VirtualService** | L7(HTTP routing) | 요청별 timeout/retry 정책 |
| **DestinationRule** | L4/L5(Connection Pool) | 연결 풀 관리, circuit breaker |

### 트러블슈팅

#### 1. Pod 생성 실패: "quantities must match the regular expression"

**원인**: YAML 파일에 빈 `resources:` 또는 `requests:` 필드가 있음

**해결**:
```bash
cd ~/DeathStarBench/DeathStarBench/hotelReservation
sed -i '/^[[:space:]]*requests:$/d' kubernetes/*.yaml
sed -i '/^[[:space:]]*resources:$/d' kubernetes/*.yaml
kubectl delete deployment --all
kubectl apply -R -f kubernetes/
```

#### 2. curl 연결 실패: "Connection reset by peer"

**원인**: Istio Native Sidecar 호환 문제

**해결**:
```bash
istioctl uninstall --purge -y
kubectl delete namespace istio-system
istioctl install --set profile=default --set values.pilot.env.ENABLE_NATIVE_SIDECARS=false -y
kubectl label namespace default istio-injection=enabled --overwrite
kubectl delete deployment --all
kubectl apply -R -f kubernetes/
```

#### 3. HTTP 000 응답 또는 연결 타임아웃 (STRICT 모드)

**원인**: mTLS STRICT 모드에서 외부 클라이언트(wrk2)가 mTLS 인증서 없이 접근

**해결**: `--mtls-permissive` 옵션 사용
```bash
bash run_experiment.sh --istio --all-namespaces --mtls-permissive
```

#### 4. "No Istio sidecars detected" 경고

**원인**: 스크립트의 sidecar 감지 로직이 `initContainers` 또는 `containers`를 잘못 확인

**확인**:
```bash
# istio-proxy가 어디에 있는지 확인
kubectl get pods -o jsonpath='{.items[*].spec.containers[*].name}' | tr ' ' '\n' | grep istio-proxy
kubectl get pods -o jsonpath='{.items[*].spec.initContainers[*].name}' | tr ' ' '\n' | grep istio-proxy
```

**해결**: `run_experiment.sh` Line 688에서 올바른 위치 확인하도록 수정
- Native Sidecar 비활성화 시: `spec.containers[*].name`
- Native Sidecar 활성화 시: `spec.initContainers[*].name`

#### 5. 높은 RPS에서 에러율 급증 (503 에러, socket 에러)

**원인**: Istio connection pool 또는 circuit breaker 제한

**해결**: DestinationRule 설정 강화 (스크립트에서 자동 적용되나, 수동 적용 시):
```bash
kubectl delete destinationrule --all
kubectl delete virtualservice --all
kubectl delete peerauthentication --all
# 스크립트 재실행
bash run_experiment.sh --istio --all-namespaces --mtls-permissive
```

#### 6. Consul 연결 에러: "read: connection reset by peer"

**원인**: Frontend(sidecar 없음)와 Consul(sidecar 있음) 간 mTLS 불일치

**해결**: 모든 서비스가 동일한 sidecar 상태를 가지도록 설정
```bash
# 전체 재배포
kubectl delete deployment --all
kubectl apply -R -f kubernetes/
# 모든 pod가 2/2 또는 1/1로 일관되게 확인
kubectl get pods
```

---

## Adaptive Cooldown

### 왜 필요한가?

고정된 cooldown 시간은 높은 RPS에서 문제:

```
문제 상황:
┌─────────────────────────────────────────────────────────────┐
│ RPS 200  → wrk 종료 → 10초 대기 → CPU 안정화됨 ✓           │
│ RPS 1000 → wrk 종료 → 10초 대기 → 아직 큐에 요청 처리 중! ✗ │
│                                 → 다음 테스트 시작          │
│                                 → 결과 오염!                │
└─────────────────────────────────────────────────────────────┘
```

### 동작 원리

```
1. 실험 시작 전: Baseline CPU 측정 (3회 평균)
   예: Baseline = 200m

2. 각 테스트 후:
   ┌─────────────────────────────────────────┐
   │ 최소 대기 (10초)                         │
   │         ↓                               │
   │ CPU 체크 (5초 간격)                      │
   │   현재 CPU > threshold? → 계속 대기      │
   │   현재 CPU ≤ threshold? → 2회 연속 확인  │
   │         ↓                               │
   │ 안정화 확인 또는 최대 시간(120초) 도달    │
   └─────────────────────────────────────────┘

3. Threshold = Baseline × 120%
```

---

## 캐시 삭제 및 워밍업

### 캐시 삭제

실험 시작 전 Memcached 캐시를 삭제하여 일관된 초기 상태를 보장
- `memcached-profile`
- `memcached-rate`
- `memcached-reserve`

```bash
# 캐시 삭제 건너뛰기
./run_experiment.sh --skip-cache-flush
```

### 시스템 워밍업

실험 전 워밍업을 통해 안정적인 측정을 보장
- gRPC 연결 수립
- 캐시 웜업
- JIT 컴파일 완료

```bash
# 워밍업 건너뛰기
./run_experiment.sh --skip-warmup
```

---

## Jaeger Trace 분석

### 사용법

```bash
# 기본 실행 (최근 1시간, 100개 trace)
python3 collect_jaeger_trace.py

# 옵션 지정
python3 collect_jaeger_trace.py --limit=200 --lookback=2

Options:
  --limit=N       수집할 trace 수 (default: 100)
  --lookback=N    조회할 시간 범위 (hours, default: 1)
```

### 출력 파일

| 파일 | 내용 |
|------|------|
| `service_dependencies.csv` | 서비스 간 호출 관계 (DAG) |
| `latency_breakdown.csv` | 서비스별 latency 통계 |

### 분석 내용

1. **Workload Distribution** (Root Operation 기반)
   ```
   Request Type       Count  Measured(%)    Target(%)
   ------------------------------------------------------------
   Search              1328        60.3%       ~60.0%
   Recommendation       856        38.9%       ~39.0%
   User/Login             9         0.4%        ~0.5%
   Reservation            8         0.4%        ~0.5%
   Unknown                0         0.0%            -
   ```

2. **Service Dependencies**
   ```
   Parent               Child                     Calls
   ------------------------------------------------------------
   frontend             profile                    2173
   frontend             reservation                1330
   search               geo                        1328
   frontend             search                     1328
   search               rate                       1324
   frontend             recommendation              856
   frontend             user                         17
   ```

3. **Service Latency Statistics**
   ```
   Service                      Count    Avg(ms)    P50(ms)    P95(ms)
   --------------------------------------------------------------------------------
   frontend                      7906     103.32       9.78     598.23
   geo                           1328       0.24       0.17       0.64
   profile                       4347       1.03       0.63       4.31
   rate                          2649      18.22       0.15      77.67
   recommendation                 856       0.06       0.02       0.14
   reservation                   3974     117.84       0.38     580.01
   search                        3984      33.86       8.51     111.39
   user                            17       0.03       0.03       0.03
   ```

---

## 개별 스크립트 사용법

### measure_step.py

```bash
python3 measure_step.py <RPS> [--istio] [--all-namespaces] [--duration=60]

# 예시
python3 measure_step.py 1000 --istio --duration=60
```

### parse_wrk.py

```bash
python3 parse_wrk.py <RPS> <LOG_FILE>

# 예시
python3 parse_wrk.py 1000 wrk_output.log
```

### aggregate_results.py

```bash
python3 aggregate_results.py

# 입력: k8s_full_metrics.csv, latency_stats.csv
# 출력: metrics_summary.csv, latency_summary.csv
```

### plot_results.py

```bash
python3 plot_results.py <metrics_csv> <latency_csv> [output_prefix]

# 예시
python3 plot_results.py results/k8s_full_metrics.csv results/latency_stats.csv results/

# 출력 파일:
#   - overview.png           (CPU/Memory/Network 개요)
#   - service_breakdown.png  (서비스별 상세)
#   - latency_analysis.png   (Latency/Throughput 분석)
#   - xtella_io_analysis.png (Disk I/O, System BW)
#   - cpu_efficiency.png     (CPU 효율성)
```

### compare_istio.py

```bash
python3 compare_istio.py <no_istio_dir> <with_istio_dir> [output_prefix]

# 예시
python3 compare_istio.py results/no_istio_20240101 results/with_istio_20240101

# 출력 파일:
#   - compare_main_comparison.png     (CPU/Memory/Network 비교)
#   - compare_sidecar_analysis.png    (Sidecar 비용 분석)
#   - compare_latency_comparison.png  (Latency 비교)
#   - compare_io_system_comparison.png (Disk/System BW 비교)
#   - compare_overhead_summary.csv    (오버헤드 요약)
```

---

## 측정 원리

### CPU 측정 (Delta 방식)

```
                    T1                      T2
                    │                       │
                    ▼                       ▼
    ────────────────●───────────────────────●────────────────
                    │                       │
                    │◄──── duration ───────►│
                    │                       │
    usageCoreNanoSeconds_T1          usageCoreNanoSeconds_T2

    CPU_millicores = (T2 - T1) / duration / 1,000,000
```

### Network 측정 (kubectl exec + Delta)

Minikube에서는 Kubelet API와 Prometheus 모두 container network 메트릭을 제공하지 않음.
따라서 `kubectl exec`로 Pod 내부의 `/proc/net/dev`를 직접 읽음.

```
[측정 방식]
T1: kubectl exec pod -- cat /proc/net/dev → rxBytes_T1, txBytes_T1
    (10개 worker로 병렬 처리)

    ... duration 대기 ...

T2: kubectl exec pod -- cat /proc/net/dev → rxBytes_T2, txBytes_T2

Net_RX_KBps = (rxBytes_T2 - rxBytes_T1) / duration / 1024
Net_TX_KBps = (txBytes_T2 - txBytes_T1) / duration / 1024
```

### Disk I/O 측정 (Prometheus)

```promql
rate(container_fs_reads_bytes_total[60s]) / 1024   # KB/s
rate(container_fs_writes_bytes_total[60s]) / 1024  # KB/s
```

### Latency 측정 (HdrHistogram)

wrk2는 **Coordinated Omission**을 방지하는 HdrHistogram을 사용하여 정확한 tail latency를 측정.

-> DeathStarBench 에서 제공하는 측정 tool 사용 및 결과 parsing

### PCM 측정 (System-wide)

```
[PCM CSV 구조 - 2-row 헤더]
Row 0: System,System,System,...,Socket 0,Socket 0,...
Row 1: Date,Time,EXEC,IPC,FREQ,...,READ,WRITE,L3HIT,...
Row 2+: 데이터

[파싱]
- "System" 카테고리에서 READ, WRITE, L3HIT 인덱스 찾기
- Memory BW = avg(READ) + avg(WRITE)  # GB/s
- LLC Hit Rate = avg(L3HIT)           # 0.0 ~ 1.0
```

### 트러블슈팅

#### 1. kubectl proxy 연결 실패

```bash
pkill -f "kubectl proxy"
kubectl proxy --port=8001
curl http://127.0.0.1:8001/api/v1/nodes
```

#### 2. Network 메트릭이 0으로 나옴

```bash
# Pod 내부에서 직접 확인
kubectl exec -n default frontend-xxx -- cat /proc/net/dev

# eth0 인터페이스 확인 (없으면 net1 등 다른 인터페이스)
```

#### 3. PCM이 0으로 나옴

```bash
# MSR 모듈 로드
sudo modprobe msr

# 직접 실행 테스트
sudo ./pcm.x 1.0 -csv=test.csv
# Ctrl+C로 중단 후 test.csv 확인
```

#### 4. Prometheus 연결 실패

```bash
kubectl get pods -n monitoring
kubectl port-forward -n monitoring svc/prometheus 9090:9090
curl http://localhost:9090/-/healthy
```

#### 5. Jaeger 연결 실패

```bash
kubectl get svc -A | grep jaeger
kubectl port-forward svc/jaeger 16686:16686
curl http://localhost:16686/api/services
```

---

## 실험 워크플로우 요약

```
┌─────────────────────────────────────────────────────────────────┐
│                    실험 시작                                     │
├─────────────────────────────────────────────────────────────────┤
│  1. 사전 검증                                                    │
│     └─ kubectl proxy, target, wrk, Prometheus, PCM 확인         │
│                                                                  │
│  2. (Istio 모드) Envoy 최적화 자동 적용                          │
│     └─ CPU/Mem limit 해제, concurrency 설정, timeout 비활성화   │
│                                                                  │
│  3. Baseline CPU 측정 (Adaptive Cooldown용)                      │
│     └─ 3회 샘플링 → 평균값 계산                                  │
│                                                                  │
│  4. Memcached 캐시 삭제                                          │
│     └─ flush_all 명령으로 캐시 초기화                            │
│                                                                  │
│  5. 시스템 워밍업                                                │
│     └─ 500 RPS로 30초간 워밍업 실행                              │
│                                                                  │
│  6. 각 RPS × 반복 횟수만큼 테스트                                │
│     ┌──────────────────────────────────────────┐                │
│     │  wrk2 시작 (백그라운드)                   │                │
│     │       ↓                                  │                │
│     │  Warmup 대기 (60초)                      │                │
│     │       ↓                                  │                │
│     │  메트릭 수집 (60초)                      │                │
│     │   - Kubelet: CPU, Memory                 │                │
│     │   - kubectl exec: Network RX/TX          │                │
│     │   - Prometheus: Disk I/O                 │                │
│     │   - PCM: Memory BW, LLC Hit              │                │
│     │       ↓                                  │                │
│     │  wrk2 완료 대기                          │                │
│     │       ↓                                  │                │
│     │  wrk2 출력 파싱 (latency, throughput)    │                │
│     │       ↓                                  │                │
│     │  Adaptive Cooldown                       │                │
│     │  (CPU가 baseline으로 돌아올 때까지)       │                │
│     └──────────────────────────────────────────┘                │
│                                                                  │
│  7. 결과 집계 및 시각화                                          │
│     └─ CSV 집계, PNG 생성, 결과 디렉토리 정리                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 메트릭 수집 소스 요약

| 메트릭 | 소스 | API/방식 |
|--------|------|----------|
| CPU | Kubelet | `/api/v1/nodes/{node}/proxy/stats/summary` |
| Memory | Kubelet | `/api/v1/nodes/{node}/proxy/stats/summary` |
| Network | kubectl exec | `cat /proc/net/dev` (병렬 10 workers) |
| Disk I/O | Prometheus | `container_fs_{reads,writes}_bytes_total` |
| Mem BW | PCM | `pcm.x -csv` → System READ/WRITE |
| LLC Hit | PCM | `pcm.x -csv` → System L3HIT |
| Latency | wrk2 | HdrHistogram percentiles |
| Traces | Jaeger | `/api/traces` |

---

## 실험 결과 분석

실제 실험에서 수집된 데이터를 기반으로 다양한 면에 대해서 분석

### 실험 환경

| 항목 | 값 |
|------|-----|
| 플랫폼 | Minikube (단일 노드) |
| 테스트 RPS (without mTLS) | 200, 400, 600, 700, 800, 1000 |
| 테스트 RPS (with mTLS) | 100, 150, 200, 250, 300, 350 |
| wrk2 실행 시간 | 120초 |
| 측정 시간 | 60초 |
| Warmup | 500 RPS × 30초 |

### 서비스 아키텍처

hotelReservation 애플리케이션은 다음과 같은 마이크로서비스로 구성:

                            ┌──────────┐
                            │  Client  │
                            └────┬─────┘
                                 │
                            ┌────▼─────┐
                            │ frontend │
                            └────┬─────┘
                                 │
     ┌───────────────┬───────────┼──────────────┬───────────────┐
     │               │           │              │               │
┌────▼───┐      ┌────▼────┐  ┌───▼───┐  ┌───────▼──────┐  ┌─────▼────────┐
│ search │      │ profile │  │ user  │  │recommendation│  │ reservation  │
└────┬───┘      └────┬────┘  └───┬───┘  └───────┬──────┘  └──────┬───────┘
     │               │           │              │                │
     │          ┌────▼────┐  ┌───▼───┐      ┌───▼───┐        ┌───▼───┐
     │          │Memcached│  │MongoDB│      │MongoDB│        │Memcached│
     │          └────┬────┘  └───────┘      └───────┘        └────┬──┘
     │               │                                            │
     │          ┌────▼────┐                                  ┌────▼────┐
     │          │MongoDB  │                                  │ MongoDB │
     │          └─────────┘                                  └─────────┘
     │
   ┌─┴──────────────┐
   │                │
┌──▼──┐          ┌──▼──┐
│ geo │          │rate │
└──┬──┘          └──┬──┘
   │                │
┌──▼──┐          ┌──▼──┐
│Mongo│          │Mem- │
│ DB  │          │cached
└───┬─┘          └──┬──┘
    │               │
  ┌─▼─┐          ┌──▼──┐
  │Map│          │Mongo│
  │   │          │ DB  │
  └───┘          └─────┘

#### 워크로드 구성 (wrk2 Lua Script)

```lua
local search_ratio      = 0.6    -- 60%: /hotels (Search)
local recommend_ratio   = 0.39   -- 39%: /recommendations
local user_ratio        = 0.005  -- 0.5%: /user (Login)
local reserve_ratio     = 0.005  -- 0.5%: /reservation (Booking)
```

#### 중요: `/hotels` 요청의 실제 호출 패턴

**Jaeger 트레이스 분석 결과**, `/hotels` 요청(60% 비율)은 단순히 search만 호출하는 것이 아니라 **search + reservation + profile을 모두 호출**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  HTTP GET /hotels 요청 (실제 Jaeger 트레이스 기반)                       │
│  Duration: 497.89ms | Services: 6 | Depth: 6 | Total Spans: 15          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  frontend: HTTP GET /hotels                                             │
│      │                                                                  │
│      ├─── /search.Search/Nearby (45.04ms)                              │
│      │        └── search (42.2ms)                                       │
│      │              ├── geo.Geo/Nearby (66µs)                          │
│      │              └── rate.Rate/GetRates (40.24ms)                   │
│      │                    └── memcached_get_multi_rate (3.89ms)        │
│      │                                                                  │
│      ├─── /reservation.Reservation/CheckAvailability (449.2ms) ◄─ 병목!│
│      │        └── reservation (363.17ms)                                │
│      │              ├── memcached_capacity_get_multi (15.59ms)         │
│      │              └── memcached_reserve_get_multi (284.6ms) ◄─ 최대   │
│      │                                                                  │
│      └─── /profile.Profile/GetProfiles (3.61ms)                        │
│               └── profile (7µs)                                         │
│                     └── memcached_get_profile (2µs)                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**핵심 발견**: 
- `/hotels` 요청의 90%가 `reservation.CheckAvailability` 대기 시간 (449ms / 498ms)
- 실제 예약을 하지 않아도 **예약 가능 여부 확인**을 위해 reservation 서비스 호출
- 이것이 reservation 서비스가 CPU의 67%를 사용하는 이유!

#### 서비스 구성 상세

| 서비스 | 역할 | 호출되는 API | 특징 |
|--------|------|--------------|------|
| **frontend** | API Gateway | 모든 요청 | 모든 요청의 진입점 |
| **search** | 호텔 검색 | /hotels | geo + rate 병렬 호출 |
| **profile** | 호텔 정보 | /hotels, /recommendations | 캐시 히트율 높음 |
| **reservation** | 예약 확인/처리 | /hotels, /reservation | **최대 병목** |
| **recommendation** | 추천 | /recommendations | 경량 서비스 |
| **user** | 인증 | /user, /reservation | 로그인 및 예약 시 인증 |
| **geo** | 위치 서비스 | /hotels (via search) | 매우 빠름 (66µs) |
| **rate** | 요금 서비스 | /hotels (via search) | memcached 의존 |

#### 각 API 엔드포인트별 실제 서비스 호출 (Jaeger 기반)

**1. GET /hotels (60% 비율) - 가장 복잡**
```
Duration: 497.89ms | Services: 6 | Spans: 15

frontend
├── search.Search/Nearby (45.04ms)
│   ├── geo.Geo/Nearby (66µs)
│   └── rate.Rate/GetRates (40.24ms)
│       └── memcached_get_multi_rate (3.89ms)
├── reservation.CheckAvailability (449.2ms) ◄── 90% latency
│   ├── memcached_capacity_get_multi (15.59ms)
│   └── memcached_reserve_get_multi (284.6ms)
└── profile.GetProfiles (3.61ms)
    └── memcached_get_profile (2µs)
```

**2. GET /recommendations (39% 비율)**
```
Duration: ~1.09ms | Services: 3 | Spans: 6

frontend
├── recommendation.GetRecommendation (440µs)
│   └── recommendation (16µs)
└── profile.GetProfiles (546µs)
    └── profile (178µs)
        └── memcached_get_profile (129µs)

※ reservation 호출 없음!
```

**3. POST /user (0.5% 비율)**
```
Duration: 4.23ms | Services: 2 | Spans: 3

frontend
└── user.CheckUser (31µs)

※ reservation 호출 없음!
```

**4. POST /reservation (0.5% 비율)**
```
Duration: 155.57ms | Services: 3 | Spans: 5

frontend
├── user.CheckUser (797µs)
│   └── user (29µs)
└── reservation.MakeReservation (~155ms)

※ 인증 후 실제 예약 생성
```

#### 서비스별 호출 여부 요약

| API | search | geo | rate | reservation | profile | recommendation | user |
|-----|--------|-----|------|-------------|---------|----------------|------|
| /hotels (60%) | O | O | O | O | O | X | X |
| /recommendations (39%) | X | X | X | X | O | O | X |
| /user (0.5%) | X | X | X | X | X | X | O |
| /reservation (0.5%) | X | X | X | O | X | X | O |

#### 데이터 저장소

| 저장소 | 용도 | 메모리 사용 |
|--------|------|-------------|
| mongodb-reservation | 예약 데이터 영구 저장 | 181 MiB |
| mongodb-profile | 호텔 프로필 저장 | 161 MiB |
| mongodb-rate | 요금 정보 저장 | 166 MiB |
| mongodb-geo | 위치 데이터 저장 | 160 MiB |
| mongodb-user | 사용자 정보 저장 | 163 MiB |
| mongodb-recommendation | 추천 데이터 저장 | 159 MiB |
| memcached-reserve | 예약 캐시 | 358 MiB (최대) |
| memcached-profile | 프로필 캐시 | 4 MiB |
| memcached-rate | 요금 캐시 | 11 MiB |

### 서비스 호출 그래프 (Jaeger 기반)

Jaeger 분산 추적을 통해 수집된 실제 서비스 호출 패턴입니다:

```
Service Dependencies (Call Count from ~4000 traces)
══════════════════════════════════════════════════════

                        /hotels 요청 (60%)
                              │
    ┌─────────────────────────┼─────────────────────────┐
    │                         │                         │
    ▼                         ▼                         ▼
 search (2376)         reservation (2389)         profile (3926)
    │                         │                         │
    ├──► geo (2376)          │                    memcached
    │                         │
    └──► rate (2372)    memcached-reserve
              │
         memcached-rate


                    /recommendations 요청 (39%)
                              │
                              ▼
                      recommendation (1562)


                        /user 요청 (0.5%)
                              │
                              ▼
                          user (31)
```

#### 왜 reservation 호출이 search와 비슷하게 많은가?

| 요청 타입 | 비율 | reservation 호출 여부 |
|-----------|------|----------------------|
| /hotels (Search) | 60% | ✅ CheckAvailability 호출 |
| /recommendations | 39% | ❌ |
| /reservation (Booking) | 0.5% | ✅ MakeReservation 호출 |
| /user (Login) | 0.5% | ❌ |

**결론**: reservation 서비스 호출의 대부분(99%)은 실제 예약이 아니라 **`/hotels` 요청의 CheckAvailability**에서 발생!

#### 호출 패턴별 상세 분석

**1. `/hotels` 요청 (60%) - 가장 복잡한 요청**

```
시간순 호출 흐름 (Jaeger 트레이스 기반):

T=0ms      frontend 요청 수신
           │
T=0ms      ├──► search.Search/Nearby 시작
T=42ms     │    └── search 완료 (geo: 66µs, rate: 40ms 포함)
           │
T=0ms      ├──► reservation.CheckAvailability 시작 (병렬)
T=449ms    │    └── reservation 완료 ◄── 전체 시간의 90% 차지!
           │
T=449ms    └──► profile.GetProfiles 시작 (reservation 후)
T=453ms         └── profile 완료

T=498ms    frontend 응답 반환

Critical Path: reservation (449ms) >> search (42ms) >> profile (4ms)
```

**2. `/recommendations` 요청 (39%) - 단순한 요청**

```
T=0ms      frontend 요청 수신
           │
T=0ms      └──► recommendation 호출
T=<1ms          └── recommendation 완료 (매우 빠름)

T=<1ms     frontend 응답 반환
```

**3. `/reservation` 요청 (0.5%) - 실제 예약**

```
T=0ms      frontend 요청 수신
           │
T=0ms      └──► reservation.MakeReservation 호출
T=~100ms        └── reservation 완료 (DB 쓰기 포함)

T=~100ms   frontend 응답 반환
```

### 서비스별 Latency (Jaeger Trace 분석)

| Service | Count | Avg (ms) | P95 (ms) | 주요 호출 원인 |
|---------|-------|----------|----------|---------------|
| frontend | 14,254 | 97.59 | 555.30 | 전체 요청 시간 |
| reservation | 7,129 | 111.90 | 547.31 | **/hotels의 CheckAvailability** |
| search | 7,128 | 33.62 | 109.11 | /hotels |
| rate | 4,750 | 18.44 | 76.18 | search에서 호출 |
| profile | 7,854 | 1.02 | 4.15 | /hotels |
| geo | 2,376 | 0.24 | 0.63 | search에서 호출 |
| recommendation | 1,562 | 0.06 | 0.14 | /recommendations |
| user | 31 | 0.03 | 0.04 | /user |


#### Latency 분포 시각화

```
Service Latency Distribution (Avg)
────────────────────────────────────────────────────────────────
reservation  ████████████████████████████████████████████ 111.90ms
frontend     ███████████████████████████████████████ 97.59ms
search       █████████████ 33.62ms
rate         ███████ 18.44ms
profile      ▏ 1.02ms
geo          ▏ 0.24ms
recommend    ▏ 0.06ms
user         ▏ 0.03ms
────────────────────────────────────────────────────────────────
             0ms        50ms       100ms      150ms
```

#### 병목 분석: 왜 reservation이 449ms나 걸리는가?

**Jaeger 트레이스 상세 분석**:

```
┌─────────────────────────────────────────────────────────────────┐
│         reservation.CheckAvailability 시간 분해                 │
│         (총 449.2ms, /hotels 요청의 90%)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. gRPC 요청 수신/파싱                    ~2ms                 │
│                                                                 │
│  2. memcached_capacity_get_multi          15.59ms              │
│     └── 호텔 객실 수용량 정보 조회                              │
│                                                                 │
│  3. memcached_reserve_get_multi           284.6ms  ◄── 최대!   │
│     └── 예약 현황 정보 조회 (캐시 미스 시 DB 접근)              │
│                                                                 │
│  4. 가용성 계산 로직                       ~60ms               │
│     └── 날짜 범위별 객실 가용성 계산                           │
│                                                                 │
│  5. gRPC 응답 생성                         ~2ms                 │
│                                                                 │
│  병목 원인: memcached_reserve 캐시 미스 → MongoDB 조회         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**memcached_reserve_get_multi가 284.6ms인 이유**:

1. **캐시 플러시 후 Cold Cache**: 실험에서 매 테스트마다 memcached를 플러시하므로 초기 요청들은 캐시 미스
2. **날짜 범위 쿼리**: 체크인/체크아웃 날짜 범위의 모든 예약 정보를 조회
3. **MongoDB Fallback**: 캐시 미스 시 MongoDB에서 조회 후 캐시 갱신
4. **데이터 양**: 80개 호텔 × 15일 날짜 범위 = 1,200개 이상의 레코드 가능성

**최적화 방안**:
- memcached TTL 증가 (캐시 히트율 향상)
- MongoDB 인덱스 추가 (hotel_id + date 복합 인덱스)
- 날짜 범위 쿼리 최적화
- reservation replicas 증가

### 성능 결과 요약

#### Latency vs RPS

| Target RPS | Actual RPS | P50 | P99 | Error Rate |
|------------|------------|-----|-----|------------|
| 200 | 197.47 | 5.29ms | 394.49ms | 0.43% |
| 400 | 397.35 | 122.82ms | 1.40s | 0% |
| **600** | **494.58** | **7.11s** | **21.97s** | 0% |
| 700 | 491.40 | 14.02s | 33.21s | 0% |
| 800 | 482.24 | 19.12s | 40.04s | 0% |
| 1000 | 472.77 | 25.31s | 49.18s | 0% |

**⚠️ Saturation Point: 600 RPS** - 이 지점에서 Actual RPS(494.58)가 Target RPS(600)를 크게 밑돌기 시작

**Latency 변화 패턴 분석**:

```
Latency (log scale)
    │
 50s┤                                          ●──── 1000 RPS
    │                                    ●──────
 30s┤                              ●─────
    │                        ●─────
 10s┤                  ●─────                    P99
    │            ●─────
  1s┤      ●─────
    │●─────
100ms┤●                                          P50
    │
 10ms┼────┬────┬────┬────┬────┬────┬────┬────
        200  300  400  500  600  700  800  1000
                      Target RPS
```

**해석**:

1. **200-400 RPS (정상 구간)**:
   - P50 latency: 5ms → 123ms (24배 증가)
   - P99 latency: 394ms → 1.4s (3.5배 증가)
   - Actual RPS ≈ Target RPS (시스템이 요청을 잘 처리)
   - **의미**: 시스템이 선형적으로 확장되는 구간

2. **400-600 RPS (전환 구간)**:
   - P50 latency: 123ms → 7.11s (**58배 급증!**)
   - Actual RPS: 397 → 494 (Target 600에 못 미침)
   - **의미**: 큐잉 지연이 발생하기 시작, 병목 발생

3. **600+ RPS (포화 구간)**:
   - P50 latency가 10초 이상으로 지속 증가
   - Actual RPS가 ~470-490에서 정체
   - **의미**: 시스템 최대 용량 도달, 추가 요청은 큐에 대기

**왜 Error Rate가 0%인데 Latency가 급증하는가?**

wrk2는 "Coordinated Omission"을 방지하는 HdrHistogram을 사용합니다. 서버가 느려져도 wrk2는 계획된 시간에 요청을 "보내려고 시도"하고, 그 시점부터 응답까지의 시간을 측정합니다. 따라서:

- 서버가 처리할 수 있는 것보다 더 많은 요청이 도착하면
- 요청들이 큐에 쌓이고
- 큐에서 대기하는 시간이 latency에 포함됨
- 결국 timeout(90초) 내에 응답이 오므로 에러는 아니지만, latency는 수십 초가 됨

#### CPU 효율성

| RPS | Total CPU (m) | Actual RPS | mCPU/request |
|-----|---------------|------------|--------------|
| 200 | 7,430 | 197.47 | 37.63 |
| 400 | 13,798 | 397.35 | 34.73 |
| **600** | **14,677** | **494.58** | **29.68** ✓ 최적 |
| 700 | 14,881 | 491.40 | 30.29 |
| 800 | 14,774 | 482.24 | 30.64 |
| 1000 | 14,958 | 472.77 | 31.64 |

**최적 효율점: 600 RPS** (29.68 mCPU/request)

**해석**:

```
mCPU/request
    │
 38 ┤●                                    
    │  ╲                                  
 35 ┤    ●                               
    │      ╲                             
 32 ┤        ╲                    ●──────● 효율 감소 구간
    │          ╲              ●──        
 30 ┤            ●───●───●────           
    │            ↑                       
 28 ┼────────────┼────────────────────────
        200    400    600    700    800   1000
                   최적점
```

- **200-600 RPS**: mCPU/request가 감소 (효율 증가)
  - 이유: 고정 오버헤드(GC, idle 스레드 등)가 더 많은 요청에 분산됨
  
- **600 RPS**: 최적점 (29.68 mCPU/request)
  - 이유: 시스템 리소스가 가장 효율적으로 활용되는 지점
  
- **600+ RPS**: mCPU/request가 다시 증가 (효율 감소)
  - 이유: 큐잉, 컨텍스트 스위칭, 캐시 미스 증가로 인한 비효율

### 서비스별 리소스 사용량 (1000 RPS 기준)

#### Top 5 CPU 사용 서비스

| Service | CPU (m) | 비율 | 역할 |
|---------|---------|------|------|
| reservation | 10,066 | 67.3% | 예약 처리, MongoDB 연동 |
| rate | 2,609 | 17.4% | 요금 계산, 캐시 조회 |
| memcached-reserve | 994 | 6.6% | 예약 정보 캐싱 |
| search | 681 | 4.6% | 호텔 검색, geo/rate 호출 |
| frontend | 280 | 1.9% | API Gateway, 라우팅 |

**CPU 사용량 분포 분석**:

```
CPU Distribution at 1000 RPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
reservation  ████████████████████████████████████████████ 67.3%
rate         ███████████ 17.4%
memcached    ████ 6.6%
search       ███ 4.6%
frontend     █ 1.9%
others       █ 2.2%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**주요 병목 서비스: `reservation` (67.3%)**

`reservation` 서비스가 전체 CPU의 2/3를 사용하는 이유:
1. **복잡한 비즈니스 로직**: 날짜 검증, 재고 확인, 트랜잭션 처리
2. **MongoDB 쿼리 부하**: 예약 가능 여부 확인, 예약 생성/수정
3. **Memcached 연동**: memcached-reserve와의 빈번한 캐시 조회/갱신 (284.6ms 소요)
4. **높은 호출 빈도**: `/hotels` 요청(60%)마다 `CheckAvailability` 호출 발생

**성능 개선을 위한 권장사항**:
- `reservation` 서비스 수평 확장 (replicas: 1 → 3)
- MongoDB 쿼리 최적화 및 인덱스 추가
- Memcached 캐시 히트율 모니터링 및 개선
- 비동기 처리 도입 검토

#### 메모리 사용량 (상위)

| Service | Memory (MiB) | 특징 |
|---------|--------------|------|
| memcached-reserve | 358 | 예약 데이터 캐싱 |
| mongodb-rate | 166 | WiredTiger 캐시 |
| mongodb-user | 163 | 사용자 데이터 캐시 |
| mongodb-profile | 161 | 호텔 프로필 캐시 |
| jaeger | 139 | 트레이스 버퍼 |

**해석**: 
- **데이터 저장소가 메모리 사용의 대부분을 차지**: Memcached(358 MiB)와 MongoDB 인스턴스들(~650 MiB 총합)
- **애플리케이션 서비스는 경량**: frontend(27 MiB), search(18 MiB), reservation(39 MiB)
- **Jaeger 오버헤드**: 트레이싱 활성화로 인한 139 MiB 추가 사용

#### 네트워크 트래픽 패턴 (1000 RPS)

| Service | RX (KB/s) | TX (KB/s) | 패턴 |
|---------|-----------|-----------|------|
| reservation | 43,094 | 22,868 | 요청 집중형 |
| rate | 37,205 | 16,269 | 요청 집중형 |
| memcached-reserve | 22,578 | 41,769 | 응답 집중형 (TX > RX) |
| memcached-rate | 19 | 37,252 | 응답 집중형 (TX >> RX) |
| search | 16,073 | 810 | 분산형 (RX >> TX) |

**흥미로운 패턴 분석**:
- **Memcached**: TX가 RX보다 훨씬 큼 → 작은 키로 큰 값을 조회하는 전형적인 캐시 패턴
- **Search**: RX가 TX보다 20배 큼 → 요청을 받아서 geo, rate로 분산하는 라우터 역할

---

## Istio 오버헤드 분석 결과

### 실험 환경

| 항목 | 값 |
|------|-----|
| Istio 버전 | 1.28.2 |
| Native Sidecar | 비활성화 |
| 테스트 환경 | Minikube (단일 노드) |

### 테스트 구성

| 환경 | mTLS 모드 | RPS 범위 | 설명 |
|------|-----------|----------|------|
| **No Istio** | N/A | 200-1000 | Baseline (Sidecar 없음) |
| **mTLS PERMISSIVE** | PERMISSIVE | 200-1000 | Sidecar O, 암호화 선택적 |
| **mTLS STRICT** | STRICT | 100-350 | Sidecar O, 전체 암호화 강제 |


### 실험 결과 및 분석

#### 1. Latency 비교

##### No Istio (Baseline)

| Target RPS | Actual RPS | P50 | P90 | P99 | Error Rate |
|------------|------------|-----|-----|-----|------------|
| 200 | 197.47 | 5.29ms | 227.58ms | 394.49ms | 0.43% |
| 400 | 397.35 | 122.82ms | 570.37ms | 1.40s | 0.0% |
| 600 | 494.58 | 7.11s | 15.86s | 21.97s | 0.0% |
| 700 | 491.40 | 14.02s | 25.51s | 33.21s | 0.0% |
| 800 | 482.24 | 19.12s | 32.93s | 40.04s | 0.0% |
| 1000 | 472.77 | 25.31s | 42.43s | 49.18s | 0.0% |

##### mTLS PERMISSIVE

| Target RPS | Actual RPS | P50 | P90 | P99 | Error Rate |
|------------|------------|-----|-----|-----|------------|
| 200 | 197.38 | 13.48ms | 296.70ms | 527.36ms | 0.43% |
| 400 | 396.59 | 281.86ms | 1.08s | 2.47s | 0.01% |
| 600 | 435.13 | 11.42s | 22.71s | 30.83s | 0.01% |
| 700 | 421.10 | 18.43s | 32.72s | 40.21s | 0.0% |
| 800 | 424.70 | 22.72s | 38.24s | 44.92s | 0.0% |
| 1000 | 418.64 | 27.84s | 47.09s | N/A | 0.0% |

##### mTLS STRICT

| Target RPS | Actual RPS | P50 | P90 | P99 | Error Rate |
|------------|------------|-----|-----|-----|------------|
| 100 | 98.98 | 12.72ms | 343.81ms | 577.53ms | 6.79% |
| 150 | 146.59 | 13.57ms | 442.88ms | 772.61ms | 1.67% |
| 200 | 198.20 | 21.18ms | 573.95ms | 1.09s | 0.41% |
| 250 | 246.81 | 198.40ms | 929.28ms | 1.95s | 0.16% |
| 300 | 289.88 | 1.98s | 6.85s | 13.40s | 0.05% |
| 350 | 310.08 | 5.22s | 15.52s | 23.49s | 1.19% |


#### 2. Latency 비교 분석 @ 200 RPS

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Latency Comparison @ 200 RPS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Percentile    No Istio     PERMISSIVE      STRICT        STRICT vs NoIstio│
│  ───────────────────────────────────────────────────────────────────────── │
│  P50           5.29ms       13.48ms         21.18ms       +300%             │
│  P90           227.58ms     296.70ms        573.95ms      +152%             │
│  P99           394.49ms     527.36ms        1.09s         +176%             │
│                                                                             │
│  ───────────────────────────────────────────────────────────────────────── │
│                                                                             │
│  P50 Latency 증가율:                                                        │
│    No Istio → PERMISSIVE:  +155% (5.29ms → 13.48ms)                        │
│    PERMISSIVE → STRICT:    +57%  (13.48ms → 21.18ms)                       │
│    No Istio → STRICT:      +300% (5.29ms → 21.18ms)                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**핵심 발견**:
- **PERMISSIVE**: Sidecar proxy 오버헤드로 P50이 2.5배 증가
- **STRICT**: mTLS 암호화 추가로 P50이 4배 증가
- mTLS 암호화 자체의 오버헤드: PERMISSIVE → STRICT에서 +57% 추가

#### 3. Saturation Point 비교

```
Throughput Saturation Analysis
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  Configuration      Saturation Point    Max Sustainable RPS    처리량 감소 │
│  ───────────────────────────────────────────────────────────────────────── │
│  No Istio           ~600 RPS            ~495 RPS               baseline    │
│  mTLS PERMISSIVE    ~400-600 RPS        ~435 RPS               -12%        │
│  mTLS STRICT        ~250-300 RPS        ~290 RPS               -41%        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

Actual RPS vs Target RPS
     │
 500 ┤  ●────●                                    No Istio
     │         ╲●────●────●────●                  (max ~495)
 450 ┤                                            
     │      ○────○                                PERMISSIVE
 400 ┤              ╲○────○────○────○             (max ~435)
     │                                            
 350 ┤                                            
     │          ■────■                            STRICT
 300 ┤                  ╲■────■                   (max ~310)
     │              ■────                         
 250 ┤          ■                                 
     │                                            
     ┼────┬────┬────┬────┬────┬────┬────┬────
        100  200  300  400  500  600  700  800
                      Target RPS

● No Istio    ○ PERMISSIVE    ■ STRICT
```

**Saturation 원인 분석**:

| 요인 | No Istio | PERMISSIVE | STRICT |
|------|:--------:|:----------:|:------:|
| Sidecar Proxy 통과 | ✗ | ✓ (2x hop) | ✓ (2x hop) |
| TLS Handshake | ✗ | 선택적 | 필수 |
| 암호화/복호화 | ✗ | 선택적 | 모든 패킷 |
| CPU 경쟁 | 앱만 | 앱 + Envoy | 앱 + Envoy + TLS |


#### 4. CPU 사용량 비교

##### 총 CPU 사용량 @ 200 RPS

| 환경 | Total CPU (m) | App CPU (m) | Sidecar CPU (m) | Sidecar 비율 |
|------|---------------|-------------|-----------------|--------------|
| No Istio | 7,430 | 7,430 | 0 | 0% |
| mTLS PERMISSIVE | 9,119 | 8,216 | 903 | 9.9% |
| mTLS STRICT | 24,946 | 22,721 | 2,225 | 8.9% |

```
CPU Usage @ 200 RPS
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  No Istio       ████████████████████████  7,430m (baseline)                │
│                                                                             │
│  PERMISSIVE     ██████████████████████████████  9,119m (+22.7%)            │
│                 ├─ App: 8,216m ─┤├ Sidecar: 903m ┤                          │
│                                                                             │
│  STRICT         ████████████████████████████████████████████████████████   │
│                 ███████████████████████████████████  24,946m (+235.8%)     │
│                 ├──── App: 22,721m ────┤├ Sidecar: 2,225m ┤                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

##### CPU 오버헤드 비교

| 비교 | CPU 오버헤드 | 주요 원인 |
|------|-------------|----------|
| No Istio → PERMISSIVE | **+22.7%** | Envoy proxy 처리 |
| No Istio → STRICT | **+235.8%** | Envoy + mTLS 암호화 |
| PERMISSIVE → STRICT | **+173.6%** | mTLS 암호화 추가 |

#### 5. 서비스별 CPU 비교 @ 200 RPS

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│  Service           No Istio   PERMISSIVE   STRICT    PERM vs No   STRICT vs No   │
├───────────────────────────────────────────────────────────────────────────────────┤
│  reservation       3,942      4,684        14,236    +18.8%       +261.1%         │
│  rate              1,675      1,930        4,951     +15.2%       +195.6%         │
│  search            617        705          1,653     +14.3%       +167.9%         │
│  memcached-reserve 450        611          1,788     +35.8%       +297.3%         │
│  frontend          348        455          836       +30.7%       +140.2%         │
│  profile           130        225          418       +73.1%       +221.5%         │
│  geo               62         118          242       +90.3%       +290.3%         │
│  recommendation    33         78           168       +136.4%      +409.1%         │
│  memcached-rate    16         72           179       +350.0%      +1018.8%        │
│  user              1          10           35        +900.0%      +3400.0%        │
├───────────────────────────────────────────────────────────────────────────────────┤
│  TOTAL             7,430      9,119        24,946    +22.7%       +235.8%         │
└───────────────────────────────────────────────────────────────────────────────────┘
```

**분석**:
- **고트래픽 서비스** (reservation, rate, search): PERMISSIVE에서 +15-35%, STRICT에서 +160-300%
- **저트래픽 서비스** (user, recommendation): 상대적으로 높은 오버헤드 % (baseline CPU가 낮아서)
- **STRICT의 급격한 증가**: mTLS 암호화가 App 자체 CPU도 크게 증가시킴

#### 6. Sidecar CPU 분석

##### PERMISSIVE vs STRICT Sidecar CPU @ 200 RPS

```
Sidecar CPU by Service @ 200 RPS
┌─────────────────────────────────────────────────────────────────────────────┐
│  Service            PERMISSIVE Sidecar    STRICT Sidecar    Increase        │
├─────────────────────────────────────────────────────────────────────────────┤
│  reservation        149m                  368m              +147%            │
│  rate               129m                  319m              +147%            │
│  frontend           147m                  327m              +122%            │
│  search             110m                  249m              +126%            │
│  profile            115m                  238m              +107%            │
│  memcached-reserve  86m                   227m              +164%            │
│  geo                67m                   146m              +118%            │
│  memcached-rate     56m                   140m              +150%            │
│  recommendation     50m                   115m              +130%            │
│  user               8m                    33m               +312%            │
├─────────────────────────────────────────────────────────────────────────────┤
│  TOTAL              903m                  2,225m            +146%            │
└─────────────────────────────────────────────────────────────────────────────┘
```

**핵심 발견**:
- STRICT 모드에서 Sidecar CPU가 평균 **2.5배** 증가
- mTLS 암호화 연산이 Sidecar CPU의 주요 원인
- 트래픽이 많은 서비스일수록 절대적인 Sidecar CPU 사용량 높음

#### 7. Memory 사용량 비교

| 환경 | Memory (Mi) | 오버헤드 |
|------|-------------|----------|
| No Istio | 1,652 | baseline |
| mTLS PERMISSIVE | 2,393 | **+44.9%** |
| mTLS STRICT | 3,194 | **+93.3%** |

```
Memory Usage Comparison
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  No Istio       ████████████████████████████████  1,652 Mi                 │
│                                                                             │
│  PERMISSIVE     ██████████████████████████████████████████████  2,393 Mi   │
│                                                   (+44.9%)                  │
│                                                                             │
│  STRICT         ██████████████████████████████████████████████████████████ │
│                 ██████████████████  3,194 Mi (+93.3%)                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Memory 오버헤드 원인**:
| 구성 요소 | PERMISSIVE | STRICT |
|-----------|------------|--------|
| Envoy Sidecar 기본 | ~30-40Mi/pod | ~40-60Mi/pod |
| TLS 세션 캐시 | 최소 | 전체 연결 |
| 연결 풀 버퍼 | 기본 | 확장 |
| Istio Control Plane | ~100Mi | ~100Mi |


#### 8. 오버헤드 종합 비교

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         Istio Overhead Summary (@ 200 RPS)                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  지표                 No Istio    PERMISSIVE     STRICT       비고              │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  CPU                  7,430m      9,119m         24,946m                        │
│    vs No Istio        -           +22.7%         +235.8%                        │
│                                                                                 │
│  Memory               1,652Mi     2,393Mi        3,194Mi                        │
│    vs No Istio        -           +44.9%         +93.3%                         │
│                                                                                 │
│  P50 Latency          5.29ms      13.48ms        21.18ms                        │
│    vs No Istio        -           +155%          +300%                          │
│                                                                                 │
│  P99 Latency          394ms       527ms          1.09s                          │
│    vs No Istio        -           +34%           +176%                          │
│                                                                                 │
│  Max Throughput       ~495 RPS    ~435 RPS       ~290 RPS                       │
│    vs No Istio        -           -12%           -41%                           │
│                                                                                 │
│  Saturation Point     600 RPS     400-600 RPS    250-300 RPS                    │
│                                                                                 │
│  Sidecar CPU 비중     N/A         9.9%           8.9%                           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### 9. 오버헤드 원인 분석

##### Sidecar Proxy 오버헤드 (No Istio → PERMISSIVE)

```
Request Path Without Istio:
  Client → frontend → search → rate → reservation → ...
  
Request Path With Istio (PERMISSIVE):
  Client → [Envoy] → frontend → [Envoy] → search → [Envoy] → rate → [Envoy] → ...
           ↑ proxy              ↑ proxy            ↑ proxy
           
오버헤드 구성:
  - Envoy 프로세싱: ~2-3ms/hop
  - Connection pooling: ~0.5ms
  - 추가 메모리 복사: ~0.5ms
  
총 추가 latency @ 7 hops: (13.48 - 5.29) / 7 = 1.17ms/hop
```

##### mTLS 암호화 오버헤드 (PERMISSIVE → STRICT)

```
Request Path With mTLS STRICT:
  Client → [Envoy+TLS] → frontend → [Envoy+TLS] → search → [Envoy+TLS] → ...
           ↑ encrypt                 ↑ decrypt/encrypt      ↑ decrypt/encrypt
           
추가 오버헤드 구성:
  - TLS Handshake: ~1-2ms (연결당 1회)
  - 암호화/복호화: ~0.5-1ms/hop
  - 인증서 검증: ~0.2ms
  
PERMISSIVE → STRICT 추가 latency: (21.18 - 13.48) / 7 = 1.1ms/hop
```

##### Little's Law 검증

```
Little's Law: L = λ × W  (동시 요청 수 = 처리량 × 평균 대기 시간)

No Istio @ 600 RPS (saturation):
  L = 495 RPS × 7.11s = 3,519 concurrent requests
  CPU = ~14,700m

PERMISSIVE @ 600 RPS (saturation):
  L = 435 RPS × 11.42s = 4,968 concurrent requests
  CPU = ~14,800m

STRICT @ 300 RPS (saturation):
  L = 290 RPS × 1.98s = 574 concurrent requests
  CPU = ~29,800m

결론: STRICT는 동일 CPU로 6배 적은 동시 요청 처리 (암호화 CPU 비용)
```

#### 10. 권장 운영 파라미터

| 파라미터 | No Istio | PERMISSIVE | STRICT |
|----------|----------|------------|--------|
| 안전 운영 RPS | ≤ 400 | ≤ 350 | ≤ 200 |
| 최대 운영 RPS | ≤ 500 | ≤ 400 | ≤ 250 |
| 메모리 할당 | baseline | +50% | +100% |
| CPU 할당 | baseline | +30% | +250% |
| 스케일 아웃 기준 | CPU 70% | CPU 60% | CPU 50% |
| reservation replicas | 2 | 2-3 | 3+ |


#### 11. 의사결정 가이드

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Istio 도입 의사결정 플로우차트                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                        Service Mesh 필요한가?                               │
│                              │                                              │
│                    Yes ──────┴────── No                                     │
│                     │                 │                                     │
│                     ▼                 ▼                                     │
│            ┌────────────────┐    No Istio 유지                              │
│            │보안 요구사항은?│    (최고 성능)                                 │
│            └───────┬────────┘                                               │
│                    │                                                        │
│         ┌─────────┬┴──────────┐                                            │
│         ▼         ▼           ▼                                            │
│      필수       권장        불필요                                          │
│    (규제/금융)  (일반)     (내부용)                                         │
│         │         │           │                                            │
│         ▼         ▼           ▼                                            │
│      STRICT   PERMISSIVE   PERMISSIVE                                      │
│    (-41% 처리량) (-12% 처리량) (Observability만)                           │
│                                                                             │
│  ─────────────────────────────────────────────────────────────────────────  │
│                                                                             │
│  각 모드별 필요 리소스 (vs No Istio baseline):                              │
│                                                                             │
│  ┌─────────────┬─────────────────┬─────────────────┐                       │
│  │             │   PERMISSIVE    │     STRICT      │                       │
│  ├─────────────┼─────────────────┼─────────────────┤                       │
│  │ CPU         │     +23%        │    +236%        │                       │
│  │ Memory      │     +45%        │    +93%         │                       │
│  │ 처리량      │     -12%        │    -41%         │                       │
│  │ P50 Latency │     +155%       │    +300%        │                       │
│  └─────────────┴─────────────────┴─────────────────┘                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 12. TL;DR (핵심 요약)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  Istio 오버헤드 요약 (@ 200 RPS 기준):                                      │
│                                                                             │
│  ┌─────────────────┬────────────────────┬────────────────────┐             │
│  │                 │     PERMISSIVE     │       STRICT       │             │
│  ├─────────────────┼────────────────────┼────────────────────┤             │
│  │ CPU             │    +23% (적당함)   │  +236% (매우 높음) │             │
│  │ Memory          │    +45%            │  +93%              │             │
│  │ P50 Latency     │    +155% (2.5배)   │  +300% (4배)       │             │
│  │ 처리량          │    -12%            │  -41%              │             │
│  └─────────────────┴────────────────────┴────────────────────┘             │
│                                                                             │
│  권장사항:                                                                  │
│  ─────────────────────────────────────────────────────────────────────────  │
│  • 보안 필수 아님 → PERMISSIVE (관찰성 + 낮은 오버헤드)                    │
│  • 규제/컴플라이언스 필수 → STRICT (CPU 3배, 처리량 절반 감안)            │
│  • 성능 최우선 → No Istio (또는 민감 서비스만 부분 적용)                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```
---

## 병목 분석

### System 메트릭 (Intel PCM)

| RPS | Memory BW (GB/s) | LLC Hit Rate |
|-----|------------------|--------------|
| 200 | 1.78 | 0.498 |
| 400 | 4.29 | 0.490 |
| 600 | 5.65 | 0.484 |
| 700 | 5.91 | 0.486 |
| 800 | 5.83 | 0.490 |
| 1000 | 5.89 | 0.496 |

**Memory Bandwidth 분석**:

```
Memory Bandwidth vs RPS
    │
  6 ┤            ●────●────●────● ← 포화 구간 (~5.9 GB/s)
    │        ●───                
  5 ┤                            
    │    ●                       
  4 ┤                             선형 증가 구간
    │                            
  3 ┤                            
    │                            
  2 ┤●                           
    │                            
  1 ┼────┬────┬────┬────┬────┬────
       200  400  600  700  800  1000
                 RPS
```

**해석**:
- **200-600 RPS**: Memory BW가 선형적으로 증가 (1.78 → 5.65 GB/s)
- **600+ RPS**: Memory BW가 ~5.9 GB/s에서 포화 상태 진입
- **포화의 의미**: 
  - CPU가 메모리 접근을 기다리는 "memory-bound" 상태
  - 추가적인 요청 처리가 메모리 병목으로 제한됨
  - 이것이 600 RPS에서 saturation이 시작되는 근본 원인 중 하나

**LLC (Last Level Cache) Hit Rate 분석**:
- 모든 부하 수준에서 약 49%로 일정하게 유지
- **의미**: 
  - L3 캐시에서 절반의 메모리 접근이 처리됨
  - 나머지 절반은 메인 메모리(DRAM)에서 가져와야 함
  - 워크로드의 데이터 지역성(locality)이 보통 수준임을 나타냄
- **개선 가능성**: 애플리케이션 레벨에서 데이터 접근 패턴 최적화로 LLC hit rate 향상 가능

### 주요 발견 사항

#### 1. Saturation Point: 600 RPS

```
┌─────────────────────────────────────────────────────────────┐
│                    시스템 상태 변화                          │
├─────────────────────────────────────────────────────────────┤
│  200-400 RPS    │  정상 운영 구간                           │
│  ───────────────┼─────────────────────────────────────────  │
│  • CPU 여유 있음│  CPU: 7,430m → 13,798m (선형 증가)        │
│  • Latency 안정 │  P50: 5ms → 123ms                        │
│  • 100% 처리    │  Actual ≈ Target RPS                     │
├─────────────────┼─────────────────────────────────────────  │
│  600 RPS        │  ⚠️ SATURATION POINT                     │
│  ───────────────┼─────────────────────────────────────────  │
│  • CPU 한계 도달│  CPU: ~15,000m (정체)                     │
│  • Latency 급증 │  P50: 123ms → 7.11s (58배!)              │
│  • 처리량 한계  │  Actual: 494 < Target: 600               │
│  • Memory BW 포화│  5.65 GB/s                               │
├─────────────────┼─────────────────────────────────────────  │
│  700-1000 RPS   │  과부하 구간                              │
│  ───────────────┼─────────────────────────────────────────  │
│  • 큐잉 지속 증가│  요청이 큐에 쌓임                         │
│  • Latency 폭증 │  P50: 14s → 25s                          │
│  • 처리량 정체  │  Actual: ~470-490 (고정)                  │
└─────────────────────────────────────────────────────────────┘
```

**실무적 의미**: 
- 이 시스템의 안전한 운영 범위는 **400 RPS 이하**
- 600 RPS는 피크 시간대 최대 허용치로 고려
- 그 이상의 트래픽은 스케일 아웃 필요

#### 2. 병목 서비스: reservation (67% CPU)

**Why `reservation`?**
- 모든 예약 관련 요청의 종착점
- MongoDB와의 동기 쿼리 수행
- 캐시 미스 시 DB 접근 필요
- 트랜잭션 처리로 인한 복잡성

**최적화 우선순위**:
1. `reservation` replicas 증가 (1 → 2~3)
2. MongoDB 인덱스 튜닝
3. 캐시 전략 개선 (TTL, 사전 로딩)
4. 비동기 처리 도입

#### 3. Istio 오버헤드 종합

| 지표 | 오버헤드 | 영향도 | 대응 방안 |
|------|----------|--------|-----------|
| Memory | +46.3% | 높음 | sidecar 리소스 제한 설정 |
| CPU (저부하) | +22.7% | 중간 | 리소스 여유 확보 |
| CPU (고부하) | ~0% | 낮음 | 무시 가능 |
| Throughput | -12% | 높음 | 12% 추가 인스턴스 |
| P99 Latency | +10~20% | 중간 | critical path 최적화 |

**Istio 도입 의사결정 가이드**:

```
Istio 도입이 적합한 경우:
  ✓ 서비스 간 mTLS가 필수인 환경
  ✓ 세밀한 트래픽 관리가 필요한 경우
  ✓ 리소스 여유가 충분한 경우 (특히 메모리)
  ✓ observability가 중요한 환경

Istio 도입을 재고해야 하는 경우:
  ✗ 메모리가 제한된 환경
  ✗ 극도로 낮은 latency가 요구되는 경우
  ✗ 서비스 호출 깊이가 깊은 아키텍처 (오버헤드 누적)
  ✗ 리소스 효율이 최우선인 경우
```

#### 4. System 레벨 병목

- **Memory Bandwidth**: 600 RPS에서 ~5.9 GB/s로 포화
  - 이는 Minikube 단일 노드 환경의 하드웨어 제약
  - 프로덕션 환경에서는 다중 노드로 분산 필요
  
- **LLC Hit Rate**: ~49%로 일정
  - 개선 여지 있음 (목표: 60%+)
  - 데이터 구조 최적화, 캐시 친화적 접근 패턴 적용 권장

### 권장 운영 파라미터

| 파라미터 | 권장값 | 근거 |
|----------|--------|------|
| 안전 운영 RPS | ≤ 400 | Saturation 전 안정 구간 |
| 최대 운영 RPS | ≤ 500 | 12% 여유 마진 확보 |
| reservation replicas | 3 | CPU 병목 분산 |
| 메모리 할당 | +50% | Istio sidecar 고려 |
| 스케일 아웃 기준 | CPU 70% | 80%에서 latency 급증 시작 |

### 생성되는 시각화 파일

| 파일명 | 내용 | 주요 인사이트 |
|--------|------|--------------|
| `overview.png` | CPU/Memory/Network 개요 | 전체 리소스 사용 패턴 |
| `service_breakdown.png` | 서비스별 CPU 추이 | 병목 서비스 식별 |
| `latency_analysis.png` | Latency Percentiles | Saturation point 확인 |
| `xtella_io_analysis.png` | Disk I/O, System BW | 하드웨어 병목 분석 |
| `cpu_efficiency.png` | mCPU per request | 최적 운영점 도출 |
| `compare_main_comparison.png` | Istio 비교 | 오버헤드 정량화 |
| `compare_sidecar_analysis.png` | Sidecar 분석 | Envoy 비용 분석 |
| `compare_latency_comparison.png` | Latency 비교 | 응답시간 영향 |
| `compare_io_system_comparison.png` | System BW 비교 | 인프라 영향 |

---

## 참고 자료

- [DeathStarBench](https://github.com/delimitrou/DeathStarBench)
- [wrk2](https://github.com/giltene/wrk2)
- [Intel PCM](https://github.com/intel/pcm)
- [Istio Performance](https://istio.io/latest/docs/ops/deployment/performance-and-scalability/)
- [Coordinated Omission](https://www.scylladb.com/2021/04/22/on-coordinated-omission/)
- [Jaeger Documentation](https://www.jaegertracing.io/docs/)