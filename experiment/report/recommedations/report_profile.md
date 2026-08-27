# Profile Service gRPC / Memcached Load Test Report

## 1. 목적 (Goal)

본 실험의 목적은 **HotelReservation 시스템에서 `GET /recommendations` 경로 중 Profile 서비스의 병목 원인**을 규명하는 것이다.
특히 다음 질문에 답하는 것을 목표로 했다.

* Profile 서비스의 처리 한계는 어디에서 발생하는가?
* gRPC 자체의 한계인가, downstream(memcached/MongoDB)의 한계인가?
* 이전 `frontend → user` 실험에서 관측된 문제와 동일한 성격인가?

## 2. 시스템 구성 요약

### 2.1 서비스 경로

```
Client
  └─ frontend (HTTP)
       └─ recommendation (gRPC)
            └─ profile (gRPC)
                 ├─ memcached-profile (TCP, 11211)
                 └─ mongodb-profile (TCP, 27017)
```

### 2.2 Profile 서비스 내부 동작

Profile 서비스의 `GetProfiles` RPC는 다음 순서로 동작한다.

1. 요청으로 받은 `hotelIds`에 대해
2. **memcached.GetMulti**

   * hit → 바로 반환
   * miss → MongoDB 조회
3. MongoDB miss 결과를 memcached에 `Set`
4. 결과 병합 후 응답

## 3. 실험 방법

### 3.1 직접 gRPC 호출 (frontend 제거)

frontend 영향을 배제하기 위해 `ghz`로 **Profile gRPC 직접 호출**을 수행했다.

#### 테스트 스크립트 (profile)

```bash
ghz --insecure \
  --proto services/profile/proto/profile.proto \
  --call profile.Profile.GetProfiles \
  -d '{"hotelIds":["1","2","3","4","5"],"locale":"en"}' \
  -c 800 \
  --connections 400 \
  --rps 80000 \
  -z 60s \
  <profile-pod-ip>:8081
```

또한 **병렬 ghz 인스턴스(최대 4~8개)** 를 동시에 실행하였다.

## 4. 관측 결과

### 4.1 Profile Pod Crash 현상

실험 도중 Profile pod가 반복적으로 CrashLoopBackOff 상태에 진입.

#### 대표 에러 로그

```text
memcache: unexpected line in get response: "ERROR Too many open connections"
panic: Tried to get hotelIds [[1 2 3 4 5]], but got memcached error
```

또는

```text
dial tcp 10.101.6.156:11211: connect: cannot assign requested address
panic: Tried to get hotelIds [[1 2 3 4 5]]
```

### 4.2 TCP Connection 상태 관측 (profile pod 내부)

#### memcached(11211) 관련 연결 상태

```bash
ss -ant '( dport = :11211 or sport = :11211 )'
```

##### ESTABLISHED

```
ESTAB ... 10.244.0.214:53738 → 10.101.6.156:11211
...
```

##### TIME_WAIT 폭증

```bash
ss -ant state time-wait '( dport = :11211 or sport = :11211 )' | wc -l
```

시간에 따른 변화:

```
03:26:05  10270
03:26:06  10616
03:26:08  10893
03:26:09  11251
03:26:10  11517
```

* **TIME_WAIT가 초당 수백 개씩 증가**
* ESTABLISHED ≈ 700
* TIME_WAIT ≈ 10,000+

👉 명확한 **short-lived TCP connection churn** 증거

## 5. 원인 분석

### 5.1 Profile ↔ Memcached 연결 특성

* Profile 서비스는 `gomemcache` 라이브러리 사용
* `memcache.Client` 객체는 재사용되지만,
* **TCP connection 자체는 요청마다 새로 생성/종료되는 형태로 동작**

➡️ 고QPS 상황에서 다음 현상 발생:

* 대량의 TCP connect/close
* TIME_WAIT 누적
* ephemeral port 고갈
* `cannot assign requested address`
* memcached server의 `max_connections` 초과

### 5.2 코드 레벨에서 문제를 악화시키는 요소

#### (1) Miss 처리 시 goroutine 폭증

```go
wg.Add(len(profileMap))
for hotelId := range profileMap {
  go func(hotelId string) {
    ...
    go s.MemcClient.Set(...)
    defer wg.Done()
  }()
}
```

* miss 수 × 요청 수 만큼 goroutine + TCP 연결 생성
* backpressure / 제한 없음

#### (2) memcached 에러 발생 시 panic

```go
if err != nil && err != memcache.ErrCacheMiss {
  log.Panic().Msgf(...)
}
```

* memcached가 한계에 도달하면 **즉시 pod crash**

## 6. 이전 User 실험과의 비교

| 항목        | frontend → user                    | profile → memcached  |
| --------- | ---------------------------------- | -------------------- |
| 프로토콜      | gRPC (HTTP/2)                      | TCP                  |
| 병목        | gRPC connection/stream concurrency | TCP connection churn |
| 해결        | frontend replica 증가                | 연결 재사용 필요            |
| TIME_WAIT | 거의 없음                              | 폭증                   |

### 핵심 차이

* **gRPC**: 하나의 TCP connection에서 다수의 stream → connection 한계보다 stream 한계가 먼저 도달
* **memcached(TCP)**: 요청당 connection → TCP/OS 한계가 먼저 도달

➡️ **둘 다 client-side concurrency 문제지만, 병목 지점이 다름**


## 7. 결론 (Key Findings)

1. Profile 서비스의 병목은 **gRPC가 아님**
2. 핵심 원인은 **Profile → Memcached 간 TCP connection churn**
3. memcached 서버 스케일을 늘려도

   * client ephemeral port / TIME_WAIT 문제는 해결되지 않음
4. frontend 실험에서 replica 증가로 해결된 이유는

   * gRPC stream 병목이었기 때문
5. 현재 상황은

   * **“가벼운 프로토콜(TCP)일수록 connection 관리가 더 중요”** 함을 보여줌

## 8. 향후 개선 방향

### 단기 (실험 지속용)

* ghz `--connections` 대폭 감소
* memcached `-c`, `-t` 증가
* Profile panic 제거 (graceful error)

### 중기

* memcached connection pooling / reuse
* miss 처리 goroutine 수 제한

### 근본

* memcached 앞에 connection-multiplexing proxy(mcrouter 등)
* 또는 Profile cache layer 자체 구조 개선

## 9. 요약 한 줄

> **Profile 서비스는 gRPC가 아니라 memcached TCP connection churn으로 먼저 한계에 도달하며, 이는 frontend-user 실험과는 다른 종류의 client-side 병목이다.**
