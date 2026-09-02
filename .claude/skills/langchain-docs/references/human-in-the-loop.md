# Human-in-the-loop

원문 : https://docs.langchain.com/oss/python/langchain/human-in-the-loop

HITL 미들웨어는 에이전트 도구 호출에 사람의 감독을 추가한다. 모델이 검토가 필요한 행동(파일 쓰기,
SQL 실행 등)을 제안하면 실행을 일시정지하고 결정을 기다린다. 각 도구 호출을 설정 가능한 정책에
대조하고, 개입이 필요하면 `interrupt`를 발행해 실행을 멈춘다. 그래프 상태는 LangGraph 영속성
레이어로 저장되어 안전하게 일시정지/재개된다.

## 인터럽트 결정 타입

| 타입 | 설명 | 예 |
|---|---|---|
| `approve` | 변경 없이 그대로 실행 | 이메일 초안을 그대로 발송 |
| `edit` | 수정 후 실행 | 발송 전 수신자 변경 |
| `reject` | 거부 + 설명을 대화에 추가 | 이메일 초안 거부하고 재작성 방법 설명 |
| `respond` | 도구 실행 건너뛰고 사람 메시지를 도구 결과로 사용 | "ask_user" 프롬프트에 직접 답변 |

다중 도구 호출이 동시에 멈추면 각각 별도 결정 필요. 결정은 인터럽트 요청의 액션 순서와 동일하게
제공해야 한다. **edit 시 보수적으로** — 큰 수정은 모델이 접근법을 재평가해 도구를 여러 번 실행하거나
예상치 못한 행동을 할 수 있다.

## 인터럽트 설정

`interrupt_on`에 도구→허용 결정 타입 매핑. checkpointer 필수.

```python
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import InMemorySaver

agent = create_agent(
    model="gpt-5.4",
    tools=[write_file, execute_sql, read_data],
    middleware=[HumanInTheLoopMiddleware(
        interrupt_on={
            "write_file": True,  # 모든 결정 허용
            "execute_sql": {"allowed_decisions": ["approve", "reject"]},  # 편집 불가
            "read_data": False,  # 안전, 승인 불필요
        },
        description_prefix="Tool execution pending approval",
    )],
    checkpointer=InMemorySaver(),  # 운영에선 AsyncPostgresSaver
)
```

`interrupt_on` 값 : `True`(기본 설정으로 인터럽트), `False`(자동 승인), `InterruptOnConfig`
(`allowed_decisions`, `description`).

## 인터럽트 응답

호출하면 완료되거나 인터럽트가 발생할 때까지 실행. `version="v2"`에서 결과는 `interrupts` 속성을
가진 `GraphOutput`. thread ID 필요.

```python
from langgraph.types import Command

config = {"configurable": {"thread_id": "some_id"}}
result = agent.invoke({"messages": [{"role": "user", "content": "Delete old records"}]},
                     config=config, version="v2")
print(result.interrupts)  # action_requests, review_configs 포함

# 승인하고 재개
agent.invoke(Command(resume={"decisions": [{"type": "approve"}]}), config=config, version="v2")
```

### 결정 타입별

```python
# approve
{"decisions": [{"type": "approve"}]}

# edit (도구명 + 인자)
{"decisions": [{"type": "edit", "edited_action": {"name": "tool_name", "args": {...}}}]}

# reject (피드백 메시지가 대화에 추가됨)
{"decisions": [{"type": "reject", "message": "No, this is wrong because..."}]}

# respond (사람 답변이 ToolMessage로 반환, 도구 미실행)
{"decisions": [{"type": "respond", "message": "Blue."}]}
```

다중 결정은 액션 순서대로 리스트로 제공.

## 스트리밍과 HITL

`stream_mode=["updates", "messages"]` + `version="v2"`로 진행/토큰 스트리밍, `__interrupt__`로
인터럽트 확인.

```python
for chunk in agent.stream({"messages": [...]}, config=config,
                          stream_mode=["updates", "messages"], version="v2"):
    if chunk["type"] == "messages":
        token, metadata = chunk["data"]
        if token.content:
            print(token.content, end="", flush=True)
    elif chunk["type"] == "updates":
        if "__interrupt__" in chunk["data"]:
            print(f"Interrupt: {chunk['data']['__interrupt__']}")

# 결정 후 재개
for chunk in agent.stream(Command(resume={"decisions": [{"type": "approve"}]}),
                          config=config, stream_mode=["updates", "messages"], version="v2"):
    ...
```

## 실행 라이프사이클

미들웨어는 모델 응답 후 도구 실행 전에 실행되는 `after_model` 훅을 정의 :
1. 모델이 응답 생성.
2. 미들웨어가 도구 호출 검사.
3. 사람 입력이 필요하면 `action_requests`/`review_configs`를 가진 `HITLRequest` 빌드 후
   `interrupt` 호출.
4. 사람 결정 대기.
5. `HITLResponse` 결정에 따라 승인/편집 호출 실행, 거부 호출은 `ToolMessage` 합성, `respond`는
   사람 답변을 `ToolMessage`로 직접 반환, 실행 재개.

## 커스텀 HITL 로직

더 특수한 워크플로우는 `interrupt` 프리미티브와 미들웨어 추상화로 직접 구현 가능.
