# Middleware - Prebuilt (Built-in)

원문 : https://docs.langchain.com/oss/python/langchain/middleware/built-in

LangChain과 Deep Agents가 제공하는 운영 준비된 프리빌트 미들웨어. 모두 `langchain.agents.middleware`
에서 임포트하고 `create_agent(middleware=[...])`로 전달한다.

## 프로바이더 무관 미들웨어 목록

| 미들웨어 | 설명 |
|---|---|
| Summarization | 토큰 한도 근접 시 대화 히스토리 자동 요약 |
| Human-in-the-loop | 도구 호출 승인을 위해 실행 일시정지 |
| Model call limit | 모델 호출 횟수 제한(비용 통제) |
| Tool call limit | 도구 호출 횟수 제한 |
| Model fallback | 주 모델 실패 시 대체 모델로 폴백 |
| PII detection | 개인식별정보 탐지/처리 |
| To-do list | 작업 계획/추적(`write_todos`) |
| LLM tool selector | 주 모델 호출 전 LLM으로 관련 도구 선택 |
| Tool retry | 실패한 도구 호출 지수 백오프 재시도 |
| Model retry | 실패한 모델 호출 지수 백오프 재시도 |
| LLM tool emulator | 테스트용 LLM 도구 실행 에뮬레이션 |
| Context editing | 토큰 한도 시 오래된 도구 사용 정리 |
| Shell tool | 명령 실행용 영속 셸 세션 노출 |
| File search | 파일시스템에 Glob/Grep 검색 도구 제공 |
| Filesystem | 컨텍스트/장기 메모리 저장용 파일시스템 제공 |
| Subagent | 서브에이전트 스폰 능력 추가 |

## SummarizationMiddleware

```python
from langchain.agents.middleware import SummarizationMiddleware

SummarizationMiddleware(
    model="gpt-5.4-mini",
    trigger=("tokens", 4000),      # 또는 ("fraction", 0.8), ("messages", N), 리스트(OR)
    keep=("messages", 20),         # 또는 ("fraction", 0.3), ("tokens", N)
)
```

`trigger` 조건 : `fraction`(컨텍스트 비율 0-1), `tokens`(절대 토큰 수), `messages`(메시지 수).
리스트로 주면 OR 로직. `fraction`은 `langchain>=1.1`의 모델 프로파일 데이터에 의존.

## HumanInTheLoopMiddleware

checkpointer 필요. 각 도구의 `.name`에 매칭.

```python
from langchain.agents.middleware import HumanInTheLoopMiddleware

HumanInTheLoopMiddleware(interrupt_on={
    "your_send_email_tool": {"allowed_decisions": ["approve", "edit", "reject"]},
    "your_read_email_tool": False,
})
```

## ModelCallLimitMiddleware

```python
ModelCallLimitMiddleware(thread_limit=10, run_limit=5, exit_behavior="end")
# thread_limit: 스레드 전체 누적, run_limit: 단일 호출, exit_behavior: "end"|"error"
# thread_limit엔 checkpointer 필요
```

## ToolCallLimitMiddleware

```python
ToolCallLimitMiddleware(thread_limit=20, run_limit=10)             # 전역
ToolCallLimitMiddleware(tool_name="search", thread_limit=5, run_limit=3)  # 도구별
# exit_behavior: "continue"(기본, 초과 호출 차단+에러 메시지) | "error" | "end"(단일 도구만)
```

## ModelFallbackMiddleware

```python
ModelFallbackMiddleware("gpt-5.4-mini", "claude-3-5-sonnet-20241022")
# 주 모델 실패 시 순서대로 폴백
```

## PIIMiddleware

```python
from langchain.agents.middleware import PIIMiddleware

PIIMiddleware("email", strategy="redact", apply_to_input=True)
PIIMiddleware("credit_card", strategy="mask", apply_to_input=True)
PIIMiddleware("api_key", detector=r"sk-[a-zA-Z0-9]{32}", strategy="block")  # 커스텀 정규식
```

- `pii_type` : 내장(`email`, `credit_card`, `ip`, `mac_address`, `url`) 또는 커스텀.
- `strategy` : `block`(예외), `redact`(`[REDACTED_TYPE]`), `mask`(부분 마스킹), `hash`(결정적 해시).
- `detector` : 정규식 문자열/컴파일된 패턴/커스텀 함수(`text`/`start`/`end` 키 dict 리스트 반환).
- `apply_to_input`(기본 True), `apply_to_output`(기본 False), `apply_to_tool_results`(기본 False).

## TodoListMiddleware

```python
TodoListMiddleware()  # write_todos 도구 + 계획 가이드 시스템 프롬프트 자동 제공
```

## LLMToolSelectorMiddleware

