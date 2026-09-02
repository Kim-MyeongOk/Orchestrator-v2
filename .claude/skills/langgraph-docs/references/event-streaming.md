# Event Streaming (v3, 타입드 프로젝션)

원문 : https://docs.langchain.com/oss/python/langgraph/event-streaming

LangGraph v1.2 도입. **대부분의 인프로세스 스트리밍에 권장**되는 모델. `stream_events(..., version="v3")`는
run stream 객체를 반환하고, **여러 프로젝션을 동시에 소비**할 수 있다.

## Quickstart

```python
stream = graph.stream_events(
    {"messages": [{"role": "user", "content": "What is 42 * 17?"}]},
    version="v3",
)
for message in stream.messages:
    for token in message.text:
        print(token, end="", flush=True)
final_state = stream.output
```

## 2계층 구조

1. **Streaming** : Pregel 엔진이 raw 실행 이벤트(`updates`/`values`/`messages`/`custom`/`checkpoints`/`tasks`/`debug`)를 emit.
2. **Event streaming** : 그 이벤트를 정규화 → stream transformer 파이프라인 → 타입드 프로젝션 노출.

**Event router**가 두 계층의 다리. 정규화된 Pregel 이벤트를 등록된 transformer에 통과시켜
`stream.messages`/`stream.values`/`stream.subgraphs`/`stream.output` 등 표준 프로젝션 생성.
커스텀 transformer는 `stream.extensions` 아래에 앱별 프로젝션 추가.

## 제공 프로젝션

| 프로젝션 | 용도 |
|---|---|
| `stream` | 모든 프로토콜 이벤트 순회 |
| `stream.messages` | 채팅 모델 메시지·토큰 델타 |
| `stream.values` | 상태 스냅샷 순회 + 최종값 대기 |
| `stream.output` | 최종 출력 대기 |
| `stream.subgraphs` | 중첩 그래프 실행 관찰 |
| `stream.interrupts` | HITL interrupt 페이로드 검사 |
| `stream.interrupted` | 사람 입력 대기 여부 확인 |
| `stream.extensions` | 커스텀 transformer 프로젝션 |

**여러 소비자가 동시에 읽을 수 있다.** `stream.messages`를 읽어도 `stream.values`/`subgraphs`/`output`이
필요로 하는 이벤트를 소비하지 않는다.

## Stream messages

```python
for message in stream.messages:
    text  = str(message.text)            # 전체 텍스트 (또는 토큰 단위로 순회)
    usage = message.output.usage_metadata
```

`message.reasoning`(추론 델타), `message.tool_calls`(도구 호출 인자 청크). text/reasoning/tool-call을
**정확한 도착 순서**로 받으려면 각 프로젝션 대신 메시지 스트림의 raw 이벤트를 순회한다.

## Stream subgraphs

```python
for subgraph in stream.subgraphs:
    print(subgraph.graph_name, subgraph.path)
    for message in subgraph.messages:
        print(message.text)
```

## Stream state

```python
for snapshot in stream.values:
    print(snapshot)
final_state = stream.output
```

## 여러 프로젝션 동시 (도착 순서)

```python
for name, item in stream.interleave("values", "messages", "subgraphs"):
    if name == "values": ...
    elif name == "messages": ...
    elif name == "subgraphs": ...
```

## Interrupt 후 재개

checkpointer + thread_id config 필요.

```python
from langgraph.types import Command

stream = graph.stream_events(input, version="v3")
for message in stream.messages:
    print(message.text)

if stream.interrupted:
    print(stream.interrupts)

stream = graph.stream_events(Command(resume={"decisions": [{"type": "approve"}]}), version="v3")
final_state = stream.output
```

## 모든 프로토콜 이벤트 (raw)

```python
for event in stream:
    namespace = event["params"]["namespace"]
    print(namespace, event["method"], event["params"]["data"])
```

**`ProtocolEvent` 봉투** (transformer의 `process(event)`도 이 형태를 받음) :

```python
class ProtocolEvent(TypedDict):
    seq: int                    # run 내 엄격 증가 — 순서에 사용
    method: str                 # 채널명: "messages", "values", "updates", "custom", "tools", "lifecycle", ...
    params: ProtocolEventParams

class ProtocolEventParams(TypedDict):
    namespace: list[str]        # 루트부터 "<name>:<runtime_id>" 세그먼트 경로. []는 루트
    timestamp: int              # 월클럭 ms (drift 가능, 순서에 의존 금지)
    data: Any                   # method별 페이로드
```

**namespace** : 루트(`[]`)부터 이벤트를 emit한 스코프까지의 경로. 자식 실행마다
`"name:runtime_id"` 세그먼트 추가. 서브그래프 내 도구 호출은 `["researcher:6f4d", "tools:91ac"]`.
`:` 앞은 안정적 그래프/노드명, 뒤는 호출별 runtime ID. (서브트리만 관심이면 직접 필터, 단 중첩
그래프는 `stream.subgraphs`가 이미 처리)

