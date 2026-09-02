# 핸드오프 (Handoffs)

원문 : https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs

핸드오프 아키텍처에서는 **상태(state)에 따라 동작이 동적으로 바뀐다**. 핵심 메커니즘 : 도구가 턴을 넘어 영속되는 상태 변수(예 : `current_step`, `active_agent`)를 갱신하고, 시스템이 이 변수를 읽어 동작을 조정한다. 다른 설정(시스템 프롬프트, 도구)을 적용하거나 다른 에이전트로 라우팅한다. 이 패턴은 서로 다른 에이전트 간 핸드오프와 단일 에이전트 내 동적 설정 변경을 모두 지원한다.

"handoffs"라는 용어는 OpenAI가 도구 호출(예 : `transfer_to_sales_agent`)로 에이전트/상태 간 제어를 넘기는 것을 가리키며 만들었다.

## 핵심 특성

- **상태 기반 동작** : 상태 변수(예 : `current_step`, `active_agent`)에 따라 동작이 변한다.
- **도구 기반 전이** : 도구가 상태 변수를 갱신해 상태 간 이동한다.
- **직접 사용자 상호작용** : 각 상태의 설정이 사용자 메시지를 직접 처리한다.
- **영속 상태** : 상태가 대화 턴을 넘어 유지된다.

## 언제 사용하나

순차적 제약을 강제해야 할 때(전제 조건 충족 후에만 기능 해제), 에이전트가 서로 다른 상태에 걸쳐 사용자와 직접 대화해야 할 때, 다단계 대화 흐름을 만들 때 사용한다. 특정 순서로 정보를 수집해야 하는 고객 지원 시나리오(예 : 환불 처리 전 보증 ID 수집)에 특히 유용하다.

## 기본 구현

핵심은 `Command`를 반환해 상태를 갱신하고 새 단계/에이전트로의 전이를 트리거하는 도구다.

```python
from langchain.tools import tool
from langchain.messages import ToolMessage
from langgraph.types import Command

@tool
def transfer_to_specialist(runtime) -> Command:
    """Transfer to the specialist agent."""
    return Command(
        update={
            "messages": [
                ToolMessage(content="Transferred to specialist", tool_call_id=runtime.tool_call_id)
            ],
            "current_step": "specialist"  # 동작 변경 트리거
        }
    )
```

**왜 `ToolMessage`를 포함하나?** LLM이 도구를 호출하면 응답을 기대한다. `tool_call_id`가 일치하는 `ToolMessage`가 이 요청-응답 사이클을 완성한다. 없으면 대화 이력이 잘못된 형태가 된다. 핸드오프 도구가 messages를 갱신할 때마다 필요하다.

## 구현 방식 2가지

### 1) 단일 에이전트 + 미들웨어 (권장)

하나의 에이전트가 상태에 따라 동작을 바꾼다. 미들웨어가 각 모델 호출을 가로채 시스템 프롬프트와 가용 도구를 동적으로 조정한다. 도구는 상태 변수를 갱신해 전이를 트리거한다.

```python
from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse
from langchain.tools import tool, ToolRuntime
from langchain.messages import ToolMessage
from langgraph.types import Command
from typing import Callable

# 1. current_step 트래커를 가진 상태 정의
class SupportState(AgentState):
    current_step: str = "triage"
    warranty_status: str | None = None

# 2. 도구가 Command로 current_step 갱신
@tool
def record_warranty_status(status: str, runtime: ToolRuntime[None, SupportState]) -> Command:
    """Record warranty status and transition to next step."""
    return Command(update={
        "messages": [ToolMessage(content=f"Warranty status recorded: {status}", tool_call_id=runtime.tool_call_id)],
        "warranty_status": status,
        "current_step": "specialist"  # 다음 단계로 전이
    })

# 3. 미들웨어가 current_step 기반으로 동적 설정 적용
@wrap_model_call
def apply_step_config(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
    step = request.state.get("current_step", "triage")
    configs = {
        "triage":     {"prompt": "Collect warranty information...", "tools": [record_warranty_status]},
        "specialist": {"prompt": "Provide solutions based on warranty: {warranty_status}", "tools": [provide_solution, escalate]}
    }
    config = configs[step]
    request = request.override(system_prompt=config["prompt"].format(**request.state), tools=config["tools"])
    return handler(request)

# 4. 미들웨어를 가진 에이전트 생성
agent = create_agent(model, tools=[record_warranty_status, provide_solution, escalate],
                     state_schema=SupportState, middleware=[apply_step_config],
                     checkpointer=InMemorySaver())  # 턴 간 상태 영속
```

