# gRPC 부하 테스트 환경에서의 처리량 병목 분석 보고서

> DeathStarBench HotelReservation 애플리케이션 분석

---

## 1. 실험 목적

본 보고서의 목적은 gRPC 부하 테스트 환경에서 요청 처리량(RPS)이 특정 수준 이상 증가하지 않는 원인을 분석하고, 그 병목 지점을 실험적으로 규명하는 것이다.

특히 다음 질문에 답하는 것을 목표로 한다:

- CPU 사용률이 100%에 도달하지 않았음에도 처리량 상한이 발생하는 이유는 무엇인가?
- 해당 병목은 네트워크/서버 병목이 아닌가?
- HTTP/2 동시성 제한(stream limit)에 의한 병목은 아닌가?
- 병렬화되지 않는 CPU 실행 경로가 실제로 존재하는가?
- DeathStarBench 애플리케이션의 gRPC 설정은 어떻게 되어 있는가?

---

## 2. 실험 환경

| 항목 | 내용 |
|------|------|
| 부하 생성기 | ghz (Go 기반 gRPC benchmark tool), wrk2 |
| 대상 서비스 | DeathStarBench HotelReservation (user gRPC service) |
| 배치 환경 | Kubernetes (kubeadm 기반), 단일 노드 |
| 통신 방식 | gRPC over HTTP/2 (h2c, cleartext) |
| CPU | 36 cores |
| OS | Linux (Ubuntu) |
| 측정 도구 | ghz, wrk2, perf record/report, htop, taskset, cpupower, tcpdump, tshark |

---

## 3. 관측된 현상

### 3.1 RPS 상한 현상

- `-c`, `--connections` 값을 증가시켜도 단일 ghz 프로세스 기준 RPS는 약 **48k 수준에서 포화**
- CPU 평균 사용률은 **모든 코어에서 100%에 도달하지 않음**
- ghz 프로세스를 **2개로 분리 실행**하면 합산 RPS는 거의 선형적으로 증가

→ 서버(user service)나 네트워크 병목이 아님을 시사

---

## 4. 대안 가설 검증: HTTP/2 동시 Stream 제한

### 4.1 가설

> "HTTP/2의 `SETTINGS_MAX_CONCURRENT_STREAMS` 제한에 의해 동시에 처리 가능한 요청 수가 제한된 것이 아닌가?"

### 4.2 HTTP/2 SETTINGS 프레임 분석

`tcpdump` 및 `tshark/Wireshark`를 이용하여 gRPC 연결 초기에 교환되는 HTTP/2 SETTINGS 프레임을 분석하였다.

- `SETTINGS_MAX_CONCURRENT_STREAMS` 항목이 **명시적으로 광고되지 않음**
- HTTP/2 RFC 상 해당 항목이 없을 경우 이론적 default는 "무제한"
- gRPC-Go 서버의 현재 기본값은 `math.MaxUint32` (사실상 무제한)

### 4.3 DeathStarBench gRPC 설정 분석

실제 소스 코드를 분석한 결과:

**Client 측 (frontend → user service) - `dialer/dialer.go`:**
```go
dialopts := []grpc.DialOption{
    grpc.WithKeepaliveParams(keepalive.ClientParameters{
        Timeout:             120 * time.Second,
        PermitWithoutStream: true,
    }),
}
```

**Server 측 (user service) - `services/user/server.go`:**
```go
opts := []grpc.ServerOption{
    grpc.KeepaliveParams(keepalive.ServerParameters{
        Timeout: 120 * time.Second,
    }),
    grpc.KeepaliveEnforcementPolicy(keepalive.EnforcementPolicy{
        PermitWithoutStream: true,
    }),
    grpc.UnaryInterceptor(otgrpc.OpenTracingServerInterceptor(s.Tracer)),
}
srv := grpc.NewServer(opts...)  // MaxConcurrentStreams 설정 없음
```

### 4.4 gRPC 설정 요약

| 항목 | Client (frontend) | Server (user) |
|------|-------------------|---------------|
| Connection 수 | 서비스당 **1개** | - |
| Connection Pool | **없음** | - |
| MaxConcurrentStreams | 설정 없음 | 설정 없음 (기본값 무제한) |
| Keepalive Timeout | 120초 | 120초 |
| Load Balancing | round_robin | - |

### 4.5 결론

ghz의 `-c` 옵션은 HTTP/2 stream 개수를 직접 제어하는 값이 아니라, 클라이언트 내부에서 동시에 in-flight 상태로 유지할 수 있는 RPC 요청 수이다. 서버 측 MaxConcurrentStreams가 무제한이므로, **HTTP/2 stream limit에 의해 직접적으로 발생한 병목이 아님**을 확인하였다.

