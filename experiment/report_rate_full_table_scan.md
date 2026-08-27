# Rate 서비스 Full Table Scan 버그 수정 실험 결과 보고서

## 1. 실험 개요

### 1.1 목적
Rate 서비스의 Full Table Scan 버그(`bson.D{}` → `bson.D{{"hotelId", id}}`)를 수정하고, 
수정 전/후 성능을 비교하여 이 버그가 시스템 병목의 원인인지 검증한다.

### 1.2 실험 조건

| 항목 | 값 |
|------|-----|
| Target RPS | 3000 |
| Duration | 60초 |
| Threads | 4 |
| Connections | 100 |
| Core 제한 | 없음 (무제한) |

### 1.3 테스트 시나리오

| 시나리오 | 설명 |
|----------|------|
| **Random** | 랜덤 Hotel ID, Cache Miss 발생 |
| **Fixed** | 단일 Hotel ID, 100% Cache Hit |
| **Distributed** | 4개 Hotel ID 분산, 100% Cache Hit |

---

## 2. 실험 결과

### 2.1 처리량 (RPS) 비교

| 시나리오 | Baseline (버그) | Fixed (수정) | 변화 | 변화율 |
|----------|-----------------|--------------|------|--------|
| **Random** | 1,179.56 | 1,168.92 | -10.64 | **-0.9%** |
| **Fixed** | 956.39 | 976.20 | +19.81 | **+2.1%** |
| **Distributed** | 962.22 | 977.56 | +15.34 | **+1.6%** |

### 2.2 Latency 비교

#### Average Latency

| 시나리오 | Baseline | Fixed | 변화 |
|----------|----------|-------|------|
| Random | 21.35s | 21.39s | +0.04s |
| Fixed | 23.93s | 23.59s | -0.34s |
| Distributed | 23.81s | 23.34s | -0.47s |

#### P50 Latency

| 시나리오 | Baseline | Fixed | 변화 |
|----------|----------|-------|------|
| Random | 21.32s | 21.27s | -0.05s |
| Fixed | 24.05s | 23.76s | -0.29s |
| Distributed | 23.81s | 23.28s | -0.53s |

#### P99 Latency

| 시나리오 | Baseline | Fixed | 변화 |
|----------|----------|-------|------|
| Random | 36.41s | 36.67s | +0.26s |
| Fixed | 40.53s | 40.17s | -0.36s |
| Distributed | 40.44s | 39.91s | -0.53s |

---

## 3. 핵심 발견

### 3.1 버그 수정 효과: 미미함

```
┌─────────────────────────────────────────────────────────────────────┐
│  결과 요약                                                          │
│                                                                     │
│  • RPS 변화: -0.9% ~ +2.1% (통계적 오차 범위)                       │
│  • Latency 변화: -0.5s ~ +0.3s (미미함)                             │
│  • 시나리오 순위 변화: 없음 (Random > Distributed ≈ Fixed)          │
│                                                                     │
│  ⚠️  Rate Full Table Scan 버그는 주요 병목이 아니었음              │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 시나리오별 성능 순위 (변함없음)

```
Before (Baseline):  Random (1180) > Distributed (962) ≈ Fixed (956)
After (Fixed):      Random (1169) > Distributed (978) ≈ Fixed (976)

→ Cache Hit 시나리오가 여전히 Cache Miss보다 느림!
→ "최적화의 역설" 현상이 Rate 버그와 무관하게 존재
```

### 3.3 왜 버그 수정 효과가 없었나?

#### 가설 1: 데이터 크기가 너무 작음

```
MongoDB rate-db.inventory: 108개 row

단일 쿼리:
  • Full Scan: 108개 × ~200 bytes ≈ 22KB
  • 단일 조회: 1개 × ~200 bytes ≈ 200 bytes

→ 100배 차이지만, 절대적 크기가 작아 영향 미미
→ 실제 프로덕션 (수만~수십만 row)에서는 영향 클 수 있음
```

#### 가설 2: 다른 병목이 더 큼

```
현재 병목 후보:

1. Reservation 서비스
   - unbuffered channel (이전에 분석함)
   - CPU 17코어 사용 (가장 높음)

2. Frontend 서비스
   - 모든 요청의 진입점
   - gRPC 클라이언트 병목 가능

3. Network I/O
   - 서비스 간 gRPC 통신 대기
```

#### 가설 3: GC가 여전히 발생

```
108개 row를 메모리에 로드하는 것은 여전히 발생:

curr.All(context.TODO(), &tmpRatePlans)  // 전체 결과 메모리 로드

→ 쿼리는 1개로 줄었지만, 결과를 담는 구조는 동일
→ 단, 108개 row면 GC 영향도 미미할 것
```

---

## 4. 추가 분석: Random이 더 빠른 이유

### 4.1 현상

```
Random (Cache Miss):  1,170 RPS, P50 21s
Fixed/Distributed:    970 RPS,  P50 24s