### 2) 다중 에이전트 서브그래프

여러 개의 뚜렷한 에이전트가 그래프의 별도 노드로 존재한다. 핸드오프 도구가 `Command.PARENT`로 다음 실행 노드를 지정해 에이전트 노드 사이를 이동한다. 서브그래프 핸드오프는 신중한 **컨텍스트 엔지니어링**이 필요하다. 단일 에이전트 미들웨어와 달리(메시지 이력이 자연히 흐름) 어떤 메시지를 에이전트 간에 넘길지 명시적으로 결정해야 한다.

```python
@tool
def transfer_to_sales(runtime: ToolRuntime) -> Command:
    """Transfer to the sales agent."""
    last_ai_message = next(msg for msg in reversed(runtime.state["messages"]) if isinstance(msg, AIMessage))
    transfer_message = ToolMessage(content="Transferred to sales agent", tool_call_id=runtime.tool_call_id)
    return Command(
        goto="sales_agent",
        update={
            "active_agent": "sales_agent",
            "messages": [last_ai_message, transfer_message],
        },
        graph=Command.PARENT
    )
```

대부분의 핸드오프 사례에는 **단일 에이전트 + 미들웨어**가 더 단순하므로 권장된다. 노드 자체가 reflection/retrieval 단계를 가진 복잡한 그래프인 경우처럼 맞춤형 에이전트 구현이 필요할 때만 **다중 에이전트 서브그래프**를 쓴다.

### 핸드오프 시 컨텍스트 처리

LLM은 도구 호출과 그 응답이 짝지어지길 기대하므로 `Command.PARENT`로 핸드오프할 때 둘 다 포함해야 한다.

1. 핸드오프를 트리거한 도구 호출을 담은 **`AIMessage`**
2. 그 도구 호출에 대한 인공 응답인 **`ToolMessage`**

이 짝이 없으면 수신 에이전트가 불완전한 대화를 보고 오류나 예상치 못한 동작을 낼 수 있다.

**서브에이전트 메시지를 전부 넘기지 않는 이유** : 전체 서브에이전트 대화를 핸드오프에 포함하면 수신 에이전트가 관련 없는 내부 추론에 혼란을 겪고 토큰 비용이 불필요하게 증가한다. 핸드오프 짝만 넘겨 부모 그래프의 컨텍스트를 고수준 조율에 집중시킨다. 추가 컨텍스트가 필요하면 원시 메시지 이력 대신 ToolMessage 내용에 서브에이전트 작업을 요약해 담는다.

**사용자에게 제어 반환** : 에이전트 턴을 끝내고 사용자에게 제어를 돌려줄 때 최종 메시지가 `AIMessage`인지 확인한다. 유효한 대화 이력을 유지하고 UI에 작업 완료를 알린다.

## 구현 시 고려사항

- **컨텍스트 필터링 전략** : 각 에이전트가 전체 대화 이력, 필터링된 일부, 요약 중 무엇을 받는가? 역할에 따라 필요한 컨텍스트가 다르다.
- **도구 의미론** : 핸드오프 도구가 라우팅 상태만 갱신하는지 부수 효과(예 : 지원 티켓 생성)도 수행하는지 명확히 한다.
- **토큰 효율** : 컨텍스트 완전성과 토큰 비용을 균형 맞춘다. 대화가 길어질수록 요약과 선택적 컨텍스트 전달이 중요해진다.
