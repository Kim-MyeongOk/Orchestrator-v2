# Middleware - Overview

원문 : https://docs.langchain.com/oss/python/langchain/middleware/overview

미들웨어는 에이전트 내부에서 일어나는 일을 더 세밀하게 제어한다. 용도 :
- 로깅/분석/디버깅으로 에이전트 동작 추적
- 프롬프트, 도구 선택, 출력 포맷 변환
- 재시도, 폴백, 조기 종료 로직 추가
- rate limit, 가드레일, PII 탐지 적용

`create_agent`에 전달한다.

```python
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware, HumanInTheLoopMiddleware

agent = create_agent(
    model="gpt-5.5",
    tools=[...],
    middleware=[SummarizationMiddleware(...), HumanInTheLoopMiddleware(...)],
)
```

## 에이전트 루프

핵심 루프 : 모델 호출 → 도구 선택/실행 → 더 이상 도구를 호출하지 않으면 종료. 미들웨어는 각
단계의 전후에 훅을 노출한다.

## LangGraph 워크플로우 내부에서 사용

미들웨어는 별도 런타임이 아니라 `create_agent`가 반환하는 컴파일된 LangGraph 안에서 실행되는
훅이다. 에이전트 전체(미들웨어 포함)를 더 큰 `StateGraph`에 노드/서브그래프로 넣을 수 있으며 모든
훅이 계속 실행된다. 표준 "끝까지 루프"보다 복잡한 토폴로지(입력 분류 후 여러 에이전트로 라우팅,
병렬 팬아웃, 결정적 단계와 에이전트 호출 결합)에 유용하다.

```python
from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.graph import START, StateGraph

email_agent = create_agent(
    model="claude-sonnet-4-6",
    tools=[read_email, send_email],
    middleware=[HumanInTheLoopMiddleware(interrupt_on={"send_email": True})],
)

graph = (
    StateGraph(AgentState)
    .add_node("classify", classify_node)
    .add_node("email_agent", email_agent)
    .add_edge(START, "classify")
    .add_conditional_edges("classify", route)
    .compile()
)
```

`HumanInTheLoopMiddleware`는 각 도구의 `.name`에 매칭한다(`@tool` 함수는 함수명이 키). HITL
인터럽트, 요약, PII 마스킹, 재시도, 커스텀 훅 모두 에이전트 노드와 함께 이동한다.

## 관련

- 프리빌트 미들웨어 : references/middleware-built-in.md
- 커스텀 미들웨어 : references/middleware-custom.md
- 프로바이더별 미들웨어 통합 : https://docs.langchain.com/oss/python/integrations/middleware/
