# Functional API Overview

원문 : https://docs.langchain.com/oss/python/langgraph/functional-api

**Functional API**는 기존 코드에 최소 변경으로 LangGraph 핵심 기능(영속성·메모리·HITL·스트리밍)을 추가한다.
`if`/`for`/함수 호출 같은 표준 언어 primitive를 그대로 쓰며, 명시적 파이프라인/DAG 재구조화를 강제하지 않는다.

두 빌딩 블록 :
- **`@entrypoint`** : 워크플로우 시작점. 로직 캡슐화·실행 흐름 관리(장시간 작업·interrupt 처리).
- **`@task`** : 이산 작업 단위(API 호출, 데이터 처리). entrypoint 안에서 비동기 실행. future-like 객체 반환.

## Graph API와 차이

- **제어 흐름** : 그래프 구조를 생각할 필요 없음. 표준 Python 구문. 보통 코드량 감소.
- **단기 메모리** : Graph API는 State 선언·reducer 정의 필요. `@entrypoint`/`@task`는 명시적 상태 관리
  불필요(상태가 함수에 범위 한정, 함수 간 비공유).
- **체크포인팅** : 둘 다 사용. Graph API는 super-step마다 새 체크포인트. Functional API는 task 실행 시
  결과를 기존 entrypoint 체크포인트에 저장(새로 생성 안 함).
- **시각화** : Graph API는 그래프 시각화 가능. Functional API는 런타임 동적 생성이라 미지원.

## 예시

```python
from langgraph.func import entrypoint, task
from langgraph.types import interrupt
from langgraph.checkpoint.memory import InMemorySaver

@task
def write_essay(topic: str) -> str:
    """주어진 주제로 에세이를 작성합니다."""
    time.sleep(1)
    return f"An essay about topic: {topic}"

@entrypoint(checkpointer=InMemorySaver())
def workflow(topic: str) -> dict:
    essay = write_essay("cat").result()
    is_approved = interrupt({"essay": essay, "action": "Please approve/reject"})
    return {"essay": essay, "is_approved": is_approved}
```

재개 시 워크플로우는 **처음부터 실행되지만**, `write_essay` 결과는 체크포인트에서 로드(재계산 안 함).
재개 : `workflow.stream(Command(resume=human_review), config)`.

## Entrypoint

`@entrypoint` 데코레이터로 함수→워크플로우. 함수는 **단일 위치 인자**(워크플로우 입력)만 받음(여러
데이터는 dict). `Pregel` 인스턴스 생성(스트리밍·재개·체크포인팅 관리). 보통 **checkpointer** 전달.

> **직렬화** : entrypoint 입출력은 JSON 직렬화 가능해야 함(체크포인팅).

### 주입 파라미터

| 파라미터 | 설명 |
|---|---|
| `previous` | 이 스레드의 이전 checkpoint 상태(단기 메모리) |
| `store` | `BaseStore`(장기 메모리) |
| `writer` | `StreamWriter`(Async Python < 3.11 커스텀 스트리밍) |
| `config` | 런타임 설정 |

```python
@entrypoint(checkpointer=in_memory_checkpointer, store=in_memory_store)
def my_workflow(some_input: dict, *, previous: Any = None, store: BaseStore,
                writer: StreamWriter, config: RunnableConfig) -> ...:
```

### 실행·재개

`invoke`/`ainvoke`/`stream`/`astream`. interrupt 후 재개는 `Command(resume=값)`. 에러 후 재개는 `None` +
같은 thread_id(에러 해결 가정).

### 단기 메모리 (previous)

```python
@entrypoint(checkpointer=checkpointer)
def my_workflow(number: int, *, previous: Any = None) -> int:
    previous = previous or 0
    return number + previous

my_workflow.invoke(1, config)  # 1 (previous None)
my_workflow.invoke(2, config)  # 3 (previous 1)
```

기본적으로 `previous`는 이전 호출 반환값.

### entrypoint.final