---

## 5. MaxConcurrentStreams 설정 변경 실험

### 5.1 실험 목적

gRPC 서버의 `MaxConcurrentStreams` 설정이 실제로 동작하는지, 그리고 성능에 어떤 영향을 미치는지 확인한다.

### 5.2 실험 방법

`services/user/server.go`를 수정하여 `grpc.MaxConcurrentStreams()` 옵션 추가 후 재빌드/재배포:

```go
opts := []grpc.ServerOption{
    grpc.MaxConcurrentStreams(100),  // 값 변경하며 실험
    // ... 기존 옵션들
}
```

테스트 명령어:
```bash
./wrk -t 8 -c 2000 -d 30s -L \
    -s ./DeathStarBench/hotelReservation/wrk2/scripts/hotel-reservation/user_only.lua \
    http://localhost:31643 -R 20000
```

### 5.3 실험 결과

| MaxConcurrentStreams | RPS | 비고 |
|---------------------|-----|------|
| 1 | 3,610 | 심각한 병목 |
| 10 | 9,751 | +170% 증가 |
| 100 | 9,756 | plateau |
| 150 | 9,745 | plateau |
| 200 | 9,758 | plateau |

### 5.4 결론

- **설정이 정상 동작함을 확인**: MaxConcurrentStreams=1에서 3,610 RPS로 제한된 것이 증거
- **10 이상에서 plateau**: MaxConcurrentStreams는 더 이상 병목이 아니며, 다른 곳에 병목 존재
- 약 10개의 concurrent streams면 충분하며, 그 이상에서는 다른 요소가 병목

---

## 6. CPU 주파수 스케일링 실험

### 6.1 실험 설계의 문제점과 보완

초기 실험에서는 ghz와 user service가 동일 노드에서 실행되어, CPU 주파수 변경 시 양쪽 모두 영향을 받는 문제가 있었다.

이를 보완하기 위해 **코어 격리 실험**을 수행하였다:
- Core 0-17: user service 전용 (주파수 고정)
- Core 18-35: ghz 전용 (주파수 변경)

```bash
# user service 코어 고정
sudo taskset -apc 0-17 <user_service_pid>
sudo cpupower -c 0-17 frequency-set -d 2.5GHz -u 2.5GHz

# ghz 코어 및 주파수 설정
sudo cpupower -c 18-35 frequency-set -u <target_freq>
taskset -c 18-35 ghz --insecure --proto user.proto --call user.User.CheckUser \
    -d '{"username": "Cornell_1", "password": "1111111111"}' \
    -c 400 --connections 1 --rps 120000 -z 30s 10.111.71.231:8086
```

### 6.2 실험 결과

**실험 1: user 고정 안함, 0-17 코어 4GHz**

| ghz 주파수 (18-35) | RPS |
|-------------------|-----|
| 1GHz | 48,959 |
| 2GHz | 80,637 |
| 3GHz | 97,761 |

**실험 2: user 고정 안함, 0-17 코어 2.5GHz**

| ghz 주파수 (18-35) | RPS |
|-------------------|-----|
| 1GHz | 48,534 |
| 2GHz | 79,364 |
| 3GHz | 94,085 |

**실험 3: user 0-17 고정, 0-17 코어 2.5GHz**

| ghz 주파수 (18-35) | RPS |
|-------------------|-----|
| 1GHz | 63,247 |
| 2GHz | 97,324 |
| 3GHz | 104,557 |

### 6.3 코어 격리 효과 분석

실험 2와 3을 비교 (동일 조건: 0-17 = 2.5GHz):

| ghz 주파수 | user 고정 안함 | user 고정 | 증가율 |
|-----------|---------------|----------|--------|
| 1GHz | 48,534 | 63,247 | **+30.3%** |
| 2GHz | 79,364 | 97,324 | **+22.6%** |
| 3GHz | 94,085 | 104,557 | **+11.1%** |

**발견**: ghz가 느릴수록 격리 효과가 더 큼

### 6.4 해석

- **ghz가 느릴 때 (1GHz)**: ghz 스레드가 CPU를 오래 점유하여 user service와 경쟁이 심함. context switch, 캐시 flush 오버헤드가 큼. 격리 시 30% 향상.
- **ghz가 빠를 때 (3GHz)**: ghz가 빨리 처리하여 경쟁 오버헤드 비중이 상대적으로 작음. 격리 효과가 11%로 감소.

### 6.5 결론

