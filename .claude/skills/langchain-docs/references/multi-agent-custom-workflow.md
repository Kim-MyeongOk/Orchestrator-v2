# 커스텀 워크플로우 (Custom Workflow)

원문 : https://docs.langchain.com/oss/python/langchain/multi-agent/custom-workflow

커스텀 워크플로우 아키텍처에서는 LangGraph로 자신만의 맞춤형 실행 흐름을 정의한다. 그래프 구조(순차 단계, 조건 분기, 루프, 병렬 실행)를 완전히 제어한다.

## 핵심 특성

- 그래프 구조에 대한 완전한 제어
- 결정론적 로직과 에이전트 동작 혼합
- 순차 단계, 조건 분기, 루프, 병렬 실행 지원
- 다른 패턴을 워크플로우의 노드로 임베드

## 언제 사용하나

표준 패턴(subagents, skills 등)이 요구사항에 맞지 않을 때, 결정론적 로직과 에이전트 동작을 섞어야 할 때, 복잡한 라우팅이나 다단계 처리가 필요할 때 사용한다.

워크플로우의 각 노드는 단순 함수, LLM 호출, 또는 도구를 가진 완전한 에이전트일 수 있다. 다른 아키텍처를 커스텀 워크플로우 안에 조합할 수도 있다 — 예를 들어 멀티 에이전트 시스템을 단일 노드로 임베드.

## 기본 구현

핵심 통찰은 어떤 LangGraph 노드 안에서든 LangChain 에이전트를 직접 호출할 수 있다는 것이다. 커스텀 워크플로우의 유연성과 사전 구축 에이전트의 편의성을 결합한다.

```python
from langchain.agents import create_agent
from langgraph.graph import StateGraph, START, END

agent = create_agent(model="openai:gpt-5.5", tools=[...])

def agent_node(state: State) -> dict:
    """A LangGraph node that invokes a LangChain agent."""
    result = agent.invoke({"messages": [{"role": "user", "content": state["query"]}]})
    return {"answer": result["messages"][-1].content}

workflow = (
    StateGraph(State)
    .add_node("agent", agent_node)
    .add_edge(START, "agent")
    .add_edge("agent", END)
    .compile()
)
```

## 예제 : RAG 파이프라인

흔한 사례는 retrieval과 에이전트를 결합하는 것이다. 세 가지 노드 유형을 보여준다.

- **모델 노드 (Rewrite)** : structured output으로 더 나은 검색을 위해 사용자 쿼리를 재작성한다.
- **결정론적 노드 (Retrieve)** : 벡터 유사도 검색을 수행한다 — LLM 미관여.
- **에이전트 노드 (Agent)** : 검색된 컨텍스트를 추론하고 도구로 추가 정보를 가져온다.

LangGraph state로 워크플로우 단계 간 정보를 전달한다. 각 부분이 구조화된 필드를 읽고 갱신하여 노드 간 데이터/컨텍스트 공유가 쉽다.

```python
from typing import TypedDict
from pydantic import BaseModel
from langgraph.graph import StateGraph, START, END
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.vectorstores import InMemoryVectorStore

class State(TypedDict):
    question: str
    rewritten_query: str
    documents: list[str]
    answer: str

embeddings = OpenAIEmbeddings()
vector_store = InMemoryVectorStore(embeddings)
vector_store.add_texts([...])  # 로스터, 경기 결과, 선수 통계 등
retriever = vector_store.as_retriever(search_kwargs={"k": 5})

@tool
def get_latest_news(query: str) -> str:
    """Get the latest WNBA news and updates."""
    return "Latest: ..."

agent = create_agent(model="openai:gpt-5.5", tools=[get_latest_news])
model = ChatOpenAI(model="gpt-5.5")

class RewrittenQuery(BaseModel):
    query: str

def rewrite_query(state: State) -> dict:
    response = model.with_structured_output(RewrittenQuery).invoke([
        {"role": "system", "content": "Rewrite this query..."},
        {"role": "user", "content": state["question"]}
    ])
    return {"rewritten_query": response.query}

def retrieve(state: State) -> dict:
    docs = retriever.invoke(state["rewritten_query"])
    return {"documents": [doc.page_content for doc in docs]}

def call_agent(state: State) -> dict:
    context = "\n\n".join(state["documents"])
    prompt = f"Context:\n{context}\n\nQuestion: {state['question']}"
    response = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
    return {"answer": response["messages"][-1].content_blocks}

workflow = (
    StateGraph(State)
    .add_node("rewrite", rewrite_query)
    .add_node("retrieve", retrieve)
    .add_node("agent", call_agent)
    .add_edge(START, "rewrite")
    .add_edge("rewrite", "retrieve")
    .add_edge("retrieve", "agent")
    .add_edge("agent", END)
    .compile()
)

result = workflow.invoke({"question": "Who won the 2024 WNBA Championship?"})
```

참고 : router 패턴 자체가 커스텀 워크플로우의 한 예다.
