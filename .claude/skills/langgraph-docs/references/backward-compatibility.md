# Backward Compatibility

원문 : https://docs.langchain.com/oss/python/langgraph/backward-compatibility

LangGraph는 **최신 배포 그래프를 모든 스레드(새 스레드 + 체크포인트에서 재개하는 스레드)에 즉시
적용**한다. 워크플로우 엔진처럼 run을 시작 버전에 고정하지 않는다. 따라서 모든 변경이 기존 체크포인트에
대한 하위 호환 API 변경이 된다 — 버그 수정이 진행 중 대화에 바로 전파되는 장점이 있지만, 각 변경이
이전 버전에서 시작된 run과 어떻게 상호작용하는지 따져야 한다.

세 범주 (마주칠 순서대로) :
1. **기술적 호환성** : 새 코드가 기존 State에 대해 로드·실행되어야 함.
2. **비즈니스 호환성** : 기존 run은 코드가 바뀌어도 옛 로직을 계속 따라야 함.
3. **비결정성** : Functional API에만 해당.

## 1. 기술적 호환성

체크포인터가 영속한 데이터와 그래프 코드 사이의 계약. 흔한 파손 :
- **노드 이름 변경/제거** : 스레드가 그 노드에서 정지(interrupt)했거나 진입 예정인데 재개 시 저장된
  이름으로 노드를 못 찾아 실패. (재개 시작점은 정지한 노드의 처음)
- **State 키 이름 변경/제거** : 옛 체크포인트가 여전히 담고 있거나 하위 노드가 읽음.
- **State 필드 강화** : `Optional`→required, 타입 좁힘, 기본값 없는 required 필드 추가. 기존 체크포인트가
  새 스키마 불만족.

> **엣지 토폴로지는 체크포인트에 영속되지 않는다.** 존재하는 노드 간 엣지 추가/제거/재라우팅은 안전.
> interrupted 스레드를 깰 수 있는 토폴로지 변경은 **노드 이름 변경/제거뿐**이다.

**권장 패턴** :
- 새 state 필드는 `NotRequired`/`Optional[...] = None`으로 추가 → 옛 체크포인트도 검증 통과.
- 제거는 deprecation으로 : 아무 노드가 안 읽어도 최소 한 drain 사이클은 필드를 유지.
- rename은 **add-then-remove** : 새 것을 옛 것과 나란히 추가, deprecation 기간 dual-write/dual-route 후 제거.
- 노드 함수는 미지의 키에 관대하게 (`TypedDict`는 런타임에 여분 키 무시).
- 롤아웃 전 staging에서 time travel + `graph.get_state`로 기존 스레드를 새 코드에 대해 점검.

**진행 중 스레드 탐지** :
- LangSmith Deployment : thread search로 `status`(`idle`/`busy`/`interrupted`/`error`) 필터.
- 어디서든 : LangSmith 추적으로 어느 노드가 진입/종료되는지 모니터링.
- thread_id 있으면 : `graph.get_state(config)`(현재 정지 노드·pending interrupt), `get_state_history(config)`.

## 2. 비즈니스 호환성

기술적으로 유효하지만(모든 체크포인트 로드·노드 해석 OK) 새 그래프의 **의미**가 다를 때. 새 동작은
새 스레드엔 맞지만 옛 로직으로 시작한 스레드엔 소급 적용하면 안 된다.

**권장 패턴** : 스레드 시작 시 **behavioral version**을 상태에 기록하고 조건부 엣지로 분기.

```python
class State(TypedDict):
    request: str
    flow_version: NotRequired[int]
    response: NotRequired[str]

def intake(state: State) -> dict:
    return {"flow_version": state.get("flow_version", 2)}   # 새 스레드에 현재 버전 stamp

def after_triage(state: State) -> str:
    if state.get("flow_version", 1) >= 2:
        return "policy_check"
    return "respond"

builder.add_conditional_edges("triage", after_triage, ["policy_check", "respond"])
```

옛 스레드는 저장된 `flow_version`(또는 v1 기본)을 읽어 새 단계를 건너뛴다. 버전은 반드시 **스레드
시작 시**(버전 분기 이전) 설정해야 한다. 모든 v1 스레드 완료 후 플래그·조건부 엣지 제거.

## 3. 비결정성 (Functional API 전용)

Graph API는 노드 경계에서 재진입하므로 노드 코드가 처음부터 "재생"되지 않는다. 반면 Functional API는
재개 시 `@entrypoint` 본문을 처음부터 재생하며 캐시된 `@task` 결과로 완료 작업을 스킵한다. 파손 :
- 재개 지점 **이전**의 `@task`/`interrupt` 호출 추가·제거·재정렬 → 위치 기반 매칭이 어긋남.
- `@task` 밖의 비결정적 연산(`time.time()`, `random.random()`, 인라인 네트워크 호출) → 재생 시 다른 값.

안전한 옵션 : 진행 중 run을 drain 후 배포 / 새 로직을 새 `@task`로 감싸 독립 체크포인트 / `langgraph.json`에
새 그래프 이름으로 새 entrypoint 등록 후 새 스레드를 그쪽으로 라우팅.

> 기본 지원되는 그래프 토폴로지·상태 변경 요약은 graph-api의 "Graph migrations" 참조.
