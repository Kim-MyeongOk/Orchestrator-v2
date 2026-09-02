# 서브에이전트 (Subagents)

원문 : https://docs.langchain.com/oss/python/langchain/multi-agent/subagents

서브에이전트 아키텍처에서는 중앙 메인 에이전트(흔히 **supervisor**라 부름)가 서브에이전트들을 **도구로 호출**하여 조율한다. 메인 에이전트가 어떤 서브에이전트를 호출할지, 무슨 입력을 줄지, 결과를 어떻게 합칠지 결정한다. 서브에이전트는 **무상태(stateless)** — 과거 상호작용을 기억하지 않으며 모든 대화 메모리는 메인 에이전트가 유지한다. 이로써 **컨텍스트 격리**가 이뤄진다. 각 서브에이전트 호출은 깨끗한 컨텍스트 윈도우에서 동작하여 메인 대화의 컨텍스트 비대화를 막는다.

내장 서브에이전트 지원은 Deep Agents를 참조.

## 핵심 특성

- **중앙집중 제어** : 모든 라우팅이 메인 에이전트를 거친다.
- **직접 사용자 상호작용 없음** : 서브에이전트는 사용자가 아니라 메인 에이전트에 결과를 반환한다 (단, 서브에이전트 내부에서 interrupt로 사용자 입력을 받을 수는 있다).
- **도구를 통한 서브에이전트 호출**.
- **병렬 실행** : 메인 에이전트가 한 턴에 여러 서브에이전트를 호출할 수 있다.

**Supervisor vs Router** : supervisor(이 패턴)는 대화 컨텍스트를 유지하며 여러 턴에 걸쳐 어떤 서브에이전트를 호출할지 동적으로 결정하는 완전한 에이전트다. router는 보통 단일 분류 단계로 진행 중인 대화 상태를 유지하지 않고 에이전트로 디스패치한다.

## 언제 사용하나

여러 개의 뚜렷한 도메인(달력, 이메일, CRM, 데이터베이스)이 있고, 서브에이전트가 사용자와 직접 대화할 필요가 없으며, 중앙집중 워크플로우 제어를 원할 때 사용한다. 도구가 몇 개뿐인 단순한 경우엔 단일 에이전트를 쓴다.

## 기본 구현

핵심 메커니즘은 서브에이전트를 메인 에이전트가 호출할 수 있는 도구로 감싸는 것이다.

```python
from langchain.tools import tool
from langchain.agents import create_agent

# 서브에이전트 생성
subagent = create_agent(model="google_genai:gemini-3.5-flash", tools=[...])

# 도구로 감싸기
@tool("research", description="Research a topic and return findings")
def call_research_agent(query: str):
    result = subagent.invoke({"messages": [{"role": "user", "content": query}]})
    return result["messages"][-1].content

# 서브에이전트를 도구로 가진 메인 에이전트
main_agent = create_agent(model="google_genai:gemini-3.5-flash", tools=[call_research_agent])
```

## 설계 결정

| 결정 | 선택지 |
|---|---|
| **동기 vs 비동기** | Sync(블로킹) vs Async(백그라운드) |
| **도구 패턴** | 에이전트당 도구 vs 단일 디스패치 도구 |
| **서브에이전트 명세** | 시스템 프롬프트 vs enum 제약 vs 도구 기반 발견 (단일 디스패치 도구 전용) |
| **서브에이전트 입력** | 쿼리만 vs 전체 컨텍스트 |
| **서브에이전트 출력** | 서브에이전트 결과 vs 전체 대화 이력 |

## 동기 vs 비동기

| 모드 | 메인 에이전트 동작 | 적합 | 트레이드오프 |
|---|---|---|---|
| **Sync** | 서브에이전트 완료까지 대기 | 결과가 있어야 진행 가능할 때 | 단순하지만 대화를 막음 |
| **Async** | 백그라운드 실행 중 계속 진행 | 독립적 작업, 사용자가 기다리면 안 될 때 | 반응성 좋지만 복잡함 |

여기서 "async"는 파이썬의 `async`/`await`가 아니라, 메인 에이전트가 백그라운드 잡(보통 별도 프로세스/서비스)을 시작하고 블로킹 없이 계속하는 것을 뜻한다.

### 동기 (기본값)

기본적으로 서브에이전트 호출은 동기다. 메인 에이전트의 다음 행동이 서브에이전트 결과에 의존할 때, 작업에 순서 의존성이 있을 때, 서브에이전트 실패가 메인 응답을 막아야 할 때 사용한다. 구현이 단순하지만 모든 서브에이전트가 완료될 때까지 사용자는 응답을 못 받고, 장시간 작업은 대화를 멈추게 한다.

### 비동기

서브에이전트 작업이 독립적일 때(메인 에이전트가 결과 없이도 대화를 계속할 수 있을 때) 사용한다. **3-도구 패턴** :

1. **Start job** : 백그라운드 작업을 시작하고 job ID 반환
2. **Check status** : 현재 상태 반환 (pending, running, completed, failed)
3. **Get result** : 완료된 결과 조회

잡 완료 처리 : 잡이 끝나면 애플리케이션이 사용자에게 알려야 한다. 한 가지 방법은 클릭 시 "Check job_123 and summarize the results" 같은 `HumanMessage`를 보내는 알림을 띄우는 것이다.

## 도구 패턴

| 패턴 | 적합 | 트레이드오프 |
|---|---|---|
| **에이전트당 도구 (Tool per agent)** | 각 서브에이전트 입출력을 세밀하게 제어 | 셋업이 많지만 커스터마이징 풍부 |
| **단일 디스패치 도구 (Single dispatch tool)** | 많은 에이전트, 분산 팀, 관례 우선 | 조합이 단순하지만 에이전트별 커스터마이징 적음 |

