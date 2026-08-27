# Frontend–User gRPC 호출 경로의 성능 포화 원인 분석 보고서

## 1. 연구 목적

본 연구의 목적은 **DeathStarBench hotel-reservation 시스템에서 `POST /user` 요청의 성능 병목 원인을 규명**하는 것이다.

특히 다음 질문에 답하는 것을 목표로 한다.

* 왜 `/user` 요청은 `/ping` 대비 매우 낮은 RPS에서 포화되는가?
* 병목은 **User 서비스 자체**인가, **Frontend의 gRPC 호출 경로**인가?
* Replica 수, gRPC connection 수, client-side concurrency는 성능에 어떤 영향을 미치는가?
* CPU, DB, cache가 아닌 경우 병목은 어디에 존재하는가?
* **왜 CPU가 아직 남아 있음에도 TCP 계층이 먼저 붕괴되는가?**

---

## 2. 시스템 구성 요약

### 2.1 요청 경로

```
wrk (HTTP/1.1)
  ↓
frontend (HTTP server)
  ↓
gRPC client (HTTP/2)
  ↓
user service (CheckUser RPC)
```

### 2.2 주요 특징

| 구성 요소 | 특징 |
|-----------|------|
| Frontend → User | gRPC (HTTP/2, unary RPC) |
| Frontend gRPC 연결 | 프로세스당 1개의 grpc.ClientConn |
| Load Balancing | client-side `round_robin` |
| Istio sidecar | 미사용 |
| User 서비스 | Stateless (in-memory map) |

### 2.3 User 서비스 구현

```go
// 서버 시작 시 한 번만 DB 접근
func (s *Server) Run() error {
    s.users = loadUsers(s.MongoClient)  // MongoDB → in-memory map
}

// 매 요청: 순수 메모리 연산만 수행
func (s *Server) CheckUser(ctx context.Context, req *pb.Request) (*pb.Result, error) {
    sum := sha256.Sum256([]byte(req.Password))  // CPU 연산
    pass := fmt.Sprintf("%x", sum)
    if true_pass, found := s.users[req.Username]; found {
        res.Correct = pass == true_pass
    }
    return res, nil
}
```

---

## 3. 실험 환경

| 항목 | 값 |
|------|-----|
| Kubernetes | kubeadm 기반 클러스터 |
| Node | 동일 node (client / server colocated) |
| Network | Pod-to-Pod (CNI) |
| Sidecar | 없음 |
| Load Generator | wrk2 (HTTP), ghz (gRPC) |
| OS | Linux |
| 실험 시간 | 각 60초 |

---

## 4. Baseline 실험: Frontend HTTP 처리 능력

### 4.1 실험: 의미 없는 POST (/ping)

**목적:** gRPC 호출을 제외한 Frontend HTTP 처리 능력 측정

**설정:**
```bash
wrk -t 16 -c 2000 -d 60s -R 250000 http://frontend/ping
```

**결과:**

| 항목 | 값 |
|------|-----|
| 처리량 | **~220,000 RPS** |
| Frontend CPU | ~67% |
| Latency | 안정적 |

**결론:**
- Frontend의 **HTTP 처리 로직은 병목 아님**
- `/user` 성능 저하 원인은 **gRPC 호출 경로 이후**에 존재

---

## 5. User 서비스 단독 성능 분석 (ghz)

### 5.1 gRPC Connection 수 실험 (Phase 1)

**목적:** gRPC connection 수가 성능에 미치는 영향 측정

**설정:**
- ghz 인스턴스: 4개
- Concurrency: 400 per instance
- Duration: 60초
- Target: User Pod 직접 호출

**결과:**

| Connections | Total RPS | Avg Latency | P99 Latency | TCP Conns |
|-------------|-----------|-------------|-------------|-----------|
| 1 | 74,737 | 18.05 ms | 20.08 ms | 4 |
| **10** | **95,328** | **7.99 ms** | 17.01 ms | 40 |
| 50 | 89,924 | 6.74 ms | 17.82 ms | 200 |
| 100 | 85,850 | 6.36 ms | 18.32 ms | 400 |
| 200 | 80,795 | 6.64 ms | 22.50 ms | 800 |
| 400 | 76,218 | 7.54 ms | 29.30 ms | 1600 |

**분석:**
- **connections=10에서 최적** (95,328 RPS)
- connections=1: 연결 부족 → 병목 (latency 18ms)
- connections>10: 연결 관리 오버헤드로 성능 감소
- TCP 연결 수는 `ghz_instances × connections`로 정확히 일치

### 5.2 sha256 연산 제거 실험

**목적:** CPU 연산이 병목인지 확인

**설정:**
```go
// Before
sum := sha256.Sum256([]byte(req.Password))
pass := fmt.Sprintf("%x", sum)

// After (제거)
pass := req.Password
```

**결과:**

