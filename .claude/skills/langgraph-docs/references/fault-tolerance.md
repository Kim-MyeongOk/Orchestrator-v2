# Fault Tolerance

원문 : https://docs.langchain.com/oss/python/langgraph/fault-tolerance

노드 실패(느린 외부 API, 일시적 네트워크 에러, 미처리 예외) 대응을 위한 3가지 조합 가능 메커니즘.

- **Retries** : 예외 타입·백오프 기준으로 실패한 시도를 자동 재실행
- **Timeouts** : 단일 시도의 실행 시간 제한
- **Error handling** : 모든 재시도 소진 후 복구 함수 실행

**고정 순서로 조합** : 시도가 예외(`NodeTimeoutError` 포함)를 던지면 → retry policy가 재시도 여부
결정 → 재시도 소진 후에만 error handler 실행.

> per-node timeout과 node-level error handler는 `langgraph>=1.2`(alpha). retry policy는 그 이전부터 가능.

## Retries (재시도)

```python
from langgraph.types import RetryPolicy
builder.add_node("call_api", call_api, retry_policy=RetryPolicy(max_attempts=3))
```

**기본 동작** : `default_retry_on`은 다음(과 서브클래스)을 **제외**한 모든 예외를 재시도 —
`ValueError`, `TypeError`, `ArithmeticError`, `ImportError`, `LookupError`, `NameError`,
`SyntaxError`, `RuntimeError`, `ReferenceError`, `StopIteration`, `StopAsyncIteration`, `OSError`.
httpx/requests 등 HTTP 라이브러리는 5xx만 재시도. `NodeTimeoutError`는 기본 재시도 대상.

**파라미터** : `max_attempts`(3), `initial_interval`(0.5s), `backoff_factor`(2.0),
`max_interval`(128.0s), `jitter`(True), `retry_on`(예외 타입/시퀀스/콜러블).

**커스텀 재시도 로직** :
```python
from langgraph.types import RetryPolicy, default_retry_on

def custom_retry_on(exc: BaseException) -> bool:
    if isinstance(exc, MyCustomError):
        return False
    return default_retry_on(exc)

builder.add_node("call_api", call_api, retry_policy=RetryPolicy(max_attempts=3, retry_on=custom_retry_on))
```

**재시도 상태 검사** : `runtime.execution_info.node_attempt`로 현재 시도 번호(1-indexed). 폴백 전환에 유용.
```python
def my_node(state, runtime: Runtime):
    if runtime.execution_info.node_attempt > 1:
        return {"result": call_fallback_api()}
    return {"result": call_primary_api()}
```
`execution_info` 필드 : `node_attempt`, `node_first_attempt_time`, `thread_id`, `run_id`,
`checkpoint_id`, `task_id`. (retry policy 없어도 사용 가능, `node_attempt` 기본 1)

## Timeouts (langgraph>=1.2, alpha, **async 노드만**)

`add_node(timeout=)`에 초(숫자)/`timedelta`/`TimeoutPolicy` 전달. sync 노드에 timeout 지정 시 컴파일 거부.
블로킹 I/O는 async 노드 안에서 `asyncio.to_thread`로 감싼다.

```python
from langgraph.types import TimeoutPolicy
builder.add_node("call_model", call_model, timeout=60)
builder.add_node("call_model", call_model, timeout=TimeoutPolicy(run_timeout=120, idle_timeout=30))
```

- **`run_timeout`** : 단일 시도의 하드 월클럭 캡. 노드 활동과 무관하게 갱신 안 됨.
- **`idle_timeout`** : 진행이 멈춘 시간 캡. 진행 신호가 오면 시계 리셋.
  - 진행 신호(`refresh_on="auto"` 기본) : state writes, stream 출력, 자식 task 스케줄링, runtime
    stream-writer 호출, 노드/하위의 LangChain 콜백 이벤트(LLM 토큰, 도구 호출 등).
  - `refresh_on="heartbeat"` : 명시적 `runtime.heartbeat()` 호출로만 리셋. 장시간 작업에서 수동 호출.

```python
async def long_running_node(state, runtime: Runtime):
    for batch in fetch_batches():
        process(batch)
        runtime.heartbeat()    # idle 시계 수동 리셋 (idle-timed 시도 밖에선 no-op)
    return {"result": "done"}
```

**`NodeTimeoutError`** : 발생 시 실패 시도의 쓰기를 클리어. 필드 : `node`, `elapsed`, `kind`("idle"/"run"),
`idle_timeout`, `run_timeout`. 기본 재시도 대상이라 `retry_policy`와 함께 쓰면 매 시도마다 시계 리셋.

**Send 동적 timeout** : map-reduce에서 `Send("node", input, timeout=...)`로 특정 푸시의 정적 timeout 오버라이드.

## Error handling (langgraph>=1.2, alpha) — Saga/보상 패턴

노드 실패 + 모든 재시도 소진 후 실행. 현재 상태를 받아 `Command`로 갱신·다른 노드로 라우팅한다.
그래프 전체를 중단하지 않고 우아하게 복구(보상 트랜잭션)할 때 유용.

```python
from langgraph.errors import NodeError
from langgraph.types import Command, RetryPolicy

def charge_payment(state) -> State:
    raise RuntimeError("payment gateway timeout")

def payment_error_handler(state, error: NodeError) -> Command:
    return Command(update={"status": f"compensated: {error.error}"}, goto="finalize")

graph = (
    StateGraph(State)
    .add_node("charge_payment", charge_payment,
              retry_policy=RetryPolicy(max_attempts=3, retry_on=ConnectionError),
              error_handler=payment_error_handler)
    .add_node("finalize", finalize)
    .add_edge(START, "charge_payment")
    .compile()
)
```

핸들러는 `retry_policy` 소진 후(또는 retry policy 없으면 즉시) 발동. retry와 error handler는 독립 설정.

**`NodeError`** : frozen dataclass. `node`(실패 노드명), `error`(예외). 타입 어노테이션으로 주입(opt-in,
`runtime: Runtime`과 동일 패턴). 컨텍스트가 불필요하면 `(state)`나 `(state, runtime)` 시그니처도 가능.

**Resume-safe** : 실패 provenance가 체크포인트된다. 노드 실패 후 핸들러 완료 전 크래시해도, 재개 시
같은 `NodeError` 컨텍스트를 본다.

**`interrupt()`와의 동작** : 노드 안 `interrupt()`는 error handler로 **라우팅되지 않는다**. interrupt는
`GraphBubbleUp` 메커니즘으로 retry·error handler를 우회해 HITL용으로 정지한다.

**서브그래프 실패** : 서브그래프의 미처리 예외는 부모 노드로 표면화. 부모 노드에 `error_handler`가
있으면 `error.error`에 서브그래프 예외를 담아 발동.

## Functional API

`@task`와 `@entrypoint`에 동일한 `timeout=` / `retry_policy=` 사용 가능.
```python
@task(timeout=TimeoutPolicy(idle_timeout=30), retry_policy=RetryPolicy(max_attempts=3))
async def call_api(url: str) -> str: ...

@entrypoint(timeout=60)
async def my_workflow(inputs: dict) -> str: ...
```

## 제한

- **Python 전용** : timeout·error handler는 JS/TS SDK에 없음 (retry policy는 양쪽 가능).
- **timeout은 async 전용**.
- **노드당 핸들러 1개**.
- **핸들러 실패는 버블업** : error handler 자신이 raise하면 노드에 핸들러 없는 것처럼 전파.

> 깔끔하게 superstep 경계에서 정지 후 재개하려면 graceful shutdown(`durable-execution#graceful-shutdown`) 참조.