### 단일 디스패치 도구

하나의 매개변수화된 `task` 도구로 휘발성 서브에이전트를 호출한다. 작업 설명이 서브에이전트에 human message로 전달되고 서브에이전트의 최종 메시지가 도구 결과로 반환된다. 새 에이전트를 코디네이터 수정 없이 확장 가능하게 추가할 때, 강한 컨텍스트 격리가 필요할 때, 관례를 선호할 때 사용한다.

```python
from langchain.tools import tool
from langchain.agents import create_agent

research_agent = create_agent(model="gpt-5.4", prompt="You are a research specialist...")
writer_agent   = create_agent(model="gpt-5.4", prompt="You are a writing specialist...")

SUBAGENTS = {
    "research": research_agent,
    "writer": writer_agent,
}

@tool
def task(agent_name: str, description: str) -> str:
    """Launch an ephemeral subagent for a task.

    Available agents:
    - research: Research and fact-finding
    - writer: Content creation and editing
    """
    agent = SUBAGENTS[agent_name]
    result = agent.invoke({"messages": [{"role": "user", "content": description}]})
    return result["messages"][-1].content

main_agent = create_agent(model="gpt-5.4", tools=[task], system_prompt="You coordinate specialized sub-agents...")
```

## 컨텍스트 엔지니어링

| 범주 | 목적 | 영향 |
|---|---|---|
| **서브에이전트 명세** | 마땅히 호출되어야 할 때 서브에이전트가 호출되도록 | 메인 에이전트 라우팅 결정 |
| **서브에이전트 입력** | 최적화된 컨텍스트로 잘 실행되도록 | 서브에이전트 성능 |
| **서브에이전트 출력** | supervisor가 결과에 따라 행동할 수 있도록 | 메인 에이전트 성능 |

### 서브에이전트 명세

서브에이전트의 **이름**과 **설명**이 메인 에이전트가 어떤 서브에이전트를 호출할지 아는 주된 수단이다. 프롬프팅 레버이므로 신중히 선택한다.

- **Name** : 명확하고 행동 지향적으로 (예 : `research_agent`, `code_reviewer`).
- **Description** : 어떤 작업을 처리하고 언제 써야 하는지 구체적으로.

단일 디스패치 도구 설계에서는 서브에이전트 정보를 추가로 제공해야 한다.

| 방법 | 적합 | 트레이드오프 |
|---|---|---|
| 시스템 프롬프트 열거 | 작고 정적인 목록 (<10개) | 단순하나 에이전트 변경 시 프롬프트 수정 필요 |
| Enum 제약 | 작고 정적인 목록 (<10개) | 타입 안전·명시적이나 코드 변경 필요 |
| 도구 기반 발견 | 크거나 동적인 레지스트리 | 유연·확장성 좋으나 복잡도 증가 |

도구 기반 발견 예 : `list_agents` 또는 `search_agents` 도구로 메인 에이전트가 온디맨드로 가용 에이전트를 발견하게 한다. 점진적 공개(progressive disclosure)와 동적 레지스트리를 지원한다.

### 서브에이전트 입력

서브에이전트가 받을 컨텍스트를 커스터마이징한다. 정적 프롬프트에 담기 어려운 전체 메시지 이력, 이전 결과, 작업 메타데이터를 에이전트 상태에서 끌어와 추가한다.

```python
from langchain.agents import AgentState
from langchain.tools import tool, ToolRuntime

class CustomState(AgentState):
    example_state_key: str

@tool("subagent1_name", description="subagent1_description")
def call_subagent1(query: str, runtime: ToolRuntime[None, CustomState]):
    subagent_input = some_logic(query, runtime.state["messages"])
    result = subagent1.invoke({
        "messages": subagent_input,
        "example_state_key": runtime.state["example_state_key"]
    })
    return result["messages"][-1].content
```

### 서브에이전트 출력

메인 에이전트가 좋은 결정을 내리도록 돌려받는 내용을 커스터마이징한다. 두 가지 전략 :

1. **서브에이전트 프롬프트** : 무엇을 반환해야 하는지 명시한다. 흔한 실패 모드는 서브에이전트가 도구 호출/추론은 했지만 결과를 최종 메시지에 담지 않는 것 — supervisor는 최종 출력만 본다는 점을 상기시킨다.
2. **코드에서 포맷** : 반환 전 응답을 조정/보강한다. 예를 들어 `Command`로 최종 텍스트 외에 특정 상태 키도 돌려보낸다.

```python
from typing import Annotated
from langchain.agents import AgentState
from langchain.tools import InjectedToolCallId
from langgraph.types import Command

@tool("subagent1_name", description="subagent1_description")
def call_subagent1(query: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
    result = subagent1.invoke({"messages": [{"role": "user", "content": query}]})
    return Command(update={
        "example_state_key": result["example_state_key"],
        "messages": [ToolMessage(content=result["messages"][-1].content, tool_call_id=tool_call_id)]
    })
```

## 체크포인팅과 상태 검사

기본적으로 서브에이전트는 **상속된 체크포인터** 모드를 쓴다. 각 호출이 새 상태로 시작하고 interrupt를 지원하며 병렬로 안전하게 실행된다. 서브에이전트가 호출 간 영속적 대화 이력을 유지해야 하면 `checkpointer=True`(continuations 모드)로 컴파일한다.

서브에이전트는 도구 함수 안에서 호출되므로 LangGraph가 정적으로 발견할 수 없다. 따라서 `get_state(subgraphs=...)`가 서브에이전트 상태를 반환하지 않는다. 중첩 그래프 상태를 읽어야 하면(예 : interrupt 중) 커스텀 그래프의 노드 함수에서 서브에이전트를 호출한다.
