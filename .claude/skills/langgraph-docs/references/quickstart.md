# LangGraph Quickstart

원문 : https://docs.langchain.com/oss/python/langgraph/quickstart

계산기 에이전트를 **Graph API**와 **Functional API** 두 방식으로 만든다.
`ANTHROPIC_API_KEY` 환경변수 설정 필요.

- **Graph API** : 노드와 엣지의 그래프로 에이전트 정의
- **Functional API** : 단일 함수로 에이전트 정의

---

## Graph API 방식

### 1. 도구와 모델 정의

```python
from langchain.tools import tool
from langchain.chat_models import init_chat_model

model = init_chat_model("claude-sonnet-4-6", temperature=0)

@tool
def multiply(a: int, b: int) -> int:
    """Multiply `a` and `b`."""
    return a * b

@tool
def add(a: int, b: int) -> int:
    """Adds `a` and `b`."""
    return a + b

@tool
def divide(a: int, b: int) -> float:
    """Divide `a` and `b`."""
    return a / b

tools = [add, multiply, divide]
tools_by_name = {tool.name: tool for tool in tools}
model_with_tools = model.bind_tools(tools)
```

### 2. 상태 정의

상태는 에이전트 실행 전반에 걸쳐 영속된다. `Annotated` + `operator.add`로 새 메시지를
기존 리스트에 **덮어쓰지 않고 추가(append)** 한다 (reducer).

```python
from langchain.messages import AnyMessage
from typing_extensions import TypedDict, Annotated
import operator

class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    llm_calls: int
```

### 3. 모델 노드

```python
from langchain.messages import SystemMessage

def llm_call(state: dict):
    """LLM이 도구 호출 여부를 결정"""
    return {
        "messages": [
            model_with_tools.invoke(
                [SystemMessage(content="You are a helpful assistant ...")]
                + state["messages"]
            )
        ],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }
```

### 4. 도구 노드

```python
from langchain.messages import ToolMessage

def tool_node(state: dict):
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    return {"messages": result}
```

### 5. 종료 로직 (조건부 엣지)

```python
from typing import Literal
from langgraph.graph import StateGraph, START, END

def should_continue(state: MessagesState) -> Literal["tool_node", END]:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tool_node"
    return END
```

### 6. 빌드 + 컴파일

```python
agent_builder = StateGraph(MessagesState)
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges("llm_call", should_continue, ["tool_node", END])
agent_builder.add_edge("tool_node", "llm_call")

agent = agent_builder.compile()

from langchain.messages import HumanMessage
result = agent.invoke({"messages": [HumanMessage(content="Add 3 and 4.")]})
for m in result["messages"]:
    m.pretty_print()
```

그래프 시각화 : `agent.get_graph(xray=True).draw_mermaid_png()`

---

## Functional API 방식

`@task`로 작업 단위를, `@entrypoint`로 진입점을 정의한다. 노드/엣지 대신 일반 제어 흐름(루프,
조건문)을 단일 함수 안에 작성한다.

```python
from langgraph.graph import add_messages
from langgraph.func import entrypoint, task
from langchain_core.messages import BaseMessage
from langchain.messages import SystemMessage, HumanMessage, ToolCall

@task
def call_llm(messages: list[BaseMessage]):
    return model_with_tools.invoke(
        [SystemMessage(content="You are a helpful assistant ...")] + messages
    )

@task
def call_tool(tool_call: ToolCall):
    tool = tools_by_name[tool_call["name"]]
    return tool.invoke(tool_call)

@entrypoint()
def agent(messages: list[BaseMessage]):
    model_response = call_llm(messages).result()
    while True:
        if not model_response.tool_calls:
            break
        # 병렬 도구 실행 (future)
        tool_result_futures = [call_tool(tc) for tc in model_response.tool_calls]
        tool_results = [fut.result() for fut in tool_result_futures]
        messages = add_messages(messages, [model_response, *tool_results])
        model_response = call_llm(messages).result()
    messages = add_messages(messages, model_response)
    return messages

# 스트리밍 호출
for chunk in agent.stream([HumanMessage(content="Add 3 and 4.")], stream_mode="updates"):
    print(chunk)
```

## API 선택 가이드

- 노드/엣지로 명시적 그래프를 그리고 싶다 → **Graph API**
- 표준 파이썬 제어 흐름(루프/조건문)으로 한 함수에 쓰고 싶다 → **Functional API**
- 자세한 비교 → `choosing-apis.md`