## 채널과 이벤트 라이프사이클

| 채널 | 용도 |
|---|---|
| `values` | 전체 그래프 상태 스냅샷 |
| `updates` | 노드별 상태 델타 |
| `messages` | content-block 중심 채팅 모델 출력 |
| `tools` | 도구 호출 start/output/finish/error |
| `lifecycle` | run/subgraph/subagent 상태 변화 |
| `checkpoints` | 분기·time travel용 경량 체크포인트 봉투 |
| `input` | HITL 입력 요청·응답 |
| `tasks` | Pregel task 생성·결과 |
| `custom` | 그래프 코드의 사용자 정의 페이로드 |
| `custom:<name>` | 앱 정의 stream transformer 출력 |

**messages 채널** (content block 모델) : `data["event"]`가 `message-start` / `content-block-start` /
`content-block-delta` / `content-block-finish` / `message-finish`. 블록은 명시적 경계(start→deltas→finish).
`message-finish`에 토큰 usage 포함 가능. raw content-block 직접 소비 :

```python
for event in stream:
    if event["method"] != "messages": continue
    data = event["params"]["data"]
    if data.get("event") != "content-block-delta": continue
    block = data.get("delta") or {}
    if block.get("type") == "text-delta":
        print(block.get("text", ""), end="", flush=True)
    elif block.get("type") == "reasoning-delta":
        print(f"[thinking]{block.get('reasoning', '')}", end="", flush=True)
```

**tools 채널** : `tool-started` / `tool-output-delta` / `tool-finished` / `tool-error`. tool call ID로
correlate되어 messages 채널의 도구 호출 블록과 조인 가능.
**lifecycle 채널** : `started` / `running` / `completed` / `failed` / `interrupted` (+ `graph_name`, `error`, `cause`).

## 커스텀 프로젝션 (Stream Transformer) 만들기

transformer는 프로토콜 이벤트를 관찰하고 자체 상태를 유지하며 파생 뷰(도구 활동, 토큰 합계, 진행
이벤트 등)를 노출한다. observational(런타임을 다시 호출하지 않음).

```python
from langgraph.stream import ProtocolEvent, StreamTransformer

class MyTransformer(StreamTransformer):
    def init(self) -> dict: ...           # 프로젝션 객체 생성 (stream.extensions 아래)
    def process(self, event: ProtocolEvent) -> bool: ...   # 이벤트 관찰. False면 원본 억제
    def finalize(self) -> None: ...        # 성공 종료 후 정리
    def fail(self, err: BaseException) -> None: ...
```

**`required_stream_modes`** : 그래프가 emit할 Pregel 모드 선언. 런타임은 모든 transformer의 합집합을
`.stream()`의 `stream_mode`로 전달한다. **아무도 요청 안 한 모드는 emit되지 않는다** —
`("custom",)` 선언이 있어야 custom 이벤트가 흐른다. `process()`는 모든 이벤트를 받으므로
`event["method"]`로 필터한다. 유효값 : `"messages"/"tools"/"custom"/"values"/"updates"/"checkpoints"/"tasks"/"debug"`.

**`StreamChannel`** : transformer의 스트리밍 값 프리미티브. 항상 `stream.extensions.<name>`에 이터러블 노출.
- `StreamChannel()` : 사이드 채널 프로젝션만 (직렬화 불가 핸들·promise·async iterable 보관에 적합)
- `StreamChannel(name)` : 각 `push()`가 메인 이벤트 스트림에도 `custom:<name>` 이벤트로 흐름 (값 직렬화 필요)

채널 라이프사이클은 stream handler가 소유 — transformer는 push만 한다.

```python
# 예 : 토큰 합계 최종값 프로젝션
class StatsTransformer(StreamTransformer):
    required_stream_modes = ("messages",)
    def __init__(self, scope=()):
        super().__init__(scope)
        self.total_tokens = 0
        self.total_tokens_log = StreamChannel[int]()
    def init(self): return {"total_tokens": self.total_tokens_log}
    def process(self, event):
        data = event["params"]["data"]
        if isinstance(data, dict):
            self.total_tokens += (data.get("usage") or {}).get("output_tokens") or 0
        return True
    def finalize(self):
        self.total_tokens_log.push(self.total_tokens)
        self.total_tokens_log.close()
```

**등록** : 호출 시 `stream_events(input, version="v3", transformers=[...])`, 또는 컴파일 시
`builder.compile(transformers=[...])`.

**내장 `ToolCallTransformer`** : 평범한 `StateGraph`에 `stream.tool_calls` 노출.
```python
from langgraph.prebuilt import ToolCallTransformer
stream = graph.stream_events(input, version="v3", transformers=[ToolCallTransformer])
for tool_call in stream.tool_calls:
    print(tool_call.tool_name, tool_call.input)
```

## 관련

- 와이어 레벨 이벤트·커맨드 포맷 : Agent Protocol (`langchain-protocol` on PyPI).
- Agent Server 배포 그래프 스트리밍 : LangSmith Streaming API.
