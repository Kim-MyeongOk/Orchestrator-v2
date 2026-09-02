---
name: langchain-docs
description: Use this skill when building or debugging LangChain (OSS Python, v1.x) agents — anything involving create_agent, init_chat_model, @tool, messages (SystemMessage/HumanMessage/AIMessage/ToolMessage, AIMessageChunk), streaming (stream/astream, stream_modes, stream_events v3), structured output (response_format), middleware (built-in like SummarizationMiddleware/HumanInTheLoopMiddleware/PIIMiddleware or custom @wrap_model_call hooks), guardrails, runtime/context engineering, MCP integration (MultiServerMCPClient, langchain-mcp-adapters), multi-agent patterns (subagents/handoffs/skills/router/custom-workflow), retrieval/RAG, short-term memory (checkpointer) and long-term memory (Store). Trigger for token usage tracking, vLLM/OpenAI-compatible base_url config, tool calling, and LangGraph-backed agent loops. Covers langchain v1.x APIs that may differ from older AgentExecutor/LLMChain training knowledge.
license: MIT
compatibility: Requires Python 3.10+, langchain v1.x, and a tool-calling LLM. Built on LangGraph runtime.
metadata:
  author: icodebroker
  source: https://docs.langchain.com/oss/python/langchain
  version: "1.0"
  updated: "2026-06"
---

# LangChain (OSS Python) Skill

## Overview

LangChain은 `create_agent`라는 최소·고도설정형 에이전트 하니스를 제공한다. 모델, 도구, 프롬프트, 미들웨어로 필요한 만큼만 조합한다. 핵심 등식은 **Agent = Model + Harness**이며, 하니스는 모델 루프를 둘러싼 모든 것(프롬프트, 도구, 동작을 형성하는 미들웨어)이다.

이 스킬은 LangChain **v1.x** OSS Python API를 다룬다. 구버전의 `AgentExecutor`, `LLMChain`, `initialize_agent` 등과 다른 새 API(`create_agent`, 미들웨어, `stream_events` v3 등)를 사용하므로, 학습 데이터의 구버전 지식 대신 이 참조 파일을 신뢰한다.

**프레임워크 구분** :
- **LangChain (`create_agent`)** : 고도로 커스터마이징 가능한 최소 하니스. 미들웨어로 능력을 점진적으로 추가.
- **LangGraph** : 더 낮은 수준의 그래프 빌딩 API. LangChain 에이전트는 LangGraph 위에 구축된다 (durable execution, HITL, persistence).
- **Deep Agents** : LangChain 위의 배터리 포함형 하니스 (자동 컨텍스트 압축, 가상 파일시스템, 서브에이전트 스포닝). 별도 `deepagents` 스킬 참조.

## When to Use This Skill

다음 작업을 할 때 사용한다.

- `create_agent`로 에이전트를 만들거나 디버깅
- `init_chat_model` / 모델 설정, vLLM·OpenAI 호환 `base_url`, 토큰 사용량 추적
- `@tool` 정의, 도구 에러 처리, `ToolRuntime`로 state/context/store 접근
- 메시지 처리 (`AIMessageChunk` 누적, `content_blocks`, 멀티모달)
- 스트리밍 (`stream`/`astream`, `stream_modes`, `stream_events` v3)
- 구조화 출력 (`response_format`, ProviderStrategy/ToolStrategy)
- 미들웨어 (내장 또는 커스텀 `@wrap_model_call` 등 훅)
- 가드레일, 런타임/컨텍스트 엔지니어링
- MCP 통합 (`MultiServerMCPClient`)
- 멀티 에이전트 (subagents / handoffs / skills / router / custom workflow)
- 검색/RAG, 단기 메모리(checkpointer), 장기 메모리(Store)

## Quick Reference

### 설치
```bash
# uv add langchain
pip install -U langchain
# 프로바이더 패키지 (필요한 것만)
pip install -U "langchain[anthropic]"   # 또는 langchain-openai, langchain-google-genai 등
```

### 기본 패턴
```python
from langchain.agents import create_agent
from langchain.tools import tool

@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

agent = create_agent(
    model="claude-sonnet-4-6",          # 또는 "openai:gpt-5.5", "google_genai:gemini-3.5-flash"
    tools=[search],
    system_prompt="You are a helpful assistant.",
)

result = agent.invoke({"messages": [{"role": "user", "content": "Your task"}]})
print(result["messages"][-1].content)
```

### 모델 문자열 형식
`"provider:model"` 형식 또는 짧은 이름. 예 : `"openai:gpt-5.5"`, `"anthropic:claude-sonnet-4-6"`, `"google_genai:gemini-3.5-flash"`. 세밀한 제어는 `init_chat_model(...)`로 모델 객체를 만들어 전달.

