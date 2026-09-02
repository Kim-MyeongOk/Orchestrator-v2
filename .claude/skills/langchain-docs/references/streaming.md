# Streaming

원문 : https://docs.langchain.com/oss/python/langchain/streaming

에이전트 실행에서 실시간 업데이트를 표면화한다. (신규 앱에는 LangChain v1.3에서 도입된 **event
streaming**의 타입드 프로젝션 API 권장 — references/event-streaming.md 참고)

가능한 것 : 에이전트 진행 스트리밍, LLM 토큰 스트리밍, 사고/추론 토큰 스트리밍, 커스텀 업데이트,
다중 모드 스트리밍.

## 지원 스트림 모드

`stream`/`astream`에 리스트로 전달.

| 모드 | 설명 |
|---|---|
| `updates` | 각 에이전트 단계 후 상태 업데이트. 같은 단계 내 다중 업데이트는 개별 스트리밍. |
| `messages` | LLM이 호출되는 노드에서 `(token, metadata)` 튜플 스트리밍. |
| `custom` | 그래프 노드 내부에서 stream writer로 커스텀 데이터 스트리밍. |

## 에이전트 진행 (`updates`)

```python
config = {"configurable": {"thread_id": str(uuid7())}}
for chunk in agent.stream(
    {"messages": [{"role": "user", "content": "What is the weather in SF?"}]},
    config=config,
    stream_mode="updates",
    version="v2",
):
    if chunk["type"] == "updates":
        for step, data in chunk["data"].items():
            print(f"step: {step}")
            print(f"content: {data['messages'][-1].content_blocks}")
```

`thread_id`로 대화를 checkpointing하면 후속 턴이 같은 히스토리를 재개한다(checkpointer 필요).
`stream_mode`와 독립적이며 `context`도 함께 전달 가능.

## LLM 토큰 (`messages`)

```python
for chunk in agent.stream({"messages": [...]}, stream_mode="messages", version="v2"):
    if chunk["type"] == "messages":
        token, metadata = chunk["data"]
        print(f"node: {metadata['langgraph_node']}")
        print(f"content: {token.content_blocks}")
```

도구 호출은 `tool_call_chunk`로 점진적으로 스트리밍된다.

## 커스텀 업데이트 (`custom`)

```python
from langgraph.config import get_stream_writer

def get_weather(city: str) -> str:
    """Get weather for a given city."""
    writer = get_stream_writer()
    writer(f"Looking up data for city: {city}")
    return f"It's always sunny in {city}!"

for chunk in agent.stream({"messages": [...]}, stream_mode="custom", version="v2"):
    if chunk["type"] == "custom":
        print(chunk["data"])
```

도구 안에서 `get_stream_writer`를 쓰면 LangGraph 실행 컨텍스트 밖에서 도구를 호출할 수 없다.

## 다중 모드

```python
for chunk in agent.stream({"messages": [...]}, stream_mode=["updates", "custom"], version="v2"):
    print(chunk["type"])  # 모드 식별
    print(chunk["data"])  # 페이로드
```

각 chunk는 `type`, `ns`, `data` 키를 가진 `StreamPart` dict다.

## 공통 패턴

### 사고/추론 토큰 스트리밍

모델에서 추론 출력을 활성화한 뒤 `"reasoning"` content block을 필터링. LangChain이 프로바이더별
포맷(Anthropic `thinking`, OpenAI `reasoning`)을 표준 `"reasoning"` 블록으로 정규화한다.

```python
from langchain.messages import AIMessageChunk
from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(model_name="claude-sonnet-4-6",
                      thinking={"type": "enabled", "budget_tokens": 5000})
agent = create_agent(model=model, tools=[get_weather])

for token, metadata in agent.stream({"messages": [...]}, stream_mode="messages"):
    if not isinstance(token, AIMessageChunk):
        continue
    reasoning = [b for b in token.content_blocks if b["type"] == "reasoning"]
    text = [b for b in token.content_blocks if b["type"] == "text"]
    if reasoning:
        print(f"[thinking] {reasoning[0]['reasoning']}", end="")
    if text:
        print(text[0]["text"], end="")
```