도구가 많을 때(10+) 주 모델 호출 전 관련 도구만 선택. 구조화 출력 사용.

```python
LLMToolSelectorMiddleware(model="gpt-5.4-mini", max_tools=3, always_include=["search"])
```

## ToolRetryMiddleware / ModelRetryMiddleware

```python
ToolRetryMiddleware(
    max_retries=3,           # 기본 2
    backoff_factor=2.0,      # 지수 백오프 배수, 0.0이면 상수
    initial_delay=1.0,
    max_delay=60.0,
    jitter=True,             # ±25% 랜덤
    tools=["api_tool"],      # None이면 모든 도구
    retry_on=(ConnectionError, TimeoutError),  # 또는 callable
    on_failure="return_message",  # "raise" | callable (Tool은 return_message/raise/continue)
)

ModelRetryMiddleware(max_retries=3, on_failure="continue")  # continue: 에러 AIMessage 반환
```

## LLMToolEmulator (테스트용)

```python
LLMToolEmulator()                          # 모든 도구 에뮬레이션
LLMToolEmulator(tools=["get_weather"])     # 특정 도구만
LLMToolEmulator(model="claude-sonnet-4-6") # 에뮬레이션용 모델 지정
```

## ContextEditingMiddleware / ClearToolUsesEdit

토큰 한도 시 오래된 도구 출력을 정리(최근 N개 보존).

```python
from langchain.agents.middleware import ContextEditingMiddleware, ClearToolUsesEdit

ContextEditingMiddleware(edits=[
    ClearToolUsesEdit(
        trigger=100000,        # 트리거 토큰 수
        keep=3,                # 보존할 최근 도구 결과 수
        clear_tool_inputs=False,
        exclude_tools=[],
        placeholder="[cleared]",
    ),
])
```

## ShellToolMiddleware

영속 셸 세션 노출. 실행 정책으로 보안 수준 결정. (현재 인터럽트/HITL과 미호환)

```python
from langchain.agents.middleware import (
    ShellToolMiddleware, HostExecutionPolicy, DockerExecutionPolicy)

ShellToolMiddleware(
    workspace_root="/workspace",
    execution_policy=HostExecutionPolicy(),  # 또는 DockerExecutionPolicy, CodexSandboxExecutionPolicy
    startup_commands=[...], redaction_rules=[...],
)
```

정책 : `HostExecutionPolicy`(전체 호스트 접근, 기본), `DockerExecutionPolicy`(실행마다 별도 도커
컨테이너), `CodexSandboxExecutionPolicy`(Codex CLI 샌드박스).

## FilesystemFileSearchMiddleware

```python
FilesystemFileSearchMiddleware(root_path="/workspace", use_ripgrep=True, max_file_size_mb=10)
# glob_search(파일 패턴 매칭), grep_search(정규식 콘텐츠 검색) 도구 추가
```

## FilesystemMiddleware (Deep Agents)

`ls`, `read_file`, `write_file`, `edit_file` 4개 도구 제공. `create_deep_agent`에 기본 포함.

```python
from deepagents.middleware import FilesystemMiddleware
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

FilesystemMiddleware(
    backend=CompositeBackend(
        default=StateBackend(),
        routes={"/memories/": StoreBackend()},  # /memories/ 경로는 영속 저장
    ),
)
```

기본은 그래프 상태의 로컬 파일시스템. `CompositeBackend`로 특정 경로(`/memories/`)를
`StoreBackend`에 라우팅하면 스레드 간 영속 저장.

## SubAgentMiddleware (Deep Agents)

`task` 도구를 통해 서브에이전트를 제공. 컨텍스트 격리로 주(supervisor) 에이전트의 컨텍스트 윈도우를
깨끗하게 유지.

```python
from deepagents.middleware.subagents import SubAgentMiddleware

SubAgentMiddleware(
    default_model="claude-sonnet-4-6",
    default_tools=[],
    subagents=[{
        "name": "weather",
        "description": "This subagent can get weather in cities.",
        "system_prompt": "Use the get_weather tool...",
        "tools": [get_weather],
        "model": "gpt-5.4",       # 선택
        "middleware": [],          # 선택
    }],
)
```

서브에이전트는 name/description/system_prompt/tools로 정의. 커스텀 model/middleware 가능. 직접 만든
LangGraph 그래프를 `CompiledSubAgent`로 래핑해 제공도 가능. 주 에이전트는 항상 `general-purpose`
서브에이전트에 접근 가능(컨텍스트 격리 목적).

## 프로바이더별 미들웨어

- Anthropic : 프롬프트 캐싱, bash 도구, text editor, memory, file search.
- AWS : Bedrock 프롬프트 캐싱.
- OpenAI : 콘텐츠 모더레이션.