CPU 주파수 증가에 따라 RPS가 단조 증가하며, 이는 **처리량 상한이 CPU 실행 성능에 의해 직접적으로 제한**되고 있음을 증명한다. 또한 워크로드 격리만으로 최대 30%의 성능 향상이 가능함을 확인하였다.

---

## 7. perf 기반 병목 경로 분석

### 7.1 프로파일링 결과 요약

```
Overhead  Symbol
  7.16%   runtime.mapassign_faststr
  5.99%   runtime.findObject
  4.12%   text/template.goodName
  3.96%   runtime.typePointers.next
  3.78%   runtime.scanobject
  3.62%   runtime.wbBufFlush1
  3.59%   internal/runtime/maps.(*Iter).Next
  2.69%   internal/runtime/maps.(*table).uncheckedPutSlot
  2.35%   runtime.bulkBarrierPreWrite
  2.28%   runtime.gcmarknewobject
  2.18%   runtime.mallocgcSmallScanNoHeader
  2.06%   aeshashbody
  ...
```

### 7.2 병목 분류

| 카테고리 | 함수들 | 비율 | 병렬화 제한 요인 |
|----------|--------|------|-----------------|
| **Map 연산** | mapassign_faststr, maps.(*Iter).Next, uncheckedPutSlot, grow, aeshashbody | ~18% | Map 연산은 goroutine-safe하지 않으며, 동일 map에 대한 빈번한 접근은 논리적 직렬화, hash 계산 및 cache-line contention을 유발 |
| **GC Scanning** | findObject, scanobject, typePointers.next, gcmarknewobject, greyobject | ~13% | GC는 25% CPU 제한, Mark Assist 발동 |
| **Write Barrier** | wbBufFlush1, bulkBarrierPreWrite, gcWriteBarrier | ~7% | 포인터 쓰기마다 오버헤드 |
| **Memory Allocation** | mallocgcSmallScanNoHeader, mallocgc, getempty | ~3% | mcentral/mheap 접근 시 락 필요 |
| **Lock Contention** | lock2, unlock2, procyield, native_queued_spin_lock_slowpath | ~2% | 커널 레벨 락 경합 |

### 7.3 핵심 발견

실제 비즈니스 로직(`text/template`, `grpc`)은 약 5% 정도에 불과하며, 대부분이 **Go 런타임 오버헤드 (map 연산, GC, 메모리 관리)**이다.

---

## 8. Go GC의 병렬성과 CPU 병목

### 8.1 Go GC 구조

Go GC는 **Tri-color Mark-and-Sweep** 알고리즘 기반의 Concurrent GC를 사용한다:

```
Mark Setup (STW) → Concurrent Mark → Mark Termination (STW) → Concurrent Sweep
```

### 8.2 GC의 CPU 사용 제한

Go GC는 기본적으로 전체 CPU의 약 25% 수준을 전용 GC worker로 사용하도록 설계되어 있으며, 추가적인 GC 작업은 Mark Assist를 통해 애플리케이션 goroutine에 분산된다.
- **Dedicated Workers**: `GOMAXPROCS/4`개, Mark 단계 동안 GC 작업만 수행
- **Fractional Workers**: 목표 CPU 사용률을 맞추기 위해 필요시 GC 작업 수행

### 8.3 Mark Assist

애플리케이션이 메모리를 빠르게 할당하면 GC가 따라잡지 못할 수 있다. 이때 **Mark Assist**가 발동되어 할당하려는 goroutine이 GC 작업을 수행해야 한다. 이는 **latency spike**의 주요 원인이 된다.

### 8.4 병렬화 제한 요인 정의

본 보고서에서 "병렬화 불가능"이란, goroutine 수가 증가하더라도 **처리율(ops/sec)이 비례하여 증가하지 않는 실행 경로**를 의미한다.

| 유형 | 예시 | 특성 |
|------|------|------|
| Serialized by lock | map 연산, sync.Mutex | 한 번에 하나만 실행 |
| Rate-limited parallelism | GC (25% CPU cap) | 병렬이지만 상한 존재 |
| Shared resource contention | cache line bouncing | 병렬이지만 간섭 발생 |

---

## 9. CPU 사용률 100% 미도달 상태에서의 CPU 병목

### 9.1 현상

- 병목 경로는 ns~µs 단위의 짧은 임계 구간
- 고빈도로 반복되며 throughput ceiling 형성
- OS 스케줄러에 의해 여러 코어에서 분산 실행됨

### 9.2 결과

- 평균 CPU 사용률은 낮아 보이나
- **처리율에는 명확한 상한 발생**