→ Cache Hit가 오히려 20% 느림!
```

### 4.2 원인 분석 (기존 분석 확인)

```
Cache Miss 시나리오 (Random):
┌─────────────────────────────────────────────────────────────┐
│  Request → Reservation → [DB 조회: 수ms 대기]              │
│                              ↓                              │
│                           Rate 서비스                       │
│                                                             │
│  DB I/O 대기 = 자연스러운 "속도 조절" (Backpressure)       │
└─────────────────────────────────────────────────────────────┘

Cache Hit 시나리오 (Fixed/Distributed):
┌─────────────────────────────────────────────────────────────┐
│  Request → Reservation → [Memcached: <1ms]                 │
│                              ↓                              │
│                     Rate 서비스 (과부하!)                   │
│                                                             │
│  Reservation이 빨라져서 Rate가 병목이 됨                   │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 결론

**Rate Full Table Scan 버그는 "병목 이동" 현상의 원인이 아님.**

진짜 원인은:
1. **Reservation 서비스의 동기화 병목** (unbuffered channel)
2. **Rate 서비스의 다른 병목** (Mutex 경합, GC 등)
3. **시스템 전체의 구조적 문제** (서비스 간 의존성)

---

## 5. 다음 단계

### 5.1 검증이 필요한 가설

| 가설 | 검증 방법 | 우선순위 |
|------|-----------|----------|
| **Reservation unbuffered channel** | buffered channel 수정 후 테스트 | 🔴 높음 |
| **Rate Mutex 경합** | Rate wchan 분석 | 🟡 중간 |
| **Frontend 병목** | Frontend CPU/스레드 분석 | 🟡 중간 |
| **데이터 크기 영향** | inventory 데이터 10,000개로 증가 후 테스트 | 🟢 낮음 |

### 5.2 권장 실험

```bash
# 1. Reservation buffered channel 테스트 (이전에 시도했던 것)
#    → 코드 수정 재확인 필요

# 2. Rate 서비스 상세 분석
RATE_POD=$(kubectl get pod -n hotel-res | grep -E "^rate-" | awk '{print $1}')
kubectl exec -n hotel-res $RATE_POD -- top -H -b -n 1 | head -20
kubectl exec -n hotel-res $RATE_POD -- sh -c "cat /proc/1/task/*/wchan 2>/dev/null" | sort | uniq -c

# 3. 서비스별 CPU 확인 (부하 중)
kubectl top pods -n hotel-res --no-headers | sort -k2 -h -r
```

---

## 6. 결론

### 6.1 실험 결과 요약

| 항목 | 결과 |
|------|------|
| **버그 수정 효과** | 거의 없음 (-0.9% ~ +2.1%) |
| **시나리오 순위** | 변화 없음 (Random > Cache Hit) |
| **주요 병목** | Rate Full Scan이 아닌 다른 곳 |

### 6.2 핵심 교훈

```
"버그 수정 = 성능 개선" 이 항상 성립하지 않음

이유:
1. 버그의 영향이 미미할 수 있음 (데이터 크기, 호출 빈도)
2. 더 큰 병목이 다른 곳에 있을 수 있음
3. 시스템은 "가장 느린 구간"에 의해 제한됨

→ 반드시 측정으로 검증해야 함!
```

### 6.3 "최적화의 역설" 재해석

```
기존 가설:
  "Rate Full Scan이 병목 → Cache Hit 시 Rate 과부하"

실험 결과:
  "Rate Full Scan 수정해도 변화 없음"

새로운 가설:
  "Cache Hit 시 Reservation이 너무 빨라져서 다른 곳에서 병목"
  
  후보:
  - Reservation의 unbuffered channel-> 아님(실험을 통해 확인)
  - Rate의 Mutex 경합
  - Frontend의 gRPC 클라이언트-> 아님(GET /recommendations 에서 10500 RPS에서 saturate 확인)
```

---

## 부록: Raw Data

### A. Baseline (버그 있는 상태)

| 시나리오 | RPS | Avg Lat | P50 | P99 |
|----------|-----|---------|-----|-----|
| Random | 1,179.56 | 21.35s | 21.32s | 36.41s |
| Fixed | 956.39 | 23.93s | 24.05s | 40.53s |
| Distributed | 962.22 | 23.81s | 23.81s | 40.44s |

### B. Fixed (버그 수정 후)

| 시나리오 | RPS | Avg Lat | P50 | P99 |
|----------|-----|---------|-----|-----|
| Random | 1,168.92 | 21.39s | 21.27s | 36.67s |
| Fixed | 976.20 | 23.59s | 23.76s | 40.17s |
| Distributed | 977.56 | 23.34s | 23.28s | 39.91s |

---

**실험 일자:** 2026-01-06  
**실험자:** Junseop Byeon