---
name: langgraph-docs
description: Use this skill when building or debugging LangGraph (OSS Python, v1.x) applications — anything involving StateGraph, the Graph API (nodes/edges/State/reducers/add_messages/MessagesState), the Functional API (@entrypoint/@task/entrypoint.final), conditional edges, Send (map-reduce), Command (state update + routing), subgraphs, persistence (checkpointers — InMemorySaver/PostgresSaver, custom BaseCheckpointSaver), stores (BaseStore long-term memory), durable execution, fault tolerance (RetryPolicy/TimeoutPolicy/error_handler), streaming (stream_mode v2, stream_events v3, custom StreamTransformer/StreamChannel), interrupts/human-in-the-loop, time travel, recursion limits, the Pregel runtime and channels (LastValue/Topic/BinaryOperatorAggregate/DeltaChannel), backward compatibility, testing, LangSmith Studio/Deployment/Observability, and frontend streaming (useStream/useExtension/useChannel). Also covers choosing Graph vs Functional APIs, custom checkpointer/store backends, and Redis/PostgreSQL streaming fan-out.
license: MIT
compatibility: Requires Python 3.10+ (3.11+ for some async features), langgraph v1.x. The DeltaChannel and custom StreamTransformer/StreamChannel features require langgraph>=1.2; runtime.execution_info/server_info require langgraph>=1.1.5.
metadata:
  author: icodebroker
  source: https://docs.langchain.com/oss/python/langgraph
  version: "1.0"
  updated: "2026-06"
---

# LangGraph (OSS Python) Skill

## Overview

LangGraph는 에이전트·워크플로우를 **그래프**로 모델링하는 저수준 오케스트레이션 프레임워크다. 세 컴포넌트 — **State**(공유 데이터), **Nodes**(로직 함수), **Edges**(라우팅) — 를 조합하고, Google Pregel에서 영감받은 **message passing**으로 이산 **super-step** 단위 실행한다. 핵심 가치는 영속성(checkpointer), durable execution, human-in-the-loop, 스트리밍을 그래프 구조에 자연스럽게 녹이는 것이다.

이 스킬은 LangGraph **v1.x** OSS Python API를 다룬다. 두 가지 작성 방식이 있으며 **같은 Pregel 런타임을 공유**한다.
- **Graph API (`StateGraph`)** : 선언적. 노드·엣지·공유 상태로 시각적 그래프. 복잡한 분기·병렬·팀 협업에 적합.
- **Functional API (`@entrypoint`/`@task`)** : 명령형. 표준 Python 제어 흐름으로 기존 코드에 최소 변경. 선형 워크플로우·빠른 프로토타이핑에 적합.

**프레임워크 구분** :
- **LangGraph** : 이 스킬. 저수준 그래프 빌딩 API + Pregel 런타임.
- **LangChain (`create_agent`)** : LangGraph 위에 구축된 고수준 에이전트 하니스. 별도 `langchain` 스킬 참조.
- **Deep Agents** : LangChain 위의 배터리 포함형 하니스. 별도 `deepagents` 스킬 참조.

## When to Use This Skill

다음 작업을 할 때 사용한다.

- `StateGraph`로 그래프를 만들거나 디버깅 (노드·엣지·조건부 엣지·State·reducer)
- Graph API vs Functional API 선택
- `@entrypoint`/`@task`로 워크플로우 작성, `entrypoint.final`로 반환값·저장값 분리
- `Send`로 map-reduce, `Command`로 상태 갱신 + 라우팅 결합
- 서브그래프 구성 (노드로 추가 / 노드 안 호출, 영속성 모드)
- 영속성 (checkpointer, thread, time travel) 및 **커스텀 checkpointer/store 백엔드 구현**
- 장기 메모리 (`BaseStore`, 시맨틱 검색)
- durable execution, fault tolerance (`RetryPolicy`/`TimeoutPolicy`/`error_handler`)
- 스트리밍 (`stream_mode` v2) 및 **타입드 이벤트 스트리밍** (`stream_events` v3, 커스텀 `StreamTransformer`/`StreamChannel`)
- interrupt / human-in-the-loop
- 재귀 한계 (`RemainingSteps`), 그래프 마이그레이션·하위 호환성
- 그래프 테스트, 프로덕션 배포 (Studio/Deployment/Observability)
- 프론트엔드 스트리밍 (`useStream`/`useExtension`/`useChannel`)
- **Pregel 저수준 채널 설계** (`LastValue`/`Topic`/`BinaryOperatorAggregate`/`DeltaChannel`)

