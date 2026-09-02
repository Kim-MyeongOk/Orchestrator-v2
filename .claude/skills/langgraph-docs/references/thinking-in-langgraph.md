# Thinking in LangGraph

원문 : https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph

LangGraph로 에이전트를 빌드하는 사고 과정. 자동화하려는 프로세스를 **노드(nodes)**라는 개별 단계로
쪼개고, 각 노드의 결정·전이를 기술하고, 노드들이 공유 **상태(state)**를 읽고 쓰며 연결한다.
(예제 : 고객 지원 이메일 에이전트)

## 5단계 워크플로우

### 1단계 : 워크플로우를 개별 단계로 분해
각 단계 = 노드(한 가지 일만 하는 함수). 노드 간 연결을 스케치한다. 일부 노드는 다음 행선지를
**결정**하고(`Classify Intent`), 일부는 항상 같은 다음 단계로 진행한다(`Read Email`→`Classify Intent`).

### 2단계 : 각 단계가 할 일 식별
노드 유형별로 필요한 컨텍스트를 정한다.
- **LLM 단계** : 이해/분석/생성/추론 결정. 정적 컨텍스트(프롬프트) + 동적 컨텍스트(상태).
- **데이터 단계** : 외부 소스 조회. 파라미터, 재시도(지수 백오프), 캐싱.
- **액션 단계** : 외부 동작 수행. 실행 시점, 재시도 전략. 캐시 금지(매 동작이 고유).
- **사용자 입력 단계** : 인간 개입. 결정에 필요한 컨텍스트, 입력 포맷, 트리거 조건.

### 3단계 : 상태 설계
상태 = 모든 노드가 접근하는 공유 메모리(에이전트의 노트북).

**상태에 넣을 것** : 단계 간 영속이 필요한 데이터.
**넣지 말 것** : 다른 데이터에서 파생 가능한 것(필요할 때 계산).

**핵심 원칙 : 상태는 원시(raw) 데이터를 저장하고, 프롬프트는 노드 안에서 온디맨드로 포맷한다.**
이로써 노드마다 같은 데이터를 다르게 포맷하고, 스키마 변경 없이 템플릿을 바꾸며, 디버깅이 명확해진다.

```python
from typing import TypedDict, Literal

class EmailClassification(TypedDict):
    intent: Literal["question", "bug", "billing", "feature", "complex"]
    urgency: Literal["low", "medium", "high", "critical"]
    topic: str
    summary: str

class EmailAgentState(TypedDict):
    email_content: str           # 원시 이메일
    sender_email: str
    email_id: str
    classification: EmailClassification | None
    search_results: list[str] | None
    customer_history: dict | None
    draft_response: str | None
    messages: list[str] | None
```

### 4단계 : 노드 구현
노드는 현재 상태를 받아 업데이트를 반환하는 파이썬 함수. 라우팅 결정 시 `Command`로 상태
업데이트 + 다음 행선지를 함께 지정한다.

**에러 처리 전략 (유형별)** :

| 에러 유형 | 해결 주체 | 전략 |
|---|---|---|
| 일시적(네트워크/레이트리밋) | 시스템 자동 | `RetryPolicy` |
| LLM 복구 가능(도구 실패/파싱) | LLM | 에러를 상태에 저장 후 루프백 |
| 사용자 수정 가능(정보 누락) | 인간 | `interrupt()`로 일시정지 |
| 예상치 못한 에러 | 개발자 | 그대로 버블업 (`raise`) |

```python
# 일시적 에러 : 재시도 정책
from langgraph.types import RetryPolicy
workflow.add_node("search_documentation", search_documentation,
                  retry_policy=RetryPolicy(max_attempts=3, initial_interval=1.0))

# LLM 복구 가능 : 에러를 상태에 넣고 루프백
from langgraph.types import Command
def execute_tool(state) -> Command[Literal["agent", "execute_tool"]]:
    try:
        result = run_tool(state["tool_call"])
        return Command(update={"tool_result": result}, goto="agent")
    except ToolError as e:
        return Command(update={"tool_result": f"Tool error: {e}"}, goto="agent")

# 사용자 수정 가능 : interrupt
def lookup(state) -> Command[Literal["draft_response"]]:
    if not state.get("customer_id"):
        user_input = interrupt({"message": "Customer ID needed", ...})
        return Command(update={"customer_id": user_input["customer_id"]}, goto="lookup")
    ...
```

**라우팅 노드** : 반환 타입 힌트 `Command[Literal["node1", "node2"]]`로 갈 수 있는 노드를 선언.

```python
def classify_intent(state) -> Command[Literal["search_documentation", "human_review", ...]]:
    structured_llm = llm.with_structured_output(EmailClassification)
    classification = structured_llm.invoke(prompt)   # 프롬프트는 온디맨드 포맷
    if classification["intent"] == "billing" or classification["urgency"] == "critical":
        goto = "human_review"
    elif ...
    return Command(update={"classification": classification}, goto=goto)
```

### 5단계 : 그래프 연결
노드가 자체 라우팅하므로 필수 엣지만 정의한다. `interrupt()`로 HITL을 쓰려면 **checkpointer**로
컴파일해 실행 간 상태를 저장한다. (로컬 서버로 실행 시엔 checkpointer 없이 컴파일)

```python
from langgraph.checkpoint.memory import MemorySaver

workflow = StateGraph(EmailAgentState)
workflow.add_node("read_email", read_email)
workflow.add_node("classify_intent", classify_intent)
workflow.add_node("search_documentation", search_documentation, retry_policy=RetryPolicy(max_attempts=3))
# ... 나머지 노드
workflow.add_edge(START, "read_email")
workflow.add_edge("read_email", "classify_intent")
workflow.add_edge("send_reply", END)

app = workflow.compile(checkpointer=MemorySaver())

# 실행 (thread_id로 영속성)
config = {"configurable": {"thread_id": "customer_123"}}
result = app.invoke(initial_state, config)   # human_review에서 일시정지
# 재개
from langgraph.types import Command
app.invoke(Command(resume={"approved": True, "edited_response": "..."}), config)
```

## 핵심 통찰

- **개별 단계로 분해** : 각 노드는 한 가지를 잘한다 → 진행 스트리밍, durable execution(정지/재개), 명확한 디버깅.
- **상태는 공유 메모리** : 원시 데이터 저장, 포맷된 텍스트 금지.
- **노드는 함수** : 상태를 받아 일하고 업데이트 반환. 라우팅 시 업데이트 + 행선지 지정.
- **에러는 흐름의 일부** : 유형별 처리(재시도/루프백/interrupt/버블업).
- **인간 입력은 1급** : `interrupt()`는 무기한 정지·전체 상태 저장·정확한 지점 재개. 노드 내 다른 동작보다 먼저 와야 한다(재개 시 이전 코드 재실행됨).
- **그래프 구조는 자연스럽게 도출** : 필수 연결만 정의, 노드가 라우팅 로직을 처리.

## 노드 입도(granularity) 트레이드오프

durable execution은 노드 경계에서 체크포인트를 만든다. 노드를 **작게** 쪼개면 체크포인트가 잦아져
실패 시 재실행 비용이 적다. 큰 노드 하나에 여러 동작을 묶으면 끝부분 실패 시 노드 처음부터 재실행한다.
외부 서비스 격리, 중간 가시성, 서로 다른 실패 모드, 재사용·테스트 용이성을 위해 분리한다.
노드가 많다고 느려지지 않는다 — 기본 async durability 모드는 백그라운드에서 체크포인트를 쓴다.
