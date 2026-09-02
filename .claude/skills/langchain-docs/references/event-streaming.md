# Event Streaming

원문 : https://docs.langchain.com/oss/python/langchain/event-streaming

LangChain 에이전트는 LangGraph 기반이므로 동일한 Event Streaming 모델을 지원하며, 메시지/도구
호출/상태/커스텀 업데이트에 대한 에이전트 중심 프로젝션을 제공한다. 대부분의 애플리케이션/프론트엔드
유스케이스에는 `stream_events(..., version="v3")`를 사용한다. Event Streaming은 타입드 프로젝션을
가진 run 객체를 반환하므로, stream-mode 튜플을 파싱하는 대신 필요한 뷰를 선택할 수 있다.

(저수준 Pregel stream 모드 `updates`/`messages`/`custom`은 references/streaming.md 참고)

## 기본 사용

```python
from langchain.agents import create_agent

def get_weather(city: str) -> str:
    """Get weather for a city."""
    return f"It's always sunny in {city}!"

agent = create_agent(model="gpt-5-nano", tools=[get_weather])

run = agent.stream_events(
    {"messages": [{"role": "user", "content": "What is the weather in SF?"}]},
    version="v3",
)

for message in run.messages:
    for delta in message.text:
        print(delta, end="", flush=True)

final_state = run.output
```

## 스트리밍 가능한 프로젝션

| 프로젝션 | 용도 |
|---|---|
| `for event in run` | 정확한 도착 순서가 필요할 때 원시 프로토콜 이벤트 |
| `run.messages` | 모델 메시지 스트림(LLM 호출당 하나) |
| `message.text` | 메시지의 텍스트 델타 및 최종 텍스트 |
| `message.reasoning` | 추론 콘텐츠를 노출하는 모델의 추론 델타 |
| `message.tool_calls` | 도구 호출 인자 청크 및 완성된 도구 호출 |
| `message.output` | 모델 호출 완료 후 최종 메시지 객체 |
| `message.usage` | 프로바이더가 반환하면 토큰 사용량 메타데이터 |
| `run.values` | 에이전트 상태 스냅샷 |
| `run.output` | 최종 에이전트 상태 |
| `run.extensions` | 커스텀 트랜스포머 프로젝션 |
| `run.tool_calls` | 도구 실행 라이프사이클, 입력, 출력 델타, 최종 출력, 에러 |

`run.messages`는 `ChatModelStream` 객체를 yield한다. 각 메시지 스트림은 `.text`, `.reasoning`,
`.tool_calls`, `.output`을 노출한다. sync 프로젝션은 라이브 델타를 위해 iterable이고 최종값을 위해
drainable하다.

## 에이전트 메시지 스트리밍

```python
run = agent.stream_events(input, version="v3")

for message in run.messages:
    print(f"[{message.node}] ", end="")
    for delta in message.text:
        print(delta, end="", flush=True)

    full_message = message.output
    usage = full_message.usage_metadata
    if usage:
        print(usage)
```

## 도구 호출 스트리밍

두 가지 프로젝션 :
- `message.tool_calls` : 모델이 도구 호출을 생성하는 동안 인자 청크 스트리밍.
- `run.tool_calls` : 도구 호출 시작 후 도구 실행 라이프사이클 스트리밍.

```python
run = agent.stream_events(input, version="v3")

for message in run.messages:
    for chunk in message.tool_calls:
        print(f"tool call chunk: {chunk}")
    finalized = message.tool_calls.get()
    if finalized:
        print(f"finalized tool calls: {finalized}")

for call in run.tool_calls:
    print(f"{call.tool_name}({call.input})")
    for delta in call.output_deltas:
        print(delta, end="", flush=True)
    print(call.output, call.error)
```

## 상태 및 최종 출력 스트리밍

```python
run = agent.stream_events(input, version="v3")

for snapshot in run.values:
    print(snapshot)

final_state = run.output
```

## 참고

실행 가능한 예제 : https://github.com/langchain-ai/streaming-cookbook