### 도구 호출 스트리밍

부분 JSON(생성 중)과 완성된 파싱 도구 호출 둘 다 스트리밍하려면 `stream_mode=["messages",
"updates"]`를 사용한다. `messages`로 chunk, `updates`로 완성 메시지(상태에 추적되는 경우).

```python
for chunk in agent.stream({"messages": [...]},
                          stream_mode=["messages", "updates"], version="v2"):
    if chunk["type"] == "messages":
        token, metadata = chunk["data"]
        # token.text, token.tool_call_chunks
    elif chunk["type"] == "updates":
        for source, update in chunk["data"].items():
            if source in ("model", "tools"):
                # update["messages"][-1] — 완성 메시지
                ...
```

상태에 추적되지 않으면 커스텀 업데이트를 쓰거나, 스트리밍 루프에서 chunk를 합산한다.

```python
full_message = None
for chunk in agent.stream(..., stream_mode=["messages", "updates"], version="v2"):
    if chunk["type"] == "messages":
        token, metadata = chunk["data"]
        if isinstance(token, AIMessageChunk):
            full_message = token if full_message is None else full_message + token
            if token.chunk_position == "last":
                if full_message.tool_calls:
                    print(f"Tool calls: {full_message.tool_calls}")
                full_message = None
```

### Human-in-the-loop 스트리밍

`HumanInTheLoopMiddleware` + checkpointer로 구성, `updates` 모드에서 `__interrupt__` 소스로
인터럽트 수집, `Command(resume=decisions)`로 응답. 결정 순서는 수집된 액션 순서와 일치해야 한다.

```python
for chunk in agent.stream({"messages": [...]}, config=config,
                          stream_mode=["messages", "updates"], version="v2"):
    if chunk["type"] == "updates":
        for source, update in chunk["data"].items():
            if source == "__interrupt__":
                interrupts.extend(update)
# ... 결정 수집 후
for chunk in agent.stream(Command(resume=decisions), config=config, ...):
    ...
```

### 서브에이전트로부터 스트리밍

여러 LLM이 있을 때 메시지 소스를 구분하려면 각 에이전트에 `name`을 부여하고, 스트림 생성 시
`subgraphs=True`를 지정한다. `"messages"` 모드 metadata의 `lc_agent_name` 키로 활성 에이전트 식별.

```python
for chunk in agent.stream({"messages": [...]},
                          stream_mode=["messages", "updates"],
                          subgraphs=True, version="v2"):
    if chunk["type"] == "messages":
        token, metadata = chunk["data"]
        if agent_name := metadata.get("lc_agent_name"):
            ...  # 활성 에이전트 추적
```

## 스트리밍 비활성화

특정 모델의 토큰 스트리밍을 끄려면 초기화 시 `streaming=False`(또는 base class의
`disable_streaming=True`). 멀티 에이전트에서 일부만 스트리밍하거나, 비스트리밍 모델을 섞을 때 유용.

```python
model = ChatOpenAI(model="gpt-5.4", streaming=False)
```

## v2 스트리밍 포맷 (LangGraph >= 1.1)

`version="v2"`로 통합 출력. 모든 chunk는 `type`/`ns`/`data` 키를 가진 `StreamPart` dict
(튜플 언패킹 불필요). `invoke()`도 `.value`/`.interrupts` 속성을 가진 `GraphOutput` 반환.

```python
# v2
for chunk in agent.stream(..., stream_mode=["updates", "custom"], version="v2"):
    print(chunk["type"], chunk["data"])

# v1 (현재 기본) — (mode, data) 튜플 언패킹 필요
for mode, chunk in agent.stream(..., stream_mode=["updates", "custom"]):
    print(mode, chunk)

result = agent.invoke({"messages": [...]}, version="v2")
print(result.value, result.interrupts)
```
