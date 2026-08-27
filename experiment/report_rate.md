# Hotel Reservation Scalability Analysis: 병목 이동 현상 분석

**MSA 환경에서의 캐싱 전략과 병목 이동(Bottleneck Shifting)에 관한 분석**

## 1. 프로젝트 개요 (Overview)

본 프로젝트는 **DeathStarBench**의 Hotel Reservation 마이크로서비스를 대상으로, 리소스 확장(Scale-up)에 따른 성능 변화를 분석했습니다.

우리는 **"캐시를 적용하여 I/O를 제거하면 성능이 향상될 것이다"**라는 일반적인 가정을 검증하고자 했습니다. 실험 결과, 특정 서비스의 I/O 대기 시간이 사라지면서 하위 서비스(`rate`)로 부하가 집중되어 **병목이 이동(Bottleneck Shifting)**하는 현상을 관찰했습니다.

**주의:** 본 보고서의 일부 결론은 가설 단계이며, 추가 검증이 필요합니다. 검증이 필요한 부분은 명시적으로 표기했습니다.

---

## 2. 실험 환경 (Experimental Setup)

### 2.1 테스트 도구 및 시나리오

* **Benchmark Tool:** `wrk` (Lua Script 지원)
* **Target System:** Kubernetes (Minikube), DeathStarBench HotelReservation
* **Target Service:** `reservation` (CPU Limit을 1~14 Core로 조절하며 측정)

| 시나리오 | Alias | Lua Script | 특징 | 목적 |
|----------|-------|------------|------|------|
| **Random** | `Standard` | `search_only.lua` | 수천 개 Hotel ID 랜덤 요청. **DB 접근 발생 (Cache Miss).** | **Baseline.** 일반적인 트래픽 상황 (I/O Latency 존재). |
| **Fixed** | `1-Key` | `search_only_fixed.lua` | 단 1개의 Hotel ID 반복 요청. **100% Cache Hit.** | 단일 키에 대한 Memcached 동작 확인. |
| **Distributed** | `4-Keys` | `search_only_fixed_four.lua` | 4개의 Hotel ID 라운드 로빈. **100% Cache Hit + 키 분산.** | DB 접근을 제거한 캐시 최적화 조건. |

### 2.2 실험 실행 명령어

```bash
# 1. Random Scenario (Cache Miss 발생)
./wrk -t 4 -c 100 -d 120s -L -s .../search_only.lua http://localhost:31643 -R 3000

# 2. Fixed Scenario (단일 키 Cache Hit)
./wrk -t 4 -c 100 -d 120s -L -s .../search_only_fixed.lua http://localhost:31643 -R 3000

# 3. Distributed Scenario (분산 키 Cache Hit)
./wrk -t 4 -c 100 -d 120s -L -s .../search_only_fixed_four.lua http://localhost:31643 -R 3000
```

**모든 시나리오는 동일한 `-R 3000` 조건에서 테스트되었습니다.**

---

## 3. 실험 데이터 (Raw Data)

### 3.1 RPS (Throughput) 종합 비교

리소스(`reservation` CPU Limit) 증가에 따른 처리량 변화입니다.

| Cores | Random (Standard) | Fixed (1-Key) | Distributed (4-Keys) | 비고 |
|-------|-------------------|---------------|----------------------|------|
| **1** | 350 | 337 | 341 | CPU Bound (초기 단계) |
| **2** | 478 | 470 | 476 | CPU Bound |
| **4** | **715** | 678 | 674 | Random 우세 시작 |
| **8** | **982** | 836 | 818 | Cache Hit 시나리오 성장 정체 |
| **12** | **1114** | 929 | 916 | Random 우위 확대 |
| **14** | **1164** | 949 | 975 | Random 최종 우위 |

**관찰:** Cache Hit 100% 시나리오(Fixed, Distributed)가 Cache Miss 시나리오(Random)보다 처리량이 낮음.

### 3.2 서비스별 CPU 사용량 (Distributed 시나리오 기준)

병목 지점을 찾기 위해 측정한 각 마이크로서비스의 실제 CPU 사용량(mCore)입니다.

| Limit | Reservation (Target) | Rate | Memcached | 상태 분석 |
|-------|----------------------|------|-----------|-----------|
| **1** | 999m | 3513m | 368m | 정상 |
| **2** | 1984m | 4969m | 509m | 정상 |
| **4** | 3877m | 6728m | 692m | Rate 부하 증가 |
| **8** | 7122m | **7881m** | 823m | Rate CPU 증가율 둔화 |
| **12** | 9436m | **8133m** | 874m | Rate 정체, Reservation 유휴 발생 |
| **14** | 10413m | **8293m** | 905m | Rate ~8.3 Core에서 정체 |