## Quick Reference

### 설치
```bash
# uv add langgraph
pip install -U langgraph
# 프로덕션 checkpointer (선택)
pip install -U langgraph-checkpoint-postgres   # PostgresSaver
```

### Graph API 기본 패턴
```python
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    foo: str

def node(state: State):
    return {"foo": "hi! " + state["foo"]}

builder = StateGraph(State)
builder.add_node("node", node)
builder.add_edge(START, "node")
builder.add_edge("node", END)
graph = builder.compile()   # 사용 전 반드시 컴파일

result = graph.invoke({"foo": "world"})
```

### Functional API 기본 패턴
```python
from langgraph.func import entrypoint, task
from langgraph.checkpoint.memory import InMemorySaver

@task
def write_essay(topic: str) -> str:
    return f"An essay about {topic}"

@entrypoint(checkpointer=InMemorySaver())
def workflow(topic: str) -> str:
    return write_essay(topic).result()

workflow.invoke("cats", config={"configurable": {"thread_id": "1"}})
```

### 영속성 (checkpointer + thread)
```python
graph = builder.compile(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "1"}}
graph.invoke({"foo": "a"}, config)   # 같은 thread_id로 대화·상태 누적
```

## Reference Files

필요할 때 해당 참조 파일을 읽는다. 각 파일은 한국어로 distill한 내용과 코드 예제, 원문 URL을 담는다.

### 시작하기
- **`references/overview.md`** : LangGraph 개요, State/Nodes/Edges, Graph vs Functional, LangChain·Deep Agents와의 관계
- **`references/install.md`** : 설치, checkpointer 패키지, Python 요구사항
- **`references/quickstart.md`** : 첫 그래프/에이전트 만들기 단계별
- **`references/local-server.md`** : 로컬 Agent Server(`langgraph dev`), langgraph.json
- **`references/thinking-in-langgraph.md`** : 그래프 사고법, 언제 그래프가 유용한가
- **`references/workflows-agents.md`** : 워크플로우 vs 에이전트, prompt chaining/routing/parallelization/orchestrator-worker/evaluator-optimizer 패턴
- **`references/changelog.md`** : 최신순 릴리스 변경사항

### 능력 (Capabilities)
- **`references/persistence.md`** : checkpointer 개념, thread, StateSnapshot, get_state/update_state, time travel 기초
- **`references/checkpointers.md`** : checkpointer 라이브러리(InMemory/Postgres/SQLite/Redis), **커스텀 BaseCheckpointSaver 전체 구현**(aput/aput_writes/aget_tuple/alist/adelete_thread, SQL 스키마, DeltaChannel 지원, conformance suite)
- **`references/stores.md`** : BaseStore 장기 메모리, namespace/key, 시맨틱 검색, **커스텀 BaseStore 구현**
- **`references/fault-tolerance.md`** : RetryPolicy, TimeoutPolicy(run/idle/heartbeat), error_handler/NodeError(Saga 보상 패턴)
- **`references/streaming.md`** : stream_mode v2, StreamPart, updates/values/messages/custom/debug 모드
- **`references/event-streaming.md`** : stream_events v3, 타입드 프로젝션, ProtocolEvent, 채널, **커스텀 StreamTransformer/StreamChannel/required_stream_modes**
- **`references/interrupts.md`** : interrupt(), Command(resume), HITL 패턴, 다중 interrupt, 검증 루프
- **`references/time-travel.md`** : get_state_history, 특정 체크포인트에서 재개, 상태 fork, as_node
- **`references/memory.md`** : 단기(checkpointer)·장기(Store) 메모리, 메시지 트림/요약
- **`references/subgraphs.md`** : 서브그래프(노드로 추가/노드 안 호출), 영속성 모드(per-invocation/per-thread/stateless), 네임스페이스 격리, 상태 검사

