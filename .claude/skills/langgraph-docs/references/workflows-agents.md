# Workflows and Agents

원문 : https://docs.langchain.com/oss/python/langgraph/workflows-agents

대표적인 워크플로우/에이전트 패턴 모음.

- **Workflow** : 사전에 정해진 코드 경로. 정해진 순서로 동작.
- **Agent** : 동적. 스스로 프로세스와 도구 사용을 정의.

구조화 출력 + 도구 호출을 지원하는 채팅 모델이면 무엇이든 사용 가능.

```python
from langchain_anthropic import ChatAnthropic
llm = ChatAnthropic(model="claude-sonnet-4-6")
```

## LLM 증강(augmentation)

```python
from pydantic import BaseModel, Field

class SearchQuery(BaseModel):
    search_query: str = Field(None, description="...")

structured_llm = llm.with_structured_output(SearchQuery)   # 구조화 출력
llm_with_tools = llm.bind_tools([multiply])                # 도구 바인딩
msg = llm_with_tools.invoke("What is 2 times 3?")
msg.tool_calls
```

## 1. Prompt chaining (프롬프트 체이닝)

각 LLM 호출이 이전 호출의 출력을 처리. 검증 가능한 작은 단계로 분해 가능한 작업에 사용
(문서 번역, 일관성 검증 등). 게이트 함수로 조건 분기.

```python
workflow = StateGraph(State)
workflow.add_node("generate_joke", generate_joke)
workflow.add_node("improve_joke", improve_joke)
workflow.add_node("polish_joke", polish_joke)
workflow.add_edge(START, "generate_joke")
workflow.add_conditional_edges("generate_joke", check_punchline, {"Fail": "improve_joke", "Pass": END})
workflow.add_edge("improve_joke", "polish_joke")
workflow.add_edge("polish_joke", END)
chain = workflow.compile()
```

## 2. Parallelization (병렬화)

여러 LLM이 동시에 작업. 독립 서브태스크를 동시 실행(속도↑)하거나 같은 작업을 여러 번
실행(신뢰도↑). START에서 여러 노드로 팬아웃 후 aggregator로 합친다.

```python
parallel_builder.add_edge(START, "call_llm_1")
parallel_builder.add_edge(START, "call_llm_2")
parallel_builder.add_edge(START, "call_llm_3")
parallel_builder.add_edge("call_llm_1", "aggregator")
parallel_builder.add_edge("call_llm_2", "aggregator")
parallel_builder.add_edge("call_llm_3", "aggregator")
```

## 3. Routing (라우팅)

입력을 분류해 컨텍스트별 작업으로 보낸다. 구조화 출력으로 라우팅 결정 후 조건부 엣지로 분기.

```python
class Route(BaseModel):
    step: Literal["poem", "story", "joke"]

router = llm.with_structured_output(Route)

def llm_call_router(state):
    decision = router.invoke([SystemMessage(content="Route ..."), HumanMessage(content=state["input"])])
    return {"decision": decision.step}

def route_decision(state):
    if state["decision"] == "story": return "llm_call_1"
    elif state["decision"] == "joke": return "llm_call_2"
    elif state["decision"] == "poem": return "llm_call_3"

router_builder.add_conditional_edges("llm_call_router", route_decision,
                                     {"llm_call_1": "llm_call_1", ...})
```

## 4. Orchestrator-worker (오케스트레이터-워커)

오케스트레이터가 작업을 서브태스크로 분해 → 워커에 위임 → 워커 출력을 종합. 서브태스크를
사전 정의할 수 없을 때(코드 작성, 여러 파일 수정 등) 유용. **`Send` API**로 워커 노드를 동적
생성하고 각자에 입력을 보낸다. 각 워커는 자체 상태를 갖고, 출력은 공유 상태 키에 병렬로 기록된다.

```python
from langgraph.types import Send

class State(TypedDict):
    sections: list[Section]
    completed_sections: Annotated[list, operator.add]   # 워커들이 병렬로 기록

def assign_workers(state):
    # Send()로 섹션마다 워커 동적 생성
    return [Send("llm_call", {"section": s}) for s in state["sections"]]

orchestrator_worker_builder.add_conditional_edges("orchestrator", assign_workers, ["llm_call"])
orchestrator_worker_builder.add_edge("llm_call", "synthesizer")
```

## 5. Evaluator-optimizer (평가자-최적화자)

한 LLM이 응답을 생성하고 다른 LLM(또는 인간)이 평가. 기준 미달이면 피드백을 주고 재생성하는
루프. 성공 기준이 명확하지만 반복이 필요할 때(번역 등) 사용.

```python
def route_joke(state):
    if state["funny_or_not"] == "funny": return "Accepted"
    elif state["funny_or_not"] == "not funny": return "Rejected + Feedback"

optimizer_builder.add_conditional_edges("llm_call_evaluator", route_joke,
                                        {"Accepted": END, "Rejected + Feedback": "llm_call_generator"})
```

## 6. Agents (에이전트)

도구를 사용해 행동하는 LLM. 연속 피드백 루프로 동작하며, 문제·해법이 예측 불가할 때 사용한다.
워크플로우보다 자율성이 높아 도구 선택과 문제 해결 방식을 스스로 결정한다(도구셋·가이드라인은 정의 가능).

quickstart의 ReAct 루프(`llm_call` ↔ `tool_node`, `should_continue` 조건부 엣지)가 기본 에이전트 패턴이다.
LangChain의 `create_agent`는 이 패턴의 프리빌트 버전이다.