이는 CPU 사용률이 100%에 도달하지 않았음에도 **명확한 CPU 병목이 존재할 수 있음을 보여주는 사례**이다.

---

## 10. 종합 결론

### 10.1 병목 원인 요약

| 병목 유형 | 증거 | 기여도 |
|----------|------|--------|
| **Go 런타임 내부 직렬화 (GC, map)** | 주파수 ↑ → RPS ↑, perf 프로파일 | 주요 병목 |
| **코어 경쟁 (cache thrashing, context switch)** | 격리 → RPS 11~30% ↑ | 부가 병목 |
| HTTP/2 stream 제한 | MaxConcurrentStreams 실험 | 병목 아님 (10 이상에서 무관) |
| 네트워크 대역폭 | CPU 주파수 실험 | 병목 아님 |

### 10.2 주요 발견

1. **ghz 기반 gRPC 부하 테스트에서 관측된 처리량 상한은 네트워크, HTTP/2 stream 제한, gRPC 서버, Kubernetes 병목이 아니다.**

2. **DeathStarBench HotelReservation의 gRPC 설정 분석 결과:**
   - 서비스 간 connection 수: 1개 (connection pool 없음)
   - MaxConcurrentStreams: 미설정 (기본값 무제한)
   - 설정 변경이 정상 동작함을 실험으로 확인

3. **CPU 주파수 스케일링 실험을 통해 CPU 실행 성능 변화가 RPS 변화로 직접 이어짐을 실험적으로 증명하였다.**

4. **코어 격리 실험을 통해 워크로드 간 CPU 경쟁이 최대 30%의 성능 저하를 유발할 수 있음을 확인하였다.**

5. **perf 분석 결과, 병목은 Go 런타임 내부의 GC 및 map 기반 통계 집계 경로에 존재한다.**

### 10.3 최종 요약

> ghz의 처리량 상한은 HTTP/2나 서버가 아닌, 병렬화되지 않는 Go 런타임 내부의 GC, map 기반 통계 집계, 메모리 관리 경로가 결합된 CPU execution-bound 병목에 의해 발생한다.

---

## 부록 A: 실험 명령어 참조

### A.1 CPU 주파수 설정

```bash
# 특정 코어 주파수 고정
sudo cpupower -c 0-17 frequency-set -d 2.5GHz -u 2.5GHz
sudo cpupower -c 18-35 frequency-set -u 3.0GHz
```

### A.2 프로세스 코어 고정

```bash
# user service PID 확인
sudo crictl ps | grep user
sudo crictl inspect <container_id> | grep pid

# 코어 고정 (모든 스레드 포함)
sudo taskset -apc 0-17 <pid>
```

### A.3 ghz 부하 테스트

```bash
taskset -c 18-35 ghz --insecure \
    --proto user.proto \
    --call user.User.CheckUser \
    -d '{"username": "Cornell_1", "password": "1111111111"}' \
    -c 400 --connections 1 --rps 120000 -z 30s \
    10.111.71.231:8086
```

### A.4 wrk2 부하 테스트

```bash
./wrk -t 8 -c 2000 -d 30s -L \
    -s ./DeathStarBench/hotelReservation/wrk2/scripts/hotel-reservation/user_only.lua \
    http://localhost:31643 -R 20000
```

### A.5 perf 프로파일링

```bash
# 기록
sudo perf record -g -p <pid> -- sleep 30

# 분석
sudo perf report
```

---

## 부록 B: DeathStarBench gRPC 코드 수정

### B.1 MaxConcurrentStreams 설정 추가

`services/user/server.go`:

```go
opts := []grpc.ServerOption{
    grpc.MaxConcurrentStreams(100),  // 추가
    grpc.KeepaliveParams(keepalive.ServerParameters{
        Timeout: 120 * time.Second,
    }),
    grpc.KeepaliveEnforcementPolicy(keepalive.EnforcementPolicy{
        PermitWithoutStream: true,
    }),
    grpc.UnaryInterceptor(
        otgrpc.OpenTracingServerInterceptor(s.Tracer),
    ),
}
```

### B.2 빌드 및 배포

```bash
# Docker 이미지 빌드
cd ~/DeathStarBench_k8s/DeathStarBench/hotelReservation
docker build -t hotel-reservation:custom-v1 .

# containerd로 이미지 가져오기
docker save hotel-reservation:custom-v1 -o hotel-reservation.tar
sudo ctr -n k8s.io images import hotel-reservation.tar

# deployment.yaml 수정 후 재배포
kubectl apply -f kubernetes/user/user-deployment.yaml -n hotel-res
```