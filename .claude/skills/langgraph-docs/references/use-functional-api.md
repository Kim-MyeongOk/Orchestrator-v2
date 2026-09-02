# Use the Functional API (실전 가이드)

원문 : https://docs.langchain.com/oss/python/langgraph/use-functional-api

functional-api.md 개념의 실전 how-to.

## 단순 워크플로우

entrypoint 입력은 **첫 인자만**. 여러 입력은 dict.

```python
@entrypoint(checkpointer=checkpointer)
def workflow(inputs: dict) -> str:
    even = is_even(inputs["number"]).result()
    return format_message(even).result()

workflow.invoke({"number": 7}, config={"configurable": {"thread_id": "..."}})
```

## 병렬 실행

task를 동시 호출하고 결과 대기(I/O-bound 성능 향상).

```python
@entrypoint(checkpointer=checkpointer)
def graph(numbers: list[int]) -> list[str]:
    futures = [add_one(i) for i in numbers]
    return [f.result() for f in futures]
```

## 그래프 호출

Functional·Graph API는 같은 런타임 — 함께 사용 가능.

```python
@entrypoint()
def some_workflow(some_input: dict) -> int:
    result_1 = some_graph.invoke(...)     # Graph API 그래프 호출
    result_2 = another_graph.invoke(...)
    return {"result_1": result_1, "result_2": result_2}
```

## 다른 entrypoint 호출

entrypoint·task 안에서 다른 entrypoint 호출(자식은 부모 checkpointer 자동 사용).

```python
@entrypoint()
def multiply(inputs: dict) -> int:
    return inputs["a"] * inputs["b"]

@entrypoint(checkpointer=checkpointer)
def main(inputs: dict) -> dict:
    result = multiply.invoke({"a": inputs["x"], "b": inputs["y"]})
    return {"product": result}
```

## 스트리밍

Graph API와 같은 메커니즘. `stream_events(..., version="v3")` + `interleave("values")`.

```python
stream = main.stream_events({"x": 5}, config=config, version="v3")
for mode, chunk in stream.interleave("values"):
    print(f"{mode}: {chunk}")
```

> Python < 3.11 + async : `get_stream_writer` 대신 `StreamWriter`를 entrypoint 인자로 직접 받음.

## retry 정책

```python
from langgraph.types import RetryPolicy

@task(retry_policy=RetryPolicy(retry_on=ValueError))
def get_info():
    ...
```

## 타임아웃 (async task/entrypoint만)

```python
from langgraph.errors import NodeTimeoutError

@task(timeout=1.0, retry_policy=RetryPolicy(retry_on=NodeTimeoutError))
async def call_api(url: str) -> str:
    await asyncio.sleep(2)
    return f"result from {url}"

@entrypoint(timeout=5.0)
async def workflow(inputs: dict) -> str:
    return await call_api(inputs["url"])
```

초 또는 `timedelta`. sync 함수에 timeout 설정 시 선언 시점 에러. 초과 시 `NodeTimeoutError`(Python
`TimeoutError` 서브클래스). 타임아웃은 시도마다 독립 적용(재시도 시 타이머 리셋).

## task 캐싱

```python
@task(cache_policy=CachePolicy(ttl=120))
def slow_add(x: int) -> int:
    time.sleep(1)
    return x * 2

@entrypoint(cache=InMemoryCache())
def main(inputs: dict) -> dict[str, int]:
    ...
```

## 에러 후 재개

task 결과가 체크포인트에 저장되므로 재개 시 완료된 task(`slow_task`)는 재실행 안 함. 에러 해결 후
`main.invoke(None, config)`로 재개.

## Human-in-the-loop

`interrupt` + `Command`. interrupt는 task 안에서 호출 — 이전 task 결과는 영속되어 재실행 안 됨.

```python
@task
def human_feedback(input_query):
    """사용자 입력을 추가합니다."""
    feedback = interrupt(f"Please provide feedback: {input_query}")
    return f"{input_query} {feedback}"

@entrypoint(checkpointer=checkpointer)
def graph(input_query):
    result_1 = step_1(input_query).result()
    result_2 = human_feedback(result_1).result()
    return step_3(result_2).result()

# 재개
graph.stream_events(Command(resume="baz"), config, version="v3")
```

### 도구 호출 검토

```python
def review_tool_call(tool_call: ToolCall) -> Union[ToolCall, ToolMessage]:
    human_review = interrupt({"question": "Is this correct?", "tool_call": tool_call})
    review_action = human_review["action"]
    if review_action == "continue":
        return tool_call
    elif review_action == "update":
        return {**tool_call, **{"args": human_review.get("data")}}
    elif review_action == "feedback":
        return ToolMessage(content=human_review.get("data"), name=tool_call["name"],
                           tool_call_id=tool_call["id"])
```

## 단기 메모리·체크포인트 관리

- **상태 조회** : `graph.get_state(config)` → `StateSnapshot`(values·next·config·metadata·tasks·interrupts).
  특정 체크포인트는 `checkpoint_id` 지정.
- **이력 조회** : `list(graph.get_state_history(config))`.

### entrypoint.final (반환값↔저장값 분리)

```python
@entrypoint(checkpointer=checkpointer)
def accumulate(n: int, *, previous: int | None) -> entrypoint.final[int, int]:
    previous = previous or 0
    total = previous + n
    return entrypoint.final(value=previous, save=total)   # previous 반환, total 저장
# invoke(1)→0, invoke(2)→1, invoke(3)→3
```

### 챗봇 예시

```python
@task
def call_model(messages: list[BaseMessage]):
    return model.invoke(messages)

@entrypoint(checkpointer=checkpointer)
def workflow(inputs: list[BaseMessage], *, previous: list[BaseMessage]):
    if previous:
        inputs = add_messages(previous, inputs)
    response = call_model(inputs).result()
    return entrypoint.final(value=response, save=add_messages(inputs, response))
```

## 장기 메모리

서로 다른 thread id 간 정보 저장(`store`). 한 대화에서 학습한 사용자 정보를 다른 대화에서 사용.

## 다른 프레임워크 통합

Functional API로 persistence·memory·streaming이 없는 다른 에이전트 프레임워크에 LangGraph 기능 추가
(langsmith/deploy-other-frameworks).