| 버전 | RPS | 변화 |
|------|-----|------|
| sha256 있음 | 40,800 | - |
| sha256 제거 | 41,032 | **+0.5%** |

**결론:** sha256 연산은 **병목 아님**

### 5.3 User Replica 증가 실험

**설정:** User replica 1 → 2

**결과:** RPS **유의미한 증가 없음**

**원인:** 단일 Pod IP 직접 호출 시 다른 replica에 분산 안 됨

---

## 6. ghz 인스턴스 수 실험 (Phase 2)

### 6.1 Client-side Scaling 실험

**목적:** 클라이언트 요청 생성 능력의 한계 측정

**설정:**
- connections: 200 per instance
- concurrency: 400 per instance
- Duration: 60초

**결과:**

| ghz Instances | Total RPS | Per-Instance RPS | Scale Efficiency |
|---------------|-----------|------------------|------------------|
| 1 | 40,800 | 40,800 | 100% |
| 2 | 60,000 | 30,000 | 73.5% |
| 4 | 83,300 | 20,825 | 51.1% |
| 8 | 100,422 | 12,553 | 30.8% |
| 16 | 107,679 | 6,730 | 16.5% |

**Scale Efficiency 계산:**
$$E(N) = \frac{T_N}{N \times T_1} \times 100\%$$

**분석:**
- 인스턴스 증가에 따라 **sublinear scaling**
- 16 인스턴스에서 효율 16.5%로 급감
- ~100k RPS 근처에서 **서버 한계 도달**

---

## 7. Frontend → User 경로 실험 (wrk)

### 7.1 `/user` 요청 단일 Frontend

**결과:**

| 항목 | 값 |
|------|-----|
| 포화 RPS | ~25,000 |
| CPU 사용량 | ~50% |
| Latency | 급격히 증가 (queueing) |

### 7.2 Cache Hit Ratio 실험

| Cache Hit | RPS | CPU |
|-----------|-----|-----|
| 0% (Random) | ~25,200 | ~50% |
| 100% (Fixed) | ~25,600 | ~50% |

**결론:** DB 접근 latency와 **무관**

### 7.3 Frontend vs 직접 호출 비교

| 테스트 경로 | RPS | 병목 |
|-------------|-----|------|
| wrk → Frontend → User | 25,200 | Frontend gRPC client |
| ghz → User (직접) | 40,800+ | 클라이언트/서버 한계 |

**차이:** 38% 성능 손실 → **Frontend gRPC 호출 경로가 병목**

---

## 8. Frontend Replica Scaling 실험

### 8.1 실험 결과

| Frontend Replicas | Achieved RPS | Latency 특성 |
|-------------------|--------------|--------------|
| 1 | ~25k | Queueing 심함 |
| 4 | ~48k | p99 ≈ 5s |
| 8 | ~49k | p99 ≈ 3.7s |
| 8 (고부하 wrk) | ~119k | p99 ≈ 1.4s |

### 8.2 분석

- Replica 증가 → 처리량 증가
- 그러나 **선형 증가 아님**
- 일정 replica 이후 **효율 급락**

**결론:** Replica 증가는 gRPC connection 수를 늘리는 **간접 수단**일 뿐

---

## 9. TCP Stack 분석 (Phase 3)

### 9.1 TCP 메트릭 변화 (60초 부하 테스트)

**설정:** 8 ghz instances, ~100k RPS

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| **Segments retransmitted** | 2,381,654 | 2,486,697 | **+105,043** |
| **TCP Loss Probes** | 2,332,705 | 2,437,746 | **+105,041** |
| **Delayed ACKs sent** | 18,172,133 | 19,026,962 | **+854,829** |
| Resets sent | 1,173,459 | 1,173,956 | +497 |
| Connection resets received | 1,049,877 | 1,050,350 | +473 |
| Active connection openings | 1,974,793 | 1,978,528 | +3,735 |

### 9.2 주요 지표 해석

| 지표 | 의미 |
|------|------|
| **Retransmissions +105k** | ~1,750/sec, 패킷 손실 또는 처리 지연 |
| **Loss Probes +105k** | TCP가 연결 생존 여부 반복 확인 |
| **Delayed ACKs +855k** | Receiver측 처리 지연으로 ACK 생성 밀림 |

### 9.3 TCP 병목이 CPU와 무관한 이유

TCP 병목은 다음 요소에서 발생한다:

- **softirq 처리 지연**
- **socket receive buffer overflow**
- **TCP backlog saturation**
- **per-flow 직렬 처리 구조**

이는 **CPU 전체 사용률이 100%에 도달하지 않아도 먼저 포화**될 수 있다.

> CPU는 계산 자원이고,  
> TCP는 **큐 + 직렬 처리 경로**이다.

---

## 10. 핵심 병목 요인 정리

### 10.1 배제된 병목

