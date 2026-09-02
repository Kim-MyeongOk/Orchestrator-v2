# 라우터 (Router)

원문 : https://docs.langchain.com/oss/python/langchain/multi-agent/router

라우터 아키텍처에서는 라우팅 단계가 입력을 분류하여 특화 에이전트로 보낸다. 각각 자기 에이전트가 필요한 뚜렷한 **버티컬(verticals, 분리된 지식 도메인)**이 있을 때 유용하다.

## 핵심 특성

- 라우터가 쿼리를 분해한다.
- 0개 이상의 특화 에이전트가 병렬로 호출된다.
- 결과가 일관된 응답으로 종합된다.

## 언제 사용하나

각각 자기 에이전트가 필요한 뚜렷한 버티컬이 있고, 여러 소스를 병렬로 조회해야 하며, 결과를 합쳐진 응답으로 종합하고 싶을 때 사용한다.

## 기본 구현

라우터가 쿼리를 분류해 적절한 에이전트로 보낸다. 단일 에이전트 라우팅엔 `Command`, 여러 에이전트로의 병렬 팬아웃엔 `Send`를 쓴다.

### 단일 에이전트

```python
from langgraph.types import Command

def classify_query(query: str) -> str:
    """Use LLM to classify query and determine the appropriate agent."""
    ...

def route_query(state: State) -> Command:
    """Route to the appropriate agent based on query classification."""
    active_agent = classify_query(state["query"])
    return Command(goto=active_agent)
```

### 여러 에이전트 (병렬)

```python
from typing import TypedDict
from langgraph.types import Send

class ClassificationResult(TypedDict):
    query: str
    agent: str

def classify_query(query: str) -> list[ClassificationResult]:
    """Use LLM to classify query and determine which agents to invoke."""
    ...

def route_query(state: State):
    """Route to relevant agents based on query classification."""
    classifications = classify_query(state["query"])
    # 선택된 에이전트로 병렬 팬아웃
    return [Send(c["agent"], {"query": c["query"]}) for c in classifications]
```

## 무상태 vs 상태 유지

- **무상태 라우터(Stateless)** : 각 요청을 독립적으로 처리한다. 호출 간 메모리가 없다.
- **상태 유지 라우터(Stateful)** : 요청 간 대화 이력을 유지한다.

**Router vs Subagents** : 둘 다 여러 에이전트로 작업을 디스패치할 수 있지만 라우팅 결정 방식이 다르다.

- **Router** : 입력을 분류해 에이전트로 디스패치하는 전용 라우팅 단계(보통 단일 LLM 호출 또는 규칙 기반). 라우터 자체는 보통 대화 이력을 유지하거나 멀티턴 조율을 하지 않는 전처리 단계다.
- **Subagents** : 메인 supervisor 에이전트가 진행 중인 대화의 일부로 어떤 서브에이전트를 호출할지 동적으로 결정한다. 메인이 컨텍스트를 유지하고 여러 턴에 걸쳐 여러 서브에이전트를 호출하며 복잡한 다단계 워크플로우를 조율한다.

명확한 입력 카테고리가 있고 결정론적/경량 분류를 원하면 **router**, 진화하는 컨텍스트에 따라 LLM이 다음 행동을 결정하는 유연한 대화 인식 조율이 필요하면 **supervisor**를 쓴다.

## 상태 유지 방식

### 도구 래퍼 (가장 단순)

무상태 라우터를 대화형 에이전트가 호출하는 도구로 감싼다. 대화형 에이전트가 메모리와 컨텍스트를 다루고 라우터는 무상태로 유지된다. 여러 병렬 에이전트에 걸친 대화 이력 관리의 복잡성을 피한다.

```python
@tool
def search_docs(query: str) -> str:
    """Search across multiple documentation sources."""
    result = workflow.invoke({"query": query})
    return result["final_answer"]

conversational_agent = create_agent(
    model,
    tools=[search_docs],
    prompt="You are a helpful assistant. Use search_docs to answer questions."
)
```

### 완전 영속

라우터 자체가 상태를 유지해야 하면 persistence로 메시지 이력을 저장한다. 에이전트로 라우팅할 때 상태에서 이전 메시지를 가져와 선택적으로 에이전트 컨텍스트에 포함한다 — 이것이 컨텍스트 엔지니어링의 레버다.

**주의** : 상태 유지 라우터는 커스텀 이력 관리가 필요하다. 라우터가 턴마다 에이전트를 바꾸면 에이전트들의 톤/프롬프트가 달라 사용자에게 매끄럽지 않게 느껴질 수 있다. 병렬 호출에서는 라우터 수준(입력과 종합 출력)에서 이력을 유지하고 라우팅 로직에 활용해야 한다. 멀티턴 대화에는 더 명확한 의미론을 제공하는 핸드오프 패턴이나 서브에이전트 패턴을 고려한다.
