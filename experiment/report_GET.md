# Frontend–User gRPC 호출 경로의 성능 포화 원인 분석 보고서 (추가 분석)

## 13. GET `/hotels` 경로 분석

### 13.1 요청 처리 흐름

`GET /hotels` 요청은 frontend에서 다음과 같은 **순차적 gRPC 호출 체인**을 가진다.

```
HTTP GET /hotels
  ↓
search.Nearby            (gRPC)
  ↓
reservation.CheckAvailability (gRPC)
  ↓
profile.GetProfiles      (gRPC)
  ↓
HTTP Response
```

중요한 점은 다음과 같다.

* **fan-out 구조가 아님**

  * gRPC 호출들이 **병렬이 아니라 순차**
* 각 단계는 이전 단계가 완료되어야만 다음 단계로 진행
* frontend는 각 downstream 서비스에 대해 **프로세스당 grpc.ClientConn 1개**만 사용

즉, `/hotels`는 **critical path 길이가 3인 순차 gRPC 파이프라인**이다.

## 13.2 Fan-out / Fan-in 관점에서의 해석

### Fan-out / Fan-in 정의

* **Fan-out**: 하나의 요청이 여러 downstream 요청으로 분기됨
* **Fan-in**: downstream 응답들을 모아 하나의 응답으로 결합

`/hotels`의 경우:

* Fan-out ❌ (병렬 아님)
* Fan-in ❌ (단순 순차)

대신 다음과 같은 구조를 가진다.

> **Serial dependency chain**

이는 성능 관점에서 가장 불리한 구조 중 하나다.

## 13.3 성능 상한에 대한 이론적 분석

### 기본 원리

요청 1개가 완료되려면 다음 조건을 모두 만족해야 한다.

```
T_hotels = T_search + T_reservation + T_profile
```

steady-state에서 frontend 1 pod의 처리량은 다음에 의해 제한된다.

[
RPS_{hotels} \le \min(RPS_{search}, RPS_{reservation}, RPS_{profile})
]

그리고 각 RPS는 다시 다음에 의해 제한된다.

* grpc.ClientConn 당 동시 stream 수
* TCP send/recv queue
* HTTP/2 flow control
* kernel TCP backlog / retransmission

## 13.4 기존 실험 결과로부터의 RPS 추정

### 관측된 사실 요약

* `/user` (gRPC 1회):

  * frontend 1 pod 기준 **~25k RPS**에서 포화
* `/ping` (gRPC 없음):

  * **~220k RPS**까지 안정적
* ghz 실험:

  * connection 수가 적을 때 gRPC 서비스는 **~30k RPS** 근처에서 포화
  * connection 수를 늘리면 100k+ RPS까지 확장 가능

이는 다음 사실을 의미한다.

> **default frontend 구성에서는 각 downstream gRPC 호출이
> “connection 1개 수준의 처리량”으로 제한됨**

## 13.5 `/hotels` RPS 예상치 (frontend 1 pod, default 설정)

`/hotels`는 gRPC 호출을 **3회 순차적으로 수행**하므로,
`/user` 대비 포화가 **더 빠르게** 발생할 수밖에 없다.

경험적·이론적 추정을 종합하면:

| 조건                                   | 예상 RPS 범위          |
| ------------------------------------ | ------------------ |
| frontend = 1 pod                     |                    |
| default grpc.ClientConn              |                    |
| search / reservation / profile 모두 정상 | **약 6k ~ 15k RPS** |

### 해석

* 하한(≈6k)

  * reservation 또는 profile에서 connection/stream 병목이 먼저 발생
* 상한(≈15k)

  * 세 서비스 모두 가볍고 TCP 큐가 비교적 안정적인 경우

이 범위를 넘기면 다음 현상이 관찰될 가능성이 높다.

* p95/p99 latency 급증
* TCP retransmission 증가
* frontend CPU는 아직 여유 있음
* 그러나 RPS는 더 이상 증가하지 않음

## 13.6 왜 CPU가 아닌 TCP/gRPC가 먼저 포화되는가

이 현상은 `/hotels`에서 특히 두드러진다.

* CPU 사용률 < 70%
* 하지만:

  * TCP retransmission 폭증
  * connection reset 증가
  * latency 수 초 단위 증가

이는 다음 구조적 이유 때문이다.

1. frontend는 goroutine으로 요청을 무제한 생성
2. 하지만 outbound gRPC는 **소수의 HTTP/2 connection**만 사용
3. kernel TCP queue가 먼저 가득 참
4. backpressure가 없으므로 요청은 계속 쌓임
5. 결과적으로 CPU보다 **TCP stack이 먼저 붕괴**

## 13.7 핵심 결론 (GET `/hotels`)

> **GET `/hotels`의 성능 상한은
> 서비스 로직이 아니라
> frontend → downstream gRPC connection 구조에 의해 결정된다.**

* 순차 gRPC 호출은 처리량을 크게 제한
* replica 증가 없이 connection 구조를 바꾸지 않으면 확장성 없음
* `/user`보다 더 낮은 RPS에서 포화 발생
* 이는 설계상 필연적인 결과

## 13.8 실험적으로 검증 가능한 예측

다음 실험을 수행하면 위 분석을 명확히 입증할 수 있다.

1. frontend에서

   * `search`, `reservation`, `profile` 각각에 대해
   * **grpc.ClientConn pool (N>1)** 적용
2. `/hotels` RPS 재측정

**예상 결과**

* `/hotels` RPS는 거의 선형적으로 증가
* TCP retransmission 급감
* latency tail 대폭 개선

## 14. 요약 (업데이트)

| 경로        | 병목 원인                        |
| --------- | ---------------------------- |
| `/ping`   | 없음 (HTTP OK)                 |
| `/user`   | gRPC client-side concurrency |
| `/hotels` | **순차 gRPC + connection 한계**  |