| 요소 | 증거 | 결론 |
|------|------|------|
| User CPU | sha256 제거해도 변화 없음 | ❌ 병목 아님 |
| DB | Cache hit 100%에서도 동일 | ❌ 병목 아님 |
| Frontend HTTP | /ping 220k RPS 가능 | ❌ 병목 아님 |
| 단일 연산 | 순수 메모리 연산만 수행 | ❌ 병목 아님 |

### 10.2 실제 병목 (다층적)

| 계층 | 병목 요인 | 증거 |
|------|-----------|------|
| **Application** | Frontend gRPC client concurrency | 직접 호출 시 38% 성능 향상 |
| **Protocol** | gRPC connection/stream 한계 | connections=10에서 최적 |
| **Kernel** | Linux TCP stack 처리 경로 포화 | Retransmission 105k/60s |

---

## 11. Replica 증가가 만능이 아닌 이유

### 11.1 Replica 증가의 효과

```
Replica ↑ → gRPC connection ↑ → RPS ↑ (초기)
```

### 11.2 한계

```
Replica ↑↑ → TCP backlog 경쟁 ↑
          → conntrack 부담 ↑
          → softirq 부담 ↑
          → 효율 ↓↓
```

### 11.3 최적 Replica 수

**Scale Efficiency 공식:**
$$E(N) = \frac{T_N}{N \times T_1}$$

실험 결과 기준:
- Frontend: **4~8 replicas**에서 최적
- 그 이후 효율 급감

---

## 12. 실험 데이터 요약

### 12.1 Phase 1: Connection 수 vs 성능

```
최적점: connections=10 (95,328 RPS)
- connections 부족: 연결 병목
- connections 과다: 관리 오버헤드
```

### 12.2 Phase 2: Client Scaling

```
Sublinear scaling 확인:
- 1 instance: 100% efficiency
- 16 instances: 16.5% efficiency
- ~100k RPS에서 서버 한계
```

### 12.3 Phase 3: TCP Stack Stress

```
60초 동안:
- Retransmissions: +105,043 (~1,750/sec)
- Loss Probes: +105,041 (~1,750/sec)
- Delayed ACKs: +854,829 (~14,247/sec)
→ TCP 레이어 스트레스 명확
```

---

## 13. 최종 결론

### 핵심 메시지

> **`/user` 요청의 성능 포화는  
> User 서비스의 처리 능력 부족이 아니라,  
> Frontend → User 경로의 gRPC client concurrency와  
> 이를 수용하지 못하는 TCP stack의 구조적 한계에서 발생한다.**

### 성능 비교 요약

| 테스트 | RPS | 병목 |
|--------|-----|------|
| Frontend HTTP only (/ping) | 220,000 | 없음 |
| Frontend → User (wrk) | 25,000 | gRPC client |
| User 직접 (ghz 1개) | 40,800 | 클라이언트 |
| User 직접 (ghz 4개, optimal conn) | 95,328 | - |
| User 직접 (ghz 16개) | 107,679 | TCP stack |

### 한 줄 요약

> **이 시스템의 성능 한계는 애플리케이션이 아니라  
> "gRPC over TCP가 커널에서 처리되는 방식"에 있다.**

---

## 14. 향후 실험 및 개선 방향

### 14.1 Application Level

- [ ] Frontend에서 **multiple grpc.ClientConn pool**
- [ ] gRPC per-conn sharding
- [ ] Client-side backpressure 구현

### 14.2 Protocol Level

- [ ] gRPC `MaxConcurrentStreams` 튜닝
- [ ] HTTP/2 stream usage 계측
- [ ] Connection pooling 전략 최적화

### 14.3 Kernel Level

- [ ] TCP backlog 튜닝 (`net.core.somaxconn`)
- [ ] Socket buffer 튜닝 (`rmem`, `wmem`)
- [ ] softirq CPU affinity 실험

---

## 부록 A: 실험 환경 상세

### A.1 클러스터 구성

```
Frontend: 16 replicas
User: 8 replicas
```

### A.2 Load Generator

**ghz (gRPC):**
```bash
ghz --insecure \
  --proto user.proto \
  --call user.User.CheckUser \
  -d '{"username": "Cornell_1", "password": "1111111111"}' \
  -c 400 --connections <N> -z 60s \
  <target>:8086
```

**wrk2 (HTTP):**
```bash
wrk -t 16 -c <connections> -d 60s -R <rps> \
  -s user.lua http://frontend:5000/user
```

---

## 부록 B: 생성된 그래프 목록

| 파일명 | 내용 |
|--------|------|
| `phase1_connections_vs_rps.png` | Connection 수 vs RPS/Latency |
| `phase2_scaling_efficiency.png` | Client scaling (Actual vs Ideal) |
| `phase2_efficiency_bar.png` | Scaling efficiency 바 차트 |
| `phase3_tcp_metrics.png` | TCP 메트릭 변화량 |
| `phase3_tcp_errors.png` | TCP 에러 메트릭 집중 분석 |
| `combined_summary.png` | 4개 그래프 종합 |