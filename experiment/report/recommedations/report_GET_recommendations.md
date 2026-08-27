# GET `/recommendations` 성능 병목 분석 보고서

*(Frontend gRPC Client Bottleneck & GetRecommendations / GetProfiles 분석)*

## 1. 분석 목적

본 보고서는 HotelReservation 시스템의 **GET `/recommendations` API**에 대해 다음을 규명하는 것을 목표로 한다.

1. GET `/recommendations`의 **처리량(RPS) 상한은 어디에서 결정되는가**
2. **Frontend의 gRPC client 한계**가 전체 API 처리량을 제한하는지
3. Recommendation 서비스와 Profile 서비스 중 **어디가 병목인가**
4. wrk 기반 HTTP 부하 실험에서 관측된 **~20k RPS / 수십 초 latency**를 논리적으로 설명할 수 있는지

## 2. GET `/recommendations` 요청 처리 구조

### 2.1 요청 경로 요약

GET `/recommendations`는 다음과 같은 **2-hop gRPC 체인**으로 처리된다.

```
HTTP Client
  ↓
Frontend
  ↓  (gRPC)
Recommendation.GetRecommendations
  ↓  (gRPC)
Profile.GetProfiles
  ↓
Frontend (결과 병합 + JSON 응답)
```

### 2.2 구조적 특징

* 요청 **1건당 gRPC 호출 2회**가 반드시 발생
* 두 gRPC 호출은 **Frontend에서 생성**
* Frontend는 gRPC 결과를 병합하여 HTTP JSON 응답을 생성
* Recommendation / Profile 서비스는 **read-only 성격의 경량 연산**

이 구조는 **Frontend의 outbound gRPC 처리 능력**이 전체 API 처리량을 제한할 가능성을 내포한다.

## 3. Recommendation 서비스(GetRecommendations) 분석

### 3.1 내부 동작 요약

Recommendation 서비스는 다음과 같이 동작한다.

* MongoDB에서 로드한 호텔 메타데이터를 메모리에 유지
* 요청된 `(lat, lon, require)` 기준으로:

  * 거리 계산
  * 정렬(`dis`, `rate`, `price`)
* 추천된 **hotel ID 리스트**를 반환

### 3.2 ghz 직접 호출 실험 결과 요약

Recommendation을 ghz로 **직접 호출**했을 때:

* 단일 ghz instance 기준:

  * concurrency 증가에도 불구하고
  * **~3–4만 RPS 근처에서 처리량 포화**
* concurrency를 과도하게 증가시키면:

  * RPS는 거의 증가하지 않고
  * latency만 증가

이는 Recommendation 서버의 계산 비용이 아니라, **gRPC 요청 생성 및 관리 비용**이 상한을 형성하고 있음을 시사한다.

## 4. Profile 서비스(GetProfiles) 분석

### 4.1 Profile 내부 구조 요약

Profile의 `GetProfiles`는 다음 경로를 따른다. 

1. `memcached.GetMulti(hotelIds)`
2. cache hit → 바로 반환
3. cache miss → MongoDB 조회
4. miss 결과를 memcached에 Set
5. 결과 병합 후 반환

### 4.2 ghz 기반 단독 부하 실험 관측

Frontend를 제거하고 ghz로 Profile RPC를 직접 호출했을 때 다음 문제가 반복적으로 발생했다. 

* `cannot assign requested address`
* `Too many open connections`
* Profile pod CrashLoopBackOff

### 4.3 네트워크 상태 분석

Profile pod 내부에서 TCP 상태를 관측한 결과: 

* ESTABLISHED 연결 수는 제한적
* TIME_WAIT 상태가 **수천~수만 단위로 누적**
* 초당 수백 개의 short-lived TCP 연결 생성/종료

### 4.4 Profile 병목에 대한 결론

Profile의 병목은 gRPC가 아니라:

* **Profile → Memcached 간 TCP connection churn**
* miss 처리 시 goroutine 폭증
* 에러 발생 시 panic 처리로 인한 pod crash

임이 확인되었다. 

즉, **Profile은 안정성 문제는 있으나**,
GET `/recommendations`의 **처리량 상한을 결정하는 1차 병목은 아니다.**

## 5. Frontend gRPC Client 병목 분석

### 5.1 Frontend의 역할