## Reference Files

필요할 때 해당 참조 파일을 읽는다. 각 파일은 한국어로 distill한 내용과 코드 예제, 원문 URL을 담는다.

### 시작하기
- **`references/overview.md`** : LangChain 개요, create_agent, LangGraph·Deep Agents와의 차이
- **`references/install.md`** : 설치, 프로바이더 패키지, Python 요구사항
- **`references/quickstart.md`** : 첫 에이전트 만들기 단계별 가이드
- **`references/philosophy.md`** : 핵심 철학, 버전 히스토리
- **`references/changelog.md`** : 최신순 릴리스 변경사항 (langchain/langgraph/deepagents)

### 핵심 컴포넌트
- **`references/agents.md`** : create_agent 전체 — 정적/동적 모델·도구, ReAct, 시스템 프롬프트, 미들웨어 개관, ToolStrategy/ProviderStrategy
- **`references/models.md`** : init_chat_model, invoke/stream/batch, with_structured_output, 토큰 사용량(UsageMetadataCallbackHandler, stream_options include_usage), base_url(vLLM/OpenAI 호환), 프롬프트 캐싱, 레이트 리미팅, reasoning
- **`references/messages.md`** : SystemMessage/HumanMessage/AIMessage/ToolMessage, usage_metadata, AIMessageChunk 누적, content_blocks, 멀티모달, output_version=v1
- **`references/tools.md`** : @tool, 스키마, ToolRuntime(State/Context/Store/Stream Writer), Command 상태 갱신, ToolNode, 에러 처리
- **`references/short-term-memory.md`** : checkpointer, InMemorySaver/PostgresSaver, thread_id, 커스텀 AgentState, trim/delete/summarize, SummarizationMiddleware
- **`references/streaming.md`** : stream_modes(updates/messages/custom), v2 StreamPart, reasoning 토큰, 도구 호출 스트리밍, HITL·서브에이전트 스트리밍
- **`references/event-streaming.md`** : stream_events v3, run.messages/text/reasoning/tool_calls/output/usage, ChatModelStream 타입드 프로젝션
- **`references/structured-output.md`** : response_format, ProviderStrategy/ToolStrategy, Union 타입, handle_errors, 검증 예외

### 미들웨어
- **`references/middleware-overview.md`** : 목적, 에이전트 루프, 훅, StateGraph에서 에이전트를 서브그래프로 사용
- **`references/middleware-built-in.md`** : 내장 미들웨어 전체 (Summarization, HumanInTheLoop, ModelCallLimit/ToolCallLimit, ModelFallback, PII, TodoList, LLMToolSelector, ToolRetry/ModelRetry, ContextEditing, ShellTool, FilesystemMiddleware, SubAgentMiddleware 등)
- **`references/middleware-custom.md`** : 노드형 vs 래핑형 훅, ExtendedModelResponse+Command, 데코레이터 vs 클래스 기반, 실행 순서, jump_to/hook_config

### 고급 사용
- **`references/guardrails.md`** : 결정론적 vs 모델 기반, PIIMiddleware, before_agent/after_agent 커스텀 가드레일, 계층 결합
- **`references/runtime.md`** : Runtime 객체(Context/Store/Stream writer/Execution info/Server info), DI, context_schema, ToolRuntime
- **`references/context-engineering.md`** : 에이전트 실패 원인, transient vs persistent, 데이터 소스(Runtime Context/State/Store), 모델·도구·라이프사이클 컨텍스트, 요약
- **`references/mcp.md`** : langchain-mcp-adapters, MultiServerMCPClient, 전송(http/streamable-http/stdio/sse), 인증, stateful 세션, 도구 인터셉터, structured content, elicitation
- **`references/human-in-the-loop.md`** : HumanInTheLoopMiddleware, decision 유형(approve/edit/reject/respond), interrupt_on, checkpointer 필수, Command resume

### 멀티 에이전트
- **`references/multi-agent-overview.md`** : 5개 패턴 비교, 선택 기준, 성능 비교(모델 호출·토큰)
- **`references/multi-agent-subagents.md`** : supervisor 패턴, 도구로 서브에이전트 호출, 동기/비동기, 단일 디스패치 도구, 컨텍스트 엔지니어링
- **`references/multi-agent-handoffs.md`** : 상태 기반 전이, Command, 단일 에이전트+미들웨어 vs 다중 서브그래프, Command.PARENT
- **`references/multi-agent-skills.md`** : 프롬프트 주도 특화, 점진적 공개, 동적 도구 등록, 계층적 스킬
- **`references/multi-agent-router.md`** : 라우팅 분류, Command vs Send(병렬 팬아웃), 무상태 vs 상태 유지
- **`references/multi-agent-custom-workflow.md`** : LangGraph 커스텀 흐름, 노드 안에서 에이전트 호출, RAG 파이프라인 예제

