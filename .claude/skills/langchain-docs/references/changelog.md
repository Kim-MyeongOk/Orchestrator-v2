# Changelog

원문 : https://docs.langchain.com/oss/python/releases/changelog

Python 패키지(`langchain`, `deepagents`, `langgraph`, integrations)의 업데이트 로그. RSS 피드 제공.

## 주요 릴리스 (최신순)

### 2026-05-12
- **`deepagents` v0.6.0** : (실험적) `CodeInterpreterMiddleware` — 스코프드 QuickJS 런타임을 통한
  코드 실행 및 프로그램적 도구 호출. `stream_events`/`astream_events`에서 `version="v3"` 지원.
- **`langchain` v1.3.0** : agents의 `stream_events`/`astream_events`에서 `version="v3"` 지원 추가.
- **`langgraph` v1.2.0** :
  - `DeltaChannel` (beta) : 매 스텝마다 전체 누적값을 재직렬화하지 않고 증분 델타만 저장.
    장시간 스레드의 메시지 리스트처럼 커지는 채널에 유용. `snapshot_frequency=K`로 K 스텝마다
    전체 스냅샷 기록.
  - 노드별 타임아웃 : `add_node(timeout=...)`. `run_timeout`(하드 한도), `idle_timeout`(진행 시
    리셋), `TimeoutPolicy`. 한도 초과 시 `NodeTimeoutError`. 비동기 노드 전용.
  - 노드 레벨 에러 핸들러 : `add_node(error_handler=...)`. 모든 재시도 소진 후 복구 함수 실행.
    `NodeError`를 받고 `Command`를 반환해 상태 갱신/라우팅 가능 (Saga/보상 패턴에 유용).
  - Graceful shutdown : `RunControl.request_drain()`으로 현재 superstep 완료 후 협력적 중단,
    재개 가능한 checkpoint 저장. `GraphDrained` 발생.
  - 새 이벤트 스트리밍 API (beta, `version="v3"`) : content-block 중심 프로토콜, 채널별 타입드
    프로젝션(`run.values`, `run.messages`, `run.lifecycle`, `run.subgraphs`).

### 2026-04-07
- **`deepagents` v0.5.0** : 비동기 서브에이전트(non-blocking 백그라운드 작업), `read_file`의
  멀티모달 지원(PDF/오디오/비디오), backend 프로토콜 변경(바이너리 파일 지원), Anthropic 프롬프트
  캐싱 개선.

### 2026-03-10
- **`langgraph` v1.1.0** : 타입 안전 스트리밍(`version="v2"`, 통합 `StreamPart`), 타입 안전
  invoke(`GraphOutput` with `.value`/`.interrupts`), Pydantic/dataclass 강제 변환.

### 2026-02-10
- **`deepagents` v0.4.0** : pluggable 샌드박스 통합 패키지(`langchain-modal`, `langchain-daytona`,
  `langchain-runloop`), 대화 히스토리 요약 변경(모델 노드에서 `wrap_model_call`로 처리,
  `ContextOverflowError` 시 자동 트리거), `"openai:"` 접두사는 Responses API 기본 사용.

### 2025-12-15
- **`langchain` v1.2.0** : 도구의 `extras` 속성을 통한 프로바이더별 도구 파라미터 지원(Anthropic
  programmatic tool calling, tool search 등), `response_format`의 strict 스키마 준수
  (`ProviderStrategy`).

### 2025-11-25
- **`langchain` v1.1.0** : 모델 프로파일(`.profile` 속성, models.dev 기반), 요약 미들웨어 유연한
  트리거, 구조화 출력 `ProviderStrategy` 추론, `create_agent`에 `SystemMessage` 직접 전달(캐시
  제어/구조화 콘텐츠 블록), 모델 재시도 미들웨어(지수 백오프), 콘텐츠 모더레이션 미들웨어.

### 2025-10-20 — v1.0.0
- **`langchain` v1.0** + **`langgraph` v1.0** : 모든 chains/agents를 LangGraph 기반 단일 고수준
  에이전트 추상화로 대체. 표준 메시지 콘텐츠 포맷 도입. 구버전은 `langchain-classic` 패키지 사용.

전체 마이그레이션 가이드 : https://docs.langchain.com/oss/python/migrate/langchain-v1