Frontend는 GET `/recommendations` 요청마다:

* gRPC `GetRecommendations` 호출
* gRPC `GetProfiles` 호출
* 결과 병합 및 JSON 직렬화

즉, **모든 downstream gRPC 호출의 생성 지점**이다.

### 5.2 gRPC Client의 구조적 한계

Frontend는 일반적으로:

* 서비스당 grpc.ClientConn 1개
* 요청당 goroutine 생성
* HTTP/2 stream 기반 multiplexing

이 구조에서는 고부하 시 다음 문제가 발생한다.

* gRPC stream 관리 및 flow control 경쟁
* goroutine scheduling 비용 증가
* CPU는 남아 있어도 **새 RPC를 충분히 빠르게 생성하지 못함**

이는 ghz 실험에서 관측된 **client-side request generation bottleneck**과 동일한 메커니즘이다.

## 6. wrk 기반 HTTP 실험 분석 (GET `/recommendations`)

### 6.1 실험 설정

wrk2 + Lua 스크립트로 캐시 효과를 제거한 상태에서 다음과 같이 실행했다.

```bash
wrk -t 8 -c 1000 -d 60s -L \
    -s recommend_only.lua \
    http://localhost:31643 -R 50000
```

* Open-loop 방식으로 **초당 50,000 요청 강제 주입**
* 서버 처리 능력과 무관하게 요청을 계속 생성

### 6.2 관측 결과 요약

* 실제 처리량: **19,679 RPS**
* 평균 latency: **20.7초**
* p99 latency: **35.4초**

즉:

* 목표 RPS의 약 39%만 처리
* latency는 **ms가 아니라 초 단위로 폭발**

### 6.3 왜 약 20k RPS에서 포화되는가? (핵심 논리)

이 결과는 **Frontend gRPC 생성 한계**로 논리적으로 설명할 수 있다.

1. ghz 실험에서 단일 gRPC 호출의 처리 상한이
   **약 38k RPC/s 수준**에서 포화됨을 관측
2. GET `/recommendations`는 요청 1건당
   **gRPC 호출 2회**를 필요로 함
3. 따라서 이상적인 상한은:

[
\text{Max HTTP RPS} \approx \frac{38,000}{2} \approx 19,000
]

4. 실제 wrk 관측치:

   * **19,679 RPS**

즉, **이론적 계산과 실측 결과가 거의 일치**한다.

### 6.4 왜 latency가 수십 초까지 증가하는가?

wrk는 open-loop 방식이므로:

* 입력: 50,000 RPS
* 처리 가능: ~19,700 RPS
* 초당 약 30,000 요청이 **Frontend 내부에서 대기열에 누적**

Frontend에는 명시적인 backpressure나 in-flight 제한이 없기 때문에,
요청은 버려지지 않고 **무한히 큐잉**되며,
그 결과 latency가 수십 초까지 증가한다.

## 7. 종합 결론

1. **GET `/recommendations`의 처리량 상한은 Recommendation이나 Profile 서버가 아니라 Frontend에서 결정된다.**
2. Frontend는 요청 1건당 gRPC 호출 2회를 생성해야 하며,
   이로 인해 **Frontend gRPC client의 요청 생성 능력**이 병목이 된다.
3. ghz 기반 단일 gRPC 실험에서 관측된 처리 상한을 기준으로 하면,
   wrk 기반 HTTP 실험에서 관측된 **~20k RPS 상한은 논리적으로 예측 가능**하다.
4. wrk open-loop 부하에서 발생한 **수십 초 단위 latency 폭발**은
   서버 계산 지연이 아니라 **Frontend 내부 무한 큐잉**의 결과다.
5. Profile 서비스는 별도의 안정성 문제(memcached 연결 churn)를 가지지만,
   GET `/recommendations`의 **1차 처리량 병목은 아니다.**

## 8. 요약 문장 (한 줄)

> GET `/recommendations`의 처리량은 downstream 서비스의 처리 능력과 무관하게, 요청 1건당 두 번의 gRPC 호출을 생성해야 하는 Frontend gRPC client의 요청 생성 한계에 의해 약 20k RPS 수준에서 포화되며, 오픈루프 부하에서는 backpressure 부재로 인해 지연이 수십 초까지 증가한다.