**관찰:** Rate 서비스의 CPU 사용량이 약 8.3 Core 부근에서 더 이상 증가하지 않음.

---

## 4. 분석 (Analysis)

### 4.1 현상: 병목 이동 (Bottleneck Shifting)

Cache Hit 시나리오에서 성능이 더 낮은 이유를 추적한 결과:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Random 시나리오 (Cache Miss)                                       │
│                                                                     │
│  Request → Reservation → [DB 조회: ~수ms 대기]                      │
│                              ↓                                      │
│                           Rate 서비스                               │
│                              ↓                                      │
│                    (적당한 속도로 요청 도착)                         │
│                                                                     │
│  → DB I/O 대기가 자연스러운 "속도 조절" 역할                        │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  Distributed 시나리오 (Cache Hit 100%)                              │
│                                                                     │
│  Request → Reservation → [Memcached Hit: <1ms]                      │
│                              ↓                                      │
│                           Rate 서비스                               │
│                              ↓                                      │
│                    (요청 폭주! Rate 과부하)                         │
│                                                                     │
│  → Reservation이 빨라지자 Rate가 병목이 됨                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Rate 서비스 CPU 정체 원인 (가설)

Rate 서비스가 약 8.3 Core에서 더 이상 CPU를 사용하지 못하는 원인에 대해 여러 가설을 세웠습니다.

#### 가설 A: GC (Garbage Collection) 오버헤드

`GODEBUG=gctrace=1`로 측정한 결과:

| 시나리오 | 측정된 GC 빈도 |
|----------|----------------|
| Fixed | 60 ~ 70 회/초 |
| Distributed | 65 ~ 75 회/초 |
| Mixed | 55 ~ 70 회/초 |

**해석:** Rate 서비스에서 높은 빈도의 GC가 관찰됨. 그러나 Go의 GC는 대부분 concurrent하며, STW(Stop-The-World) 시간은 일반적으로 1ms 미만임. 초당 70회 × 1ms = 약 7%의 오버헤드로, 이것만으로 8.3코어 한계를 설명하기 어려움.

**검증 필요:**
```bash
# GC 빈도를 줄여서 테스트
GOGC=200 ./rate_service

# 또는 GC 완전 비활성화 (테스트용)
GOGC=off ./rate_service
```

#### 가설 B: 내부 동기화 병목 (Channel/Mutex)

Rate 서비스 내부에서 unbuffered channel이나 mutex 경합이 있을 수 있음.

**검증 필요:**
```bash
# wchan 분석
kubectl exec -n hotel-res <rate-pod> -- sh -c "cat /proc/1/task/*/wchan 2>/dev/null" | sort | uniq -c

# 스레드 상태 확인
kubectl exec -n hotel-res <rate-pod> -- top -H -b -n 1 | head -20
```

#### 가설 C: Full Scan 로직

코드 분석 결과, Rate 서비스는 요청마다 DB의 데이터를 Full Scan하는 로직이 있을 수 있음. 이로 인해 메모리 할당이 급증하고 GC 부하가 높아질 수 있음.

**검증 필요:**
- Rate 서비스 소스 코드 분석
- 쿼리 패턴 확인 (인덱스 사용 여부)

#### 가설 D: MongoDB Connection Pool 제한

Rate 서비스가 MongoDB와 통신할 때 connection pool 크기 제한이 있을 수 있음.

**검증 필요:**
```bash
kubectl exec -n hotel-res <mongodb-rate-pod> -- mongo --eval "db.serverStatus().connections"
```

### 4.3 Memcached 관련 관찰

Fixed(1-Key)와 Distributed(4-Keys) 시나리오에서 Memcached CPU 사용량 차이가 관찰됨:

| 시나리오 | Memcached CPU (8 Core 기준) |
|----------|----------------------------|
| Fixed (1-Key) | 649m |
| Distributed (4-Keys) | 823m (+27%) |

**주의:** 이 차이만으로 "락 경합"을 단정할 수 없음. 키가 분산되면 더 많은 작업을 처리하므로 CPU가 올라가는 것이 자연스러움. 락 경합을 확인하려면 다음이 필요:

```bash
# Memcached 상세 통계 확인
echo "stats" | nc memcached-reserve 11211 | grep -E "get_hits|get_misses|curr_connections|threads"

# 또는 slabs 통계
echo "stats slabs" | nc memcached-reserve 11211
```

### 4.4 Context Switching 분석

```bash
# pidstat -wt -p $(pgrep rate) 1 결과 요약
- cswch/s (자발적 교체): 수백 ~ 1,400회/초
- nvcswch/s (강제 교체): 30 ~ 70회/초
```

