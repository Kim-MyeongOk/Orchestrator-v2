# Time Travel

원문 : https://docs.langchain.com/oss/python/langgraph/use-time-travel

체크포인트를 통한 시간 여행 :
- **Replay** : 이전 체크포인트에서 재시도.
- **Fork** : 이전 체크포인트에서 상태를 수정해 분기, 대안 경로 탐색.

둘 다 이전 체크포인트에서 재개한다. 체크포인트 **이전** 노드는 재실행 안 함(결과 저장됨).
**이후** 노드는 재실행(LLM 호출·API·interrupt 포함 — 다른 결과가 나올 수 있음).

## Replay

이전 체크포인트의 config로 그래프를 호출. 캐시 읽기가 아니라 **재실행**이다. 최종 체크포인트
(`next` 없음)에서 replay는 no-op.

```python
# 1. 실행
config = {"configurable": {"thread_id": str(uuid7())}}
result = graph.invoke({}, config)

# 2. 이력에서 체크포인트 찾기 (역순)
history = list(graph.get_state_history(config))
before_joke = next(s for s in history if s.next == ("write_joke",))

# 3. 특정 체크포인트에서 replay
replay_result = graph.invoke(None, before_joke.config)
# write_joke 재실행, generate_topic은 안 함
```

## Fork

과거 체크포인트에서 상태를 수정해 새 분기 생성. `update_state`로 fork를 만들고 `None`으로 재개.
`update_state`는 스레드를 롤백하지 **않는다** — 새 체크포인트로 분기하며 원본 이력은 그대로 유지.

```python
history = list(graph.get_state_history(config))
before_joke = next(s for s in history if s.next == ("write_joke",))

# Fork : topic 변경
fork_config = graph.update_state(before_joke.config, values={"topic": "chickens"})

# fork에서 재개 — write_joke가 새 topic으로 재실행
fork_result = graph.invoke(None, fork_config)
```

### `as_node` (특정 노드에서)

`update_state` 값은 지정 노드의 writer(reducer 포함)로 적용된다. 체크포인트는 그 노드가 업데이트를
생산한 것으로 기록하고, 실행은 그 노드의 후속 노드부터 재개. 기본적으로 LangGraph가 버전 이력에서
`as_node`를 추론한다. 명시가 필요한 경우 :
- **병렬 분기** : 같은 스텝에서 여러 노드가 갱신해 마지막을 결정 못함(`InvalidUpdateError`).
- **이력 없음** : 새 스레드에 상태 셋업(테스트에서 흔함).
- **노드 건너뛰기** : 후속 노드를 `as_node`로 지정해 그 노드가 이미 실행된 것처럼.

```python
fork_config = graph.update_state(before_joke.config, values={"topic": "chickens"},
                                 as_node="generate_topic")
# generate_topic이 생산한 것으로 취급 → write_joke(후속)부터 재개
```

## Interrupts와 함께

interrupt가 있으면 time travel 중 **항상 재트리거**된다. interrupt 노드가 재실행되고 새
`Command(resume=...)`를 기다린다.

```python
# ask_human 이전에서 replay → interrupt에서 정지, 새 Command(resume=...) 대기
before_ask = [s for s in history if s.next == ("ask_human",)][-1]
graph.invoke(None, before_ask.config)

# fork 후 다른 답변으로 재개
fork_config = graph.update_state(before_ask.config, {"value": ["forked"]})
graph.invoke(None, fork_config)
graph.invoke(Command(resume="Bob"), fork_config)
```

**다중 interrupt** : interrupt들 사이에서 fork해 이전 질문을 다시 묻지 않고 이후 답변만 변경.
```python
between = [s for s in history if s.next == ("ask_age",)][-1]  # ask_name 후, ask_age 전
fork_config = graph.update_state(between.config, {"value": ["modified"]})
# ask_name 결과 보존, ask_age는 interrupt에서 정지
```

## Subgraphs와 함께

서브그래프가 자체 checkpointer를 갖는지에 따라 time travel 입도가 달라진다.

**상속 checkpointer (기본)** : 부모가 서브그래프 전체를 **하나의 super-step**으로 취급. 서브그래프
실행 전체에 부모 레벨 체크포인트 하나만 존재. 서브그래프 이전에서 time travel하면 전체 재실행.
서브그래프 노드 *사이*로는 time travel 불가.

**`checkpointer=True`** : 서브그래프에 자체 체크포인트 이력 부여. 서브그래프 **내부** 각 스텝에
체크포인트 생성 → 내부 특정 지점(예: 두 interrupt 사이)에서 time travel 가능.

```python
subgraph = (... ).compile(checkpointer=True)   # 자체 이력

# 서브그래프 자체 체크포인트 접근
parent_state = graph.get_state(config, subgraphs=True)
sub_config = parent_state.tasks[0].state.config

# 서브그래프 체크포인트에서 fork
fork_config = graph.update_state(sub_config, {"value": ["forked"]})
result = graph.invoke(None, fork_config)   # step_b 재실행, step_a 결과 보존
```
