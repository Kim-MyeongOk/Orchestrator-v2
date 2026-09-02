# Context engineering in agents

원문 : https://docs.langchain.com/oss/python/langchain/context-engineering

에이전트가 실패하는 주된 이유는 (1) LLM 역량 부족, 또는 (2) "올바른" 컨텍스트가 전달되지 않음.
대부분 (2)가 원인이다. **컨텍스트 엔지니어링**은 LLM이 작업을 완수할 수 있도록 올바른 정보와
도구를 올바른 형식으로 제공하는 것이다. LangChain 미들웨어가 이를 실용적으로 만드는 메커니즘이다.

## 에이전트 루프와 제어 가능한 것

루프 : 모델 호출 → 도구 실행 → (반복) → 종료.

| 컨텍스트 유형 | 제어 대상 | 일시/영속 |
|---|---|---|
| Model Context | 모델 호출에 들어가는 것(지시/메시지 히스토리/도구/응답 형식) | Transient |
| Tool Context | 도구가 접근/생성하는 것(state/store/runtime 읽기·쓰기) | Persistent |
| Life-cycle Context | 모델/도구 호출 사이에 일어나는 것(요약/가드레일/로깅) | Persistent |

- **Transient(일시)** : 단일 호출에 LLM이 보는 것. state 저장 내용을 바꾸지 않고 메시지/도구/
  프롬프트 수정.
- **Persistent(영속)** : 턴 간 state에 저장되는 것. life-cycle 훅과 도구 쓰기가 영구 수정.

### 데이터 소스

| 소스 | 별칭 | 범위 | 예 |
|---|---|---|---|
| Runtime Context | 정적 설정 | 대화 범위 | user ID, API 키, DB 연결, 권한, 환경 설정 |
| State | 단기 메모리 | 대화 범위 | 현재 메시지, 업로드 파일, 인증 상태, 도구 결과 |
| Store | 장기 메모리 | 대화 간 | 사용자 선호, 추출된 인사이트, 메모리, 이력 |

## Model Context

각 모델 호출에 들어가는 것(시스템 프롬프트, 메시지, 도구, 모델, 응답 형식)을 제어. 모두 state/
store/runtime context에서 끌어올 수 있다.

### System Prompt — `@dynamic_prompt`

```python
@dynamic_prompt
def state_aware_prompt(request: ModelRequest) -> str:
    message_count = len(request.messages)  # request.state["messages"]의 단축
    base = "You are a helpful assistant."
    if message_count > 10:
        base += "\nThis is a long conversation - be extra concise."
    return base
```

store(`request.runtime.store`)나 runtime context(`request.runtime.context`)에서도 끌어올 수 있다.

### Messages — `wrap_model_call`로 주입

```python
@wrap_model_call
def inject_file_context(request: ModelRequest, handler) -> ModelResponse:
    uploaded_files = request.state.get("uploaded_files", [])
    if uploaded_files:
        file_context = "..."
        messages = [*request.messages, {"role": "user", "content": file_context}]
        request = request.override(messages=messages)
    return handler(request)
```

모델은 마지막 메시지에 더 주의하므로 컨텍스트를 끝에 추가하는 패턴이 흔하다. 위는 **일시적**
업데이트(state 미변경). **영속적**이려면 `ExtendedModelResponse`+`Command` 반환 또는
`before_model`/`after_model` 같은 life-cycle 훅 사용.

### Tools — 정의와 선택

정의 : 명확한 이름/설명/인자명/인자 설명이 모델 추론을 안내한다. `@tool(parse_docstring=True)`로
docstring을 파싱.

선택 : 너무 많으면 컨텍스트 과부하/오류 증가, 너무 적으면 능력 제한. `wrap_model_call`에서
`request.override(tools=...)`로 인증 상태/권한/단계에 따라 동적 필터링.

### Model — 동적 선택

```python
@wrap_model_call
def state_based_model(request: ModelRequest, handler) -> ModelResponse:
    message_count = len(request.messages)
    model = large_model if message_count > 20 else efficient_model
    return handler(request.override(model=model))
```

대화 길이/사용자 선호/비용 티어에 따라 모델 교체.

### Response format — 동적 선택

```python
@wrap_model_call
def state_based_output(request: ModelRequest, handler) -> ModelResponse:
    if len(request.messages) < 3:
        request = request.override(response_format=SimpleResponse)
    else:
        request = request.override(response_format=DetailedResponse)
    return handler(request)
```

## Tool Context

도구는 컨텍스트를 읽고 쓴다.

### 읽기 (Reads)

`runtime.state`(세션 정보), `runtime.store`(영속 선호), `runtime.context`(API 키/user ID/DB 연결).

```python
@tool
def fetch_user_data(query: str, runtime: ToolRuntime[Context]) -> str:
    """Fetch data using Runtime Context configuration."""
    api_key = runtime.context.api_key
    db_connection = runtime.context.db_connection
    ...
```

### 쓰기 (Writes)

State : `Command(update={...})` 반환. Store : `runtime.store.put(...)`.

```python
@tool
def authenticate_user(password: str, runtime: ToolRuntime) -> Command:
    """Authenticate user and update State."""
    return Command(update={"authenticated": password == "correct"})

@tool
def save_preference(key: str, value: str, runtime: ToolRuntime[Context]) -> str:
    """Save user preference to Store."""
    prefs = (runtime.store.get(("preferences",), runtime.context.user_id) or {}).value or {}
    prefs[key] = value
    runtime.store.put(("preferences",), runtime.context.user_id, prefs)
    return f"Saved: {key}={value}"
```

## Life-cycle Context

핵심 단계 **사이**에 일어나는 일(요약/가드레일/로깅 등 교차 관심사). 미들웨어로 (1) 컨텍스트
업데이트(state/store 영속 변경), (2) 라이프사이클 점프(조건에 따라 단계 이동) 가능.

### 예: 요약 (영속)

일시적 메시지 트리밍과 달리, 요약은 state를 **영속적으로** 갱신해 오래된 메시지를 요약으로 영구
교체한다.

```python
from langchain.agents.middleware import SummarizationMiddleware

SummarizationMiddleware(model="gpt-4.1-mini", trigger={"tokens": 4000}, keep={"messages": 20})
```

## 베스트 프랙티스

1. 단순하게 시작(정적 프롬프트/도구), 필요할 때만 동적 추가. 2. 점진적 테스트(한 번에 하나씩).
3. 성능 모니터링(모델 호출/토큰/지연). 4. 프리빌트 미들웨어 활용. 5. 컨텍스트 전략 문서화.
6. 일시 vs 영속 구분(모델 컨텍스트는 일시적, life-cycle은 state에 영속).