**체크포인트 저장값**과 **반환값**을 분리. `entrypoint.final(value=반환, save=저장)`. 타입은
`entrypoint.final[return_type, save_type]`.

```python
@entrypoint(checkpointer=checkpointer)
def my_workflow(number: int, *, previous: Any = None) -> entrypoint.final[int, int]:
    previous = previous or 0
    return entrypoint.final(value=previous, save=2 * number)   # previous 반환, 2*number 저장
```

## Task

이산 작업. 특성 : **비동기 실행**(동시 실행 비차단), **체크포인팅**(결과 저장→재개).

```python
from langgraph.func import task

@task()
def slow_computation(input_value):
    ...
    return result
```

> **직렬화** : task 출력은 JSON 직렬화 가능해야 함.

**실행** : task는 **entrypoint·다른 task·state graph 노드 안에서만** 호출(메인 코드에서 직접 호출 불가).
호출 시 즉시 future 반환. 결과는 `.result()`(동기) 또는 `await`(비동기).

```python
@entrypoint(checkpointer=checkpointer)
def my_workflow(some_input: int) -> int:
    future = slow_computation(some_input)
    return future.result()
```

## task를 쓸 때

체크포인팅(장시간 작업 결과 저장→재개 시 재계산 회피), HITL(랜덤성/API 호출 캡슐화로 올바른 재개),
병렬 실행(I/O-bound 동시), 관찰성(LangSmith), 재시도 가능 작업.

## 결정성 (Determinism)

재개 시 코드는 **멈춘 줄에서 재개하지 않는다**. 체크포인트 경계로 돌아가 다시 pause까지 **재생(replay)**한다.
Functional API는 entrypoint 처음부터 재생하며 완료된 task·subgraph 결과를 체크포인터에서 복원(재계산 안 함).

HITL 등을 쓰려면 **비결정적 작업(랜덤)·부수 효과(파일 쓰기·API 호출)를 task에 넣어야 한다.** 가이드라인 :
- 작업 반복 회피 : 여러 부수 효과는 각각 별도 task로(재개 시 출력 복원).
- 비결정적 연산 캡슐화 : 시도마다 바뀌는 값(랜덤·wall-clock)을 task 안에.
- 멱등 연산 사용.

## 멱등성 (Idempotency)

같은 연산을 여러 번 실행해도 같은 결과. 재개 시 LangGraph는 완료된 task 결과를 재생하지만, 시작했으나
완료 안 된 task는 재개 시 다시 실행될 수 있다. 부수 효과(특히 데이터 쓰기)는 멱등하게 설계 — 멱등성
키 사용 또는 기존 결과 검증으로 중복 방지.

## 흔한 함정

### 부수 효과
파일 쓰기·이메일 전송 등을 task에 캡슐화(재개 시 중복 실행 방지).

```python
# 잘못 — 재개 시 두 번 실행
@entrypoint(checkpointer=checkpointer)
def my_workflow(inputs: dict) -> int:
    with open("output.txt", "w") as f:
        f.write("Side effect")
    value = interrupt("question")
    return value

# 올바름 — task에 캡슐화
@task
def write_to_file():
    with open("output.txt", "w") as f:
        f.write("Side effect")

@entrypoint(checkpointer=checkpointer)
def my_workflow(inputs: dict) -> int:
    write_to_file().result()
    value = interrupt("question")
    return value
```

### 비결정적 제어 흐름

현재 시간·랜덤은 task에 캡슐화(재개 시 같은 결과). LangGraph는 각 task/entrypoint에 resume 값 리스트를
유지하고, interrupt를 만나면 대응 resume 값과 **index 기반**으로 매칭한다. 실행 순서가 유지되지 않으면
interrupt가 잘못된 resume 값과 매칭될 수 있다(특히 다중 interrupt HITL).

```python
# 올바름 — 시간을 task에
@task
def get_time() -> float:
    return time.time()

@entrypoint(checkpointer=checkpointer)
def my_workflow(inputs: dict) -> int:
    t1 = get_time().result()
    ...
```
