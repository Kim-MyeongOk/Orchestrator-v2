# Interrupts

원문 : https://docs.langchain.com/oss/python/langgraph/interrupts

`interrupt()`는 그래프 실행을 특정 지점에서 일시정지하고 외부 입력을 기다린다(HITL). interrupt 발생 시
LangGraph는 영속성 계층으로 상태를 저장하고 **무기한** 대기. 정적 breakpoint와 달리 **동적**이다
(코드 어디든, 조건부 가능).

필요 조건 :
1. 상태 영속용 **checkpointer** (프로덕션은 durable 백엔드)
2. config의 **thread_id** (재개할 상태를 식별 — 영속 커서. 재사용 시 같은 체크포인트 재개, 새 값이면 빈 상태 새 스레드)
3. JSON 직렬화 가능 페이로드로 `interrupt()` 호출

```python
from langgraph.types import interrupt

def approval_node(state: State):
    approved = interrupt("Do you approve this action?")   # 정지, 페이로드를 호출자에게 노출
    return {"approved": approved}                          # 재개 시 Command(resume=...)가 여기 반환됨
```

## 재개

같은 thread_id로 `Command(resume=값)`을 전달해 재개. **event streaming 권장** (interrupt를
`stream.interrupts`/`stream.interrupted`로, 최종 상태를 `stream.output`으로 노출).

```python
from langgraph.types import Command

config = {"configurable": {"thread_id": "thread-1"}}
stream = graph.stream_events({"input": "data"}, config=config, version="v3")
final = stream.output

if stream.interrupted:
    print(stream.interrupts)   # (Interrupt(value='Do you approve this action?'),)

resumed = graph.stream_events(Command(resume=True), config=config, version="v3")
final = resumed.output
```

(기본 `invoke()`도 `result["__interrupt__"]`로 노출.)

**핵심** : 재개 시 같은 thread_id 필수. `Command(resume=값)`이 `interrupt()`의 반환값이 됨.
**노드는 처음부터 재실행**되므로 interrupt 이전 코드가 다시 실행된다. `Command(resume=...)`만 입력으로
쓴다 — `Command(update/goto/graph)`는 노드 반환용이므로 입력으로 멀티턴 대화를 잇지 말 것(평범한 dict 사용).

## 주요 패턴

**HITL 스트리밍 루프** :
```python
stream_input = initial_input
while True:
    stream = graph.stream_events(stream_input, config=config, version="v3")
    for message in stream.messages:
        for token in message.text:
            display_streaming_content(token)
    if not stream.interrupted:
        final_state = stream.output
        break
    interrupt_info = stream.interrupts[0].value
    stream_input = Command(resume=get_user_input(interrupt_info))
```

**다중 interrupt** (병렬 분기가 동시에 interrupt) : interrupt id를 resume 값에 매핑.
```python
resume_map = {i.id: f"answer for {i.value}" for i in stream.interrupts}
resumed = graph.stream_events(Command(resume=resume_map), config, version="v3")
```

**승인/거부** :
```python
def approval_node(state) -> Command[Literal["proceed", "cancel"]]:
    is_approved = interrupt({"question": "...", "details": state["action_details"]})
    return Command(goto="proceed" if is_approved else "cancel")
# graph.stream_events(Command(resume=True), ...)  # 승인
```

**상태 검토·편집** :
```python
def review_node(state):
    edited = interrupt({"instruction": "Review and edit", "content": state["generated_text"]})
    return {"generated_text": edited}
# Command(resume="The edited text")
```

**도구 안 interrupt** (도구가 호출될 때마다 승인 정지) :
```python
@tool
def send_email(to: str, subject: str, body: str):
    """수신자에게 이메일을 보냅니다."""
    response = interrupt({"action": "send_email", "to": to, ..., "message": "Approve?"})
    if response.get("action") == "approve":
        final_to = response.get("to", to)   # resume 값으로 인자 오버라이드 가능
        ...
    return "Email cancelled by user"
```

**입력 검증** (루프) :
```python
def get_age_node(state):
    prompt = "What is your age?"
    while True:
        answer = interrupt(prompt)
        if isinstance(answer, int) and answer > 0:
            break
        prompt = f"'{answer}' is not a valid age. ..."
    return {"age": answer}
```

## interrupt 규칙 (중요)

`interrupt()`는 특수 예외를 raise해 정지한다. 재개 시 **노드 전체가 처음부터 재실행**된다. 따라서 :

1. **try/except로 감싸지 말 것** : bare except가 interrupt 예외를 삼킨다. interrupt와 에러 발생 코드를
   분리하거나, 구체적 예외 타입(`except NetworkException`)만 잡는다.
2. **노드 내 interrupt 호출 순서를 바꾸지 말 것** : resume 값 매칭이 **엄격히 인덱스 기반**이다.
   조건부로 interrupt를 건너뛰거나 비결정적 루프로 호출하면 인덱스 불일치. 매번 같은 순서로 호출.
3. **복잡한 값을 넘기지 말 것** : 함수·클래스 인스턴스는 직렬화 불가. JSON 직렬화 가능한 단순 타입/dict만.
4. **interrupt 이전 side effect는 idempotent해야 함** : 재실행되므로. upsert 사용, 또는 side effect를
   interrupt 이후에 두거나 별도 노드로 분리. (새 레코드 생성·리스트 append를 interrupt 전에 하면 중복 발생)

## 서브그래프와 함께

노드 안에서 서브그래프를 함수로 호출하고 그 안에서 interrupt가 발생하면, 부모는 **서브그래프를 호출한
노드의 처음부터**, 서브그래프도 **interrupt가 있던 노드의 처음부터** 재개된다. (양쪽 모두 이전 코드 재실행)

## 정적 interrupt (디버깅 breakpoint)

HITL용이 아닌 디버깅용. 컴파일/런타임에 `interrupt_before`/`interrupt_after` 지정. 재개는 입력에 `None`.

```python
graph = builder.compile(interrupt_before=["node_a"], interrupt_after=["node_b"], checkpointer=checkpointer)
graph.invoke(inputs, config=config)   # breakpoint까지 실행
graph.invoke(None, config=config)     # 다음 breakpoint까지 재개
```

LangSmith Studio UI에서도 정적 interrupt 설정·상태 검사 가능.
