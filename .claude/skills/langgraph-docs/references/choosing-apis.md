# Choosing between Graph and Functional APIs

원문 : https://docs.langchain.com/oss/python/langgraph/choosing-apis

LangGraph는 에이전트 워크플로우를 만드는 두 API를 제공한다 : **Graph API**와 **Functional API**.
둘은 **같은 런타임을 공유**하고 한 앱에서 함께 쓸 수 있지만, 다른 사용 사례·개발 선호를 위해 설계됐다.

## 빠른 결정 가이드

**Graph API**를 쓸 때 :
- 디버깅·문서화를 위한 복잡한 워크플로우 시각화
- 여러 노드에 공유되는 데이터의 명시적 상태 관리
- 여러 결정 지점의 조건부 분기
- 나중에 병합하는 병렬 실행 경로
- 시각적 표현이 이해를 돕는 팀 협업

**Functional API**를 쓸 때 :
- 기존 절차적 코드에 최소 변경
- 표준 제어 흐름(if/else, 루프, 함수 호출)
- 명시적 상태 관리 없는 함수 범위 상태
- 보일러플레이트 적은 빠른 프로토타이핑
- 단순 분기의 선형 워크플로우

## Graph API 사용 시점

선언적 접근 — 노드·엣지·공유 상태로 시각적 그래프 구조.

```python
# 1. 복잡한 결정 트리·분기 — 분기를 명시적·시각화 가능하게
def should_continue(state):
    if state["retry_count"] > 3:
        return "end"
    elif state["current_tool"] == "search":
        return "process_search"
    else:
        return "call_llm"

workflow.add_conditional_edges("call_llm", should_continue)

# 2. 여러 컴포넌트 간 상태 관리 — 노드들이 공유 상태 read/write
# 3. 동기화 있는 병렬 처리 — START에서 여러 노드로 fan-out, combine 노드가 모두 대기
workflow.add_edge(START, "fetch_news")
workflow.add_edge(START, "fetch_weather")
workflow.add_edge("fetch_news", "combine_data")
workflow.add_edge("fetch_weather", "combine_data")

# 4. 팀 개발·문서화 — 각자 다른 노드 담당
```

## Functional API 사용 시점

명령형 접근 — LangGraph 기능을 표준 절차적 코드에 통합.

```python
from langgraph.func import entrypoint, task

# 1. 기존 절차적 코드 — 최소 리팩토링
@task
def process_user_input(user_input: str) -> dict:
    return {"processed": user_input.lower().strip()}

@entrypoint(checkpointer=checkpointer)
def workflow(user_input: str) -> str:
    processed = process_user_input(user_input).result()
    if "urgent" in processed["processed"]:
        response = handle_urgent_request(processed).result()
    else:
        response = handle_normal_request(processed).result()
    return response

# 2. 단순 로직의 선형 워크플로우 (interrupt로 HITL 체크포인트)
# 3. 빠른 프로토타이핑 — 상태 스키마 불필요
# 4. 함수 범위 상태 관리 — 넓게 공유 불필요
```

## 두 API 결합

```python
# Graph API로 복잡한 멀티 에이전트 조정
coordination_graph = StateGraph(CoordinationState)

# Functional API로 단순 데이터 처리
@entrypoint()
def data_processor(raw_data: dict) -> dict:
    cleaned = clean_data(raw_data).result()
    return transform_data(cleaned).result()

# 그래프 노드 안에서 functional 결과 사용
def orchestrator_node(state):
    processed_data = data_processor.invoke(state["raw_data"])
    return {"processed_data": processed_data}
```

## 마이그레이션

- **Functional → Graph** : functional 워크플로우가 복잡해지면 노드·조건부 엣지로 전환.
- **Graph → Functional** : 그래프가 단순 선형 프로세스에 과도하면 `@entrypoint`로 단순화.

## 요약

두 API 모두 같은 핵심 기능(영속성, 스트리밍, HITL, 메모리)을 제공하되 다른 패러다임으로 패키징한다.
구조의 명시적 제어·복잡한 분기·병렬·팀 협업이 필요하면 Graph API, 기존 코드에 최소 변경·단순 선형·
빠른 프로토타이핑이면 Functional API.
