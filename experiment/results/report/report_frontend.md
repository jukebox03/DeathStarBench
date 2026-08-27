# gRPC 기반 DeathStarBench HotelReservation 시스템에서

## CPU 미활용 상태에서 발생하는 처리량 상한의 원인 분석

---

## 1. 실험 목적

본 보고서의 목적은 DeathStarBench HotelReservation 애플리케이션에서 **CPU 사용률이 100%에 도달하지 않음에도 불구하고 요청 처리량(RPS)이 특정 값 이상 증가하지 않는 현상**의 원인을 규명하는 것이다.

특히 다음 질문에 답하는 것을 목표로 한다.

* CPU가 여전히 여유 있음에도 RPS가 증가하지 않는 이유는 무엇인가?
* 병목은 User 서비스 자체인가, Frontend인가?
* HTTP/2(gRPC)의 flow control(window) 또는 단일 connection 구조가 원인인가?
* “직렬화(serialization) 병목”이 실제로 CPU 사용률이 낮은 상태에서도 발생할 수 있는가?

---

## 2. 실험 환경

### 2.1 시스템 구성

```
wrk ──HTTP──> Frontend ──gRPC (HTTP/2)──> User
```

* **Frontend**: HTTP 서버 + gRPC client
* **User service**: gRPC server
* **부하 생성기**:

  * end-to-end: `wrk`
  * user 단독: `ghz`

### 2.2 CPU 고정 실험 환경

* CPU pinning (`taskset`)
* CPU 주파수 고정: 2.5GHz
* 코어 배치 실험을 통해 병목 위치를 분석

---

## 3. 핵심 관측 1: User 서비스 자체는 병목이 아니다

### 3.1 ghz 기반 User 단독 처리량 측정

```bash
ghz --call user.User.CheckUser \
    -c 25 --connections 1 -z 30s
```

(4 instances 기준)

| User 코어    | ghz RPS     |
| ---------- | ----------- |
| 6~12 cores | 133k ~ 138k |
| 3 cores    | ~94k        |

**해석**

* User 서비스는 **6 cores 이상에서 130k+ RPS를 안정적으로 처리**
* end-to-end에서 관측되는 100~112k RPS 상한은 User 내부 처리 능력 때문이 아님

---

## 4. 핵심 관측 2: end-to-end 병목은 Frontend에 존재

### 4.1 wrk vs ghz 비교 실험

| User cores | Frontend cores | wrk RPS | ghz RPS | 병목 위치    |
| ---------- | -------------- | ------- | ------- | -------- |
| 12         | 6              | 100k    | 135k    | Frontend |
| 9          | 9              | 102k    | 133k    | Frontend |
| 6          | 12             | 112k    | 138k    | Frontend |
| 3          | 15             | 96k     | 94k     | **User** |

**핵심 규칙**

* `wrk RPS ≪ ghz RPS` → 병목은 **Frontend**
* `wrk RPS ≈ ghz RPS` → 병목은 **User**

→ User cores ≥ 6 인 경우, **end-to-end 병목은 항상 Frontend**

---

## 5. CPU를 더 줘도 RPS가 증가하지 않는 현상

### 5.1 관측된 현상

* Frontend CPU 사용률: **55~70%**
* 여전히 RPS는 **~100–112k에서 포화**
* CPU를 더 할당해도 선형적 증가 없음

이는 **CPU-bound 병목이 아님**을 강하게 시사한다.

---

## 6. 네트워크 큐(Recv-Q) 관측

### 6.1 관측 결과 요약

* **wrk → Frontend**: Recv-Q 증가
* **Frontend → User**: Recv-Q는 일정 수준 유지 (steady-state)
* **User → Frontend**: Recv-Q 거의 없음

**해석**

* Frontend가 HTTP 요청을 충분히 빠르게 처리하지 못함
* User는 완전히 밀리지 않지만 항상 약간 backlog를 가진 상태
* 응답 경로(User→Frontend)는 병목 아님

---

## 7. HTTP/2 Flow Control(Window) 가설 검증

### 7.1 가설

> HTTP/2 initial window size(64KB)가 throughput을 제한하는가?

### 7.2 실험

Frontend → User gRPC client에서 initial window size 변경:

| Window size    | RPS   | Avg latency |
| -------------- | ----- | ----------- |
| 64KB (default) | ~111k | ~10.4 ms    |
| 1MB            | ~111k | ~10.48 ms   |
| 16MB           | ~111k | ~10.64 ms   |

### 7.3 결론

* **Window 크기 증가로 RPS 변화 없음**
* latency만 소폭 증가 (in-flight 증가 효과)

→ **HTTP/2 flow control은 병목의 원인이 아님**
→ 오히려 병목을 “안정화”시키는 역할

---

## 8. 병목 이동 현상 확인

### 8.1 User 코어를 과도하게 줄인 경우

| User cores | Frontend cores | wrk RPS | ghz RPS |
| ---------- | -------------- | ------- | ------- |
| 3          | 15             | 96k     | 94k     |

* wrk ≈ ghz
* 이 경우에만 User가 병목

→ **병목은 상황에 따라 이동하지만**, 정상적인 자원 배치에서는 Frontend가 병목

---

## 9. 왜 “직렬화 병목”인데 CPU 100% 코어가 보이지 않는가?

### 9.1 오해의 원인

일반적인 오해:

> 직렬화 병목이면 한 코어가 항상 100%여야 한다

### 9.2 실제 동작

Frontend 병목 경로는 다음 특성을 가진다.

* 짧은 CPU burst + 대기 반복
* I/O(read/write), lock, scheduler 대기 포함
* Go 런타임 스케줄러로 인해 특정 goroutine/OS thread가 고정되지 않음

따라서:

* 특정 코어 100%가 **지속적으로 관측되지 않아도**
* 전체 처리량은 **단일 실행 경로(critical path)**에 의해 제한됨

---

## 10. 병목의 본질: CPU 부족이 아닌 구조적 직렬화

### 10.1 종합 결론

* User 서비스는 충분한 처리 능력을 가짐
* Frontend는:

  * HTTP 인입 처리
  * gRPC client transport
  * 단일 HTTP/2 connection의 read/demux/lock 경로
    중 **병렬화가 제한된 실행 경로**를 가짐

→ **CPU 총량이 아니라 “직렬화된 실행 경로”가 throughput을 결정**

---

## 11. 최종 결론

> 본 실험을 통해, CPU 사용률이 100%에 도달하지 않았음에도 처리량이 포화되는 원인은 CPU 자원 부족이 아니라 Frontend 내부의 직렬화된 실행 경로임을 확인하였다.
> HTTP/2 flow control은 병목의 원인이 아니며, 단일 connection 기반 gRPC client transport 및 HTTP 인입 처리 경로가 병렬 처리를 제한한다.
> 따라서 본 시스템의 처리량 상한은 구조적(serialization) 병목에 의해 결정된다.

---

## 12. 향후 작업

* Frontend → User **gRPC connection pool** 도입 실험
* Frontend pprof(CPU/mutex/block) 기반 정밀 병목 위치 확인
* HTTP 인입 경로와 gRPC outbound 경로 분리 실험

---

## 한 줄 요약

**CPU가 남는 것은 문제가 아니라 결과다.
문제는 CPU를 동시에 쓰지 못하게 만드는 구조적 직렬화 경로에 있다.**