### API (Graph / Functional / Runtime)
- **`references/choosing-apis.md`** : Graph vs Functional 결정 가이드, 결합·마이그레이션
- **`references/graph-api.md`** : Graph API 전체 — StateGraph, State/schema/다중스키마, reducer/Overwrite, add_messages/MessagesState, Nodes(Runtime), START/END, 캐싱, Edges, Send, Command, graph migrations, runtime context, recursion limit/RemainingSteps
- **`references/use-graph-api.md`** : Graph API 실전 — private state, Pydantic state, retry/cache, execution_info/server_info, 시퀀스/분기/병렬/defer, 조건부 분기, map-reduce, 루프, async, Command(도구 안 사용), 시각화
- **`references/functional-api.md`** : Functional API 전체 — @entrypoint(주입 파라미터·previous·entrypoint.final), @task, 결정성, 멱등성, 흔한 함정
- **`references/use-functional-api.md`** : Functional API 실전 — 병렬, 그래프/다른 entrypoint 호출, 스트리밍, retry/timeout/cache, 에러 후 재개, HITL(도구 호출 검토), 체크포인트 관리, 챗봇
- **`references/pregel.md`** : Pregel 런타임 — actor/channel, Plan/Execution/Update, LastValue/Topic/BinaryOperatorAggregate/**DeltaChannel(bulk reducer·snapshot_frequency)**, 저수준 Pregel API

### 프로덕션
- **`references/application-structure.md`** : langgraph.json, 의존성, 그래프·환경변수 설정
- **`references/test.md`** : pytest 패턴, 개별 노드 테스트, 부분 실행(update_state+interrupt_after)
- **`references/backward-compatibility.md`** : 기술적/비즈니스 호환성, 비결정성(Functional), 진행 중 스레드 탐지, behavioral version 패턴
- **`references/studio.md`** : LangSmith Studio 로컬 셋업, langgraph dev, 핫 리로드
- **`references/ui.md`** : Agent Chat UI(Next.js), 로컬/배포 에이전트 연결
- **`references/deploy.md`** : LangSmith Cloud 배포, GitHub 연동, langgraph-sdk API
- **`references/observability.md`** : LangSmith 추적, 프로젝트/메타데이터/태그, 익명화(민감 데이터 마스킹)

### 프론트엔드
- **`references/frontend-overview.md`** : 프론트엔드 스트림 API·아키텍처, useStream, 런타임 개념→UX 매핑
- **`references/frontend-graph-execution.md`** : 노드별 카드, subgraphs 발견, useMessages 노드 범위 스트리밍, 진행바
- **`references/frontend-custom-stream-channels.md`** : 서버측 StreamTransformer→custom channel, useExtension(최신)/useChannel(버퍼), PII 레닥션 예제

## Common Tasks

**"그래프를 처음 만든다"**
→ `quickstart.md`, `graph-api.md`, `use-graph-api.md`

**"Graph API와 Functional API 중 뭘 쓸지 모르겠다"**
→ `choosing-apis.md`

**"기존 절차적 코드에 영속성·HITL만 더하고 싶다"**
→ `functional-api.md`, `use-functional-api.md`

**"커스텀 checkpointer/store 백엔드를 만든다 (asyncpg/Redis)"**
→ `checkpointers.md` (커스텀 BaseCheckpointSaver 전체 구현), `stores.md`

**"실시간 스트리밍 출력이 필요하다"**
→ `streaming.md` (v2), `event-streaming.md` (타입드 v3·커스텀 transformer)

**"Redis fan-out / 커스텀 스트림 채널을 설계한다"**
→ `event-streaming.md`, `frontend-custom-stream-channels.md`, `pregel.md` (DeltaChannel)

**"사람의 승인을 받아야 한다"**
→ `interrupts.md`, `use-functional-api.md` (도구 호출 검토)

**"분산 트랜잭션·재시도·보상(Saga)을 처리한다"**
→ `fault-tolerance.md` (RetryPolicy/error_handler), `subgraphs.md`

**"map-reduce / 병렬 팬아웃이 필요하다"**
→ `use-graph-api.md` (Send), `graph-api.md`

**"세션을 넘어 사용자 정보를 기억한다"**
→ `stores.md`, `memory.md`

**"체크포인트 크기가 스레드 길이에 선형 증가한다"**
→ `pregel.md` (DeltaChannel + snapshot_frequency)

**"프로덕션 코드를 무중단 업데이트한다"**
→ `backward-compatibility.md`

**"그래프를 테스트한다"**
→ `test.md`

**"프론트엔드에서 그래프 실행을 시각화한다"**
→ `frontend-overview.md`, `frontend-graph-execution.md`

## Architecture at a Glance

```python
# Graph API
builder = StateGraph(
    State,             # TypedDict/dataclass/Pydantic — schema + reducer
    context_schema,    # 런타임 의존성 주입 (Runtime.context)
    input_schema,      # 선택적 입력 스키마
    output_schema,     # 선택적 출력 스키마
)
builder.add_node("name", fn)              # fn(state, config, runtime)
builder.add_edge(START, "name")           # 정적 라우팅
builder.add_conditional_edges("a", route) # 동적 라우팅 (또는 노드에서 Command 반환)
graph = builder.compile(
    checkpointer,      # 영속성 (InMemorySaver/PostgresSaver) + thread_id
    store,             # 장기 메모리 (BaseStore)
    cache,             # 노드 캐싱 (InMemoryCache/SqliteCache)
)

# Functional API (같은 런타임)
@entrypoint(checkpointer=..., store=...)
def workflow(input, *, previous, store, writer, config):
    result = some_task(input).result()    # @task는 future 반환
    return entrypoint.final(value=..., save=...)
```

## 프로젝트 코딩 컨벤션 주의 (icodebroker)

이 스킬로 **실제 코드를 작성할 때**는 사용자의 파이썬 코딩 지침을 따른다 (userPreferences). 핵심 :
- 타입 힌트는 `typing` 스타일(`Dict`/`List`/`Optional`), 내장 제네릭 금지
- 한 줄에 임포트 하나, 그룹별 `import` 키워드 컬럼 정렬, 내부 모듈 절대 경로
- 타입 어노테이션 콜론과 키워드 인자 `=` 양쪽 공백, 연속 대입·dict 콜론 정렬, Enum 값 정렬
- 변수명 타입 접미사(`_list`/`_dictionary`/`_count`/`_id`), 축약어 금지(`maximum`/`minimum`)
- 클래스 하나당 파일 하나(snake_case), `__init__.py` 없음, src/common + src/app 레이아웃
- 주석은 한국어, docstring은 `@tool` 함수만(LLM이 읽는 한국어 한 줄)
- `async def` 메소드/함수명에 `_async` 접미사 (단 `__aenter__`/`__aexit__`/`main`/상속받은 함수 제외)
- `from __future__ import annotations` 금지, git 미사용

위 문서의 예제 코드는 LangGraph 공식 스타일(PEP 8 — `dict[str, Any]` 내장 제네릭, 다중 임포트 등)이므로, 사용자 코드베이스에 통합할 때는 위 컨벤션으로 변환한다. 특히 LangGraph 노드 함수·State TypedDict는 사용자의 명명·포매팅 규칙으로 다시 쓴다.

## Additional Resources

- 공식 문서 : https://docs.langchain.com/oss/python/langgraph/overview
- 전체 문서 인덱스 : https://docs.langchain.com/llms.txt
- API 레퍼런스 : https://reference.langchain.com/python/langgraph
- GitHub : https://github.com/langchain-ai/langgraph