### 검색 & 메모리
- **`references/retrieval.md`** : RAG, 지식 베이스, 검색 파이프라인, 2-Step/Agentic/Hybrid RAG 아키텍처
- **`references/long-term-memory.md`** : LangGraph Store, namespace/key, InMemoryStore/PostgresStore, 도구에서 읽기/쓰기, 벡터 인덱스

## Common Tasks

**"에이전트를 처음 만든다"**
→ `quickstart.md`, `agents.md`, `models.md`

**"토큰 사용량을 추적하고 싶다 / vLLM 서버에 붙인다"**
→ `models.md` (base_url, UsageMetadataCallbackHandler, stream_options)

**"실시간 스트리밍 출력이 필요하다"**
→ `streaming.md` (token-level), `event-streaming.md` (타입드 v3 이벤트)

**"대화 이력이 너무 길어진다"**
→ `short-term-memory.md` (trim/summarize), `middleware-built-in.md` (SummarizationMiddleware), `context-engineering.md`

**"세션을 넘어 사용자 정보를 기억하고 싶다"**
→ `long-term-memory.md` (Store), `runtime.md` (context_schema)

**"여러 전문 에이전트를 조율한다"**
→ `multi-agent-overview.md`로 패턴 선택 → 해당 패턴 파일

**"커스텀 동작을 훅으로 주입한다"**
→ `middleware-custom.md`, `middleware-overview.md`

**"MCP 서버의 도구를 쓰고 싶다"**
→ `mcp.md`

**"사람의 승인을 받아야 하는 작업이 있다"**
→ `human-in-the-loop.md`, `middleware-built-in.md` (HumanInTheLoopMiddleware)

**"지식 베이스 기반 RAG를 만든다"**
→ `retrieval.md`, `multi-agent-custom-workflow.md` (RAG 파이프라인 예제)

**"구조화된 JSON 출력이 필요하다"**
→ `structured-output.md`

## Architecture at a Glance

```python
create_agent(
    model,            # "provider:model" 문자열 또는 init_chat_model 객체
    tools,            # @tool 함수, LangChain 도구, dict
    system_prompt,    # 문자열 또는 SystemMessage (동적 프롬프트는 미들웨어)

    # 상태 & 메모리
    state_schema,     # 커스텀 AgentState (추가 상태 키)
    checkpointer,     # 단기 메모리 (InMemorySaver/PostgresSaver) + thread_id
    store,            # 장기 메모리 (InMemoryStore/PostgresStore) + namespace/key
    context_schema,   # 런타임 의존성 주입 (Runtime.context)

    # 동작 형성
    middleware,       # 내장/커스텀 훅 (모델·도구 호출 래핑, before/after)
    response_format,  # 구조화 출력 (ProviderStrategy/ToolStrategy)
)
```

## 프로젝트 코딩 컨벤션 주의 (icodebroker)

이 스킬로 **실제 코드를 작성할 때**는 사용자의 파이썬 코딩 지침을 따른다 (userPreferences). 핵심 :
- 타입 힌트는 `typing` 스타일(`Dict`/`List`/`Optional`), 내장 제네릭 금지
- 한 줄에 임포트 하나, 그룹별 `import` 키워드 컬럼 정렬
- 타입 어노테이션 콜론과 키워드 인자 `=` 양쪽 공백, 연속 대입·dict 콜론 정렬
- 클래스 하나당 파일 하나(snake_case), `__init__.py` 없음, src/common + src/app 레이아웃
- 주석은 한국어, docstring은 `@tool` 함수만(LLM이 읽는 한국어 한 줄)
- `async def` 메소드/함수명에 `_async` 접미사 (단 `__aenter__`/`__aexit__`/`main`/상속받은 함수 제외)
- `from __future__ import annotations` 금지, git 미사용

위 문서의 예제 코드는 LangChain 공식 스타일(PEP 8)이므로, 사용자 코드베이스에 통합할 때는 위 컨벤션으로 변환한다.

## Additional Resources

- 공식 문서 : https://docs.langchain.com/oss/python/langchain/overview
- 전체 문서 인덱스 : https://docs.langchain.com/llms.txt
- GitHub : https://github.com/langchain-ai/langchain
- LangChain Skills 저장소 : https://github.com/langchain-ai/langchain-skills