**해석:**
- `cswch/s`가 높음: I/O 대기, channel 대기, mutex 대기 등 여러 원인 가능
- `nvcswch/s`가 존재: CPU를 집약적으로 사용하는 작업이 있음

**주의:** Context switching만으로는 원인을 특정할 수 없음. GC, Network I/O, 내부 동기화 모두 cswch를 유발함.

---

## 5. 결론 및 해석

### 5.1 확인된 사실 (Observations)

1. **Cache Hit 시나리오가 Cache Miss보다 처리량이 낮음** - 반직관적 결과
2. **Rate 서비스 CPU가 약 8.3 Core에서 정체** - 확장성 제한 존재
3. **Rate 서비스에서 높은 GC 빈도 관찰** - 초당 60-75회

### 5.2 추정되는 원인 (Hypotheses)

```
┌─────────────────────────────────────────────────────────────────────┐
│  병목 이동 메커니즘 (추정)                                          │
│                                                                     │
│  1. Cache Hit으로 Reservation의 I/O 대기 시간 제거                 │
│                           ↓                                         │
│  2. Rate 서비스로 요청이 더 빠르게, 더 많이 도착                   │
│                           ↓                                         │
│  3. Rate 서비스 내부의 확장성 제한에 도달                           │
│     (GC, 동기화, Full Scan 등 - 정확한 원인 미확인)                │
│                           ↓                                         │
│  4. Rate 서비스가 응답 지연 → Reservation도 대기                   │
│                           ↓                                         │
│  5. 전체 처리량 저하                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3 핵심 교훈

> **"한 서비스를 최적화하면 병목이 다른 서비스로 이동할 수 있다."**

- 이는 "최적화가 나쁘다"는 의미가 아님
- Rate 서비스의 확장성 문제가 근본 원인
- Rate 서비스를 함께 최적화하면 Distributed 시나리오가 우위를 점할 것으로 예상

---

## 6. 추가 검증 필요 사항

본 분석의 결론을 확정하기 위해 다음 검증 실험이 필요합니다:

| 가설 | 검증 방법 | 예상 결과 |
|------|-----------|-----------|
| **GC가 주요 병목** | `GOGC=200` 또는 `GOGC=off`로 테스트 | 성능 향상 시 GC가 원인 |
| **내부 동기화 병목** | Rate 서비스 wchan 분석 | `futex_wait` 다수 시 동기화 문제 |
| **Rate 확장으로 해결 가능** | `kubectl scale deployment rate --replicas=3` | Distributed 성능 향상 시 Rate가 병목 |
| **Full Scan 로직** | Rate 소스 코드 분석 및 수정 | 쿼리 최적화 후 성능 변화 |
| **Memcached 락 경합** | Memcached stats 상세 분석 | lock/contention 메트릭 확인 |

---

## 7. 한계점 및 향후 연구

### 7.1 본 분석의 한계

1. **Rate 서비스 8.3코어 한계의 정확한 원인 미확인** - 여러 가설 중 검증 필요
2. **Memcached 락 경합 증거 불충분** - 상세 메트릭 분석 필요
3. **단일 환경(Minikube)에서의 테스트** - 실제 분산 환경에서 재현 필요

### 7.2 향후 연구 방향

1. Rate 서비스 프로파일링 (pprof)
2. 분산 트레이싱 (Jaeger) 활용한 병목 시각화
3. Rate 서비스 코드 최적화 후 재테스트
4. 실제 분산 클러스터 환경에서 재현

---

## 8. 시각화 (Visualization)

본 분석에 사용된 그래프:

* `final_rps_comparison.png`: 시나리오별 RPS 비교
* `final_cpu_bottleneck_analysis.png`: 서비스별 CPU 사용량 추이
* `memcached_cpu_comparison.png`: Memcached CPU 사용량 비교
* `rate_service_cpu_comparison.png`: 시나리오별 Rate 서비스 부하 비교

---

## 부록 A. 용어 정리

| 용어 | 설명 |
|------|------|
| **Bottleneck Shifting** | 한 지점의 병목을 해소하면 다른 지점으로 병목이 이동하는 현상 |
| **Cache Hit** | 요청한 데이터가 캐시에 존재하여 빠르게 반환되는 경우 |
| **Cache Miss** | 캐시에 데이터가 없어 원본 저장소(DB)에서 조회하는 경우 |
| **GC (Garbage Collection)** | 사용하지 않는 메모리를 자동으로 해제하는 런타임 기능 |
| **STW (Stop-The-World)** | GC 수행 중 모든 애플리케이션 스레드가 멈추는 시간 |
| **wchan** | 프로세스/스레드가 대기 중인 커널 함수 (wait channel) |

---

**Author:** Junseop Byeon (2022-18071)  
**Date:** 2026-01-06  
**Version:** 2.0 (Revised)