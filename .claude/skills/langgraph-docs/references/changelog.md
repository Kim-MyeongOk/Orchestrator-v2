# Changelog (LangGraph 중심)

원문 : https://docs.langchain.com/oss/python/releases/changelog
RSS : https://docs.langchain.com/oss/python/releases/changelog/rss.xml

LangGraph 위주 최신순 변경사항. (langchain/deepagents 변경은 langchain 스킬 참조)

## langgraph v1.2.0 (2026-05-12)

노드 실행 제어 강화 + 신규 채널 타입 + content-block 중심 스트리밍 API(v3).

- **`DeltaChannel` (beta)** : 각 스텝의 증분(delta)만 저장하고 전체 누적값을 재직렬화하지 않는
  채널 타입. 장시간 스레드의 메시지 리스트처럼 커지는 채널에 유용. `snapshot_frequency=K`로
  K 스텝마다 전체 스냅샷을 써서 읽기 지연을 제한.
- **Per-node timeouts** : `add_node(timeout=)`로 단일 시도 시간 제한. `run_timeout`(하드
  월클럭), `idle_timeout`(진행 시 리셋), 또는 `TimeoutPolicy`. 초과 시 `NodeTimeoutError`를
  raise하고 해당 시도의 쓰기를 클리어 후 재시도 정책으로 핸드오프. **async 노드만**.
- **Node-level error handlers** : `add_node(error_handler=)`로 모든 재시도 소진 후 복구 함수 실행.
  타입드 `NodeError`를 받아 `Command`로 상태 갱신·다른 노드 라우팅. Saga/보상 패턴에 유용.
- **Graceful shutdown** : 현재 superstep 완료 후 협조적으로 중단하고 재개 가능 체크포인트 저장.
  `RunControl` 생성 후 `request_drain()` 호출 → `GraphDrained` raise, 같은 config로 재개 가능.
- **Event streaming v3 (beta)** : `stream_events(version="v3")`. content-block 중심 프로토콜.
  타입드 per-channel 프로젝션(`run.values`, `run.messages`, `run.lifecycle`, `run.subgraphs`).
  `run.messages`는 LLM 호출당 하나의 `ChatModelStream`(text/reasoning/tool calls/usage 서브프로젝션).
  v1/v2는 변경 없음. (timeouts·error handlers는 Python 전용)

## langgraph v1.1.0 (2026-03-10)

- **Type-safe streaming (`version="v2"`)** : `stream()`/`astream()`에 `version="v2"` → 모든 청크가
  `type`/`ns`/`data` 키를 가진 통일 `StreamPart`. 모드별 `TypedDict`는 `langgraph.types`에서 임포트.
- **Type-safe invoke (`version="v2"`)** : `invoke()`/`ainvoke()`에 `version="v2"` → `.value`와
  `.interrupts` 속성을 가진 `GraphOutput`.
- **Pydantic/dataclass coercion** : v2에서 `invoke()`와 values-mode 출력이 선언된 모델/dataclass로 자동 변환.
- **Time travel 버그 수정** : interrupt·subgraph 재생에서 stale `RESUME` 재사용 안 함. 서브그래프는
  부모의 과거 상태 체크포인트를 올바르게 복원.
- 완전 하위 호환. v2는 opt-in이며 `GraphOutput`은 dict 스타일 접근도 지원.

## v1.0.0 (2025-10-20)

langchain v1 / langgraph v1 정식 출시.
- langgraph 릴리스 노트 : https://docs.langchain.com/oss/python/releases/langgraph-v1
- langgraph 마이그레이션 : https://docs.langchain.com/oss/python/migrate/langgraph-v1

## 관련 deepagents/langchain 주요 변경 (참고)

- **deepagents v0.6.0** (2026-05-12) : `CodeInterpreterMiddleware`(QuickJS 런타임), stream_events v3.
- **langchain v1.3.0** (2026-05-12) : agents에 stream_events v3 지원.
- **deepagents v0.5.0** (2026-04-07) : async subagents, read_file 멀티모달(PDF/오디오/비디오), 백엔드 바이너리 지원.
- **langchain v1.2.0** (2025-12-15) : tool `extras` 속성(프로바이더별 도구 파라미터), response_format strict 스키마.
- **langchain v1.1.0** (2025-11-25) : model profiles(`.profile`), ModelRetryMiddleware, SystemMessage 직접 전달.
