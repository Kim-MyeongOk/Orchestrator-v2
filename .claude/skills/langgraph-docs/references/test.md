# Test

원문 : https://docs.langchain.com/oss/python/langgraph/test

커스텀 구조 그래프의 단위 테스트 패턴(LangGraph 특화). `create_agent` 기반은 LangChain Test 참조.
`pip install -U pytest`.

## 기본 패턴

상태에 의존하므로, 각 테스트마다 그래프를 만들고 새 checkpointer로 컴파일한다.

```python
def create_graph() -> StateGraph:
    class MyState(TypedDict):
        my_key: str
    graph = StateGraph(MyState)
    graph.add_node("node1", lambda state: {"my_key": "hello from node1"})
    graph.add_node("node2", lambda state: {"my_key": "hello from node2"})
    graph.add_edge(START, "node1")
    graph.add_edge("node1", "node2")
    graph.add_edge("node2", END)
    return graph

def test_basic_agent_execution():
    compiled = create_graph().compile(checkpointer=MemorySaver())
    result = compiled.invoke({"my_key": "initial_value"},
                             config={"configurable": {"thread_id": "1"}})
    assert result["my_key"] == "hello from node2"
```

## 개별 노드/엣지 테스트

컴파일된 그래프는 `graph.nodes`로 각 노드 참조를 노출한다. 개별 노드를 테스트할 수 있다(이 경우
checkpointer는 우회됨).

```python
def test_individual_node_execution():
    compiled = create_graph().compile(checkpointer=MemorySaver())
    result = compiled.nodes["node1"].invoke({"my_key": "initial_value"})
    assert result["my_key"] == "hello from node1"
```

## 부분 실행 (partial execution)

큰 그래프에서 전체가 아닌 일부 경로만 테스트. (서브그래프로 재구조화하는 것이 의미상 맞을 수도
있지만) 구조 변경 없이 영속성으로 시뮬레이션 :

1. checkpointer로 컴파일.
2. `update_state(as_node=...)`로 시작하려는 노드 **직전** 노드 상태를 설정.
3. 같은 `thread_id`로 `invoke(None, interrupt_after=...)`로 멈출 노드까지 실행.

```python
def test_partial_execution_from_node2_to_node3():
    compiled = create_graph().compile(checkpointer=MemorySaver())
    compiled.update_state(
        config={"configurable": {"thread_id": "1"}},
        values={"my_key": "initial_value"},
        as_node="node1",          # node1이 생산한 것처럼 → node2부터 재개
    )
    result = compiled.invoke(
        None,                      # 재개
        config={"configurable": {"thread_id": "1"}},
        interrupt_after="node3",   # node3 후 멈춤(node4 미실행)
    )
    assert result["my_key"] == "hello from node3"
```
