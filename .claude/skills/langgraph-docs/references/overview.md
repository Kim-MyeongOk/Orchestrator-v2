# LangGraph Overview

원문 : https://docs.langchain.com/oss/python/langgraph/overview

## 핵심 개념

LangGraph는 **저수준 오케스트레이션 프레임워크이자 런타임**이다. 길게 실행되는(long-running)
상태 유지(stateful) 에이전트를 빌드·관리·배포한다. Klarna, Uber, J.P. Morgan 등에서 사용된다.

LangGraph는 매우 저수준이며 오로지 에이전트 **오케스트레이션**에 집중한다. 프롬프트나 아키텍처를
추상화하지 않는다. 더 높은 수준의 추상화를 원하면 LangChain의 `create_agent`(프리빌트 ReAct 루프)를
먼저 검토한다. LangChain 없이도 LangGraph만 단독으로 쓸 수 있다.

핵심 역량 : **durable execution**(지속 실행), **streaming**, **human-in-the-loop**, **persistence**(영속성).

## 제품 스택 위치

- **Deep Agents** : 에이전트 하니스 (계획, 서브에이전트, 파일시스템 도구, 컨텍스트 관리). LangGraph 위에 구축.
- **LangChain** (`create_agent`) : 에이전트 프레임워크 (모델/도구/에이전트 루프 추상화·통합).
- **LangGraph** : 오케스트레이션 런타임 (durable execution, streaming, HITL, persistence).
- **LangSmith** : 추적/평가/프롬프트/배포 플랫폼.

## 설치 + Hello World

```bash
pip install -U langgraph
# 또는 uv add langgraph
```

```python
from langgraph.graph import StateGraph, MessagesState, START, END

def mock_llm(state: MessagesState):
    return {"messages": [{"role": "ai", "content": "hello world"}]}

graph = StateGraph(MessagesState)
graph.add_node(mock_llm)
graph.add_edge(START, "mock_llm")
graph.add_edge("mock_llm", END)
graph = graph.compile()

graph.invoke({"messages": [{"role": "user", "content": "hi!"}]})
```

## 핵심 이점

- **Persistence** : 실패를 견디고 장시간 실행하며 중단 지점부터 재개.
- **Human-in-the-loop** : 임의 시점에 상태를 검사·수정.
- **Comprehensive memory** : 단기 작업 메모리 + 세션 간 장기 메모리.
- **Debugging (LangSmith)** : 실행 경로 시각화, 상태 전이 캡처, 런타임 메트릭.
- **Production-ready deployment** : 상태 유지·장시간 워크플로우를 위한 확장 가능 인프라.

## 영감

LangGraph는 Google **Pregel**과 Apache Beam에서 영감을 받았다. 공개 인터페이스는 NetworkX에서 영감.
LangChain Inc가 빌드했지만 LangChain 없이 사용 가능하다.

## LangSmith 추적

`LANGSMITH_TRACING=true`와 API 키를 설정하면 추적 시작. LangSmith Engine은 트레이스를 모니터링하고
이슈를 탐지해 수정안을 제안한다.

## 참고

전체 문서 인덱스 : https://docs.langchain.com/llms.txt
