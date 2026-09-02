---
name: python-style
description: "이 저장소의 파이썬 코드 스타일 규약. 파일 하나에 클래스 하나, __init__.py 를 만들지 않음(네임스페이스 패키지), 한 줄에 하나만 import 하고 import 컬럼 정렬, 타입 어노테이션 콜론 양쪽에 공백, 키워드 인자 등호 양쪽에 공백, 연속 대입문과 dict 콜론 컬럼 정렬, 축약 금지(max 는 maximum, config 는 Configuration, _dict 는 _dictionary), 변수명에 타입 접미사(_list · _dictionary · _count), 주석은 한국어, docstring 없음. backend/ 아래 .py 파일을 새로 만들거나 고치기 전에 반드시 이 스킬을 읽는다. black·ruff 를 쓰지 않는 고유 스타일이라 이 규약 없이 짜면 기존 120개 파일과 어긋난다."
---

# 파이썬 코드 작성 지침

새 코드를 작성하거나 기존 코드를 수정할 때 반드시 이 지침을 따른다.

---

## 프로젝트 컨텍스트

- **Python 버전**: 3.12+
- **패키지 매니저**: `uv` (선호) / `pip`
- **주요 스택**: <deepagents / langgraph / langchain / fastapi / uvicorn / httpx / aiohttp / asyncpg / redis>
- **엔트리포인트**: `backend/server.py`

## 개발 명령

```windows command prompt
# 가상환경 + 의존성
uv venv && source .venv\scripts\activate
uv sync
```

## 프로젝트 구조

- **소스 루트 레이아웃**을 사용한다. 패키지 루트는 `backend/common`(범용 라이브러리)과 `backend/app`(애플리케이션 도메인)이다.
- **`__init__.py`를 만들지 않는다.** 전체 코드베이스에 `__init__.py`가 하나도 없다 (네임스페이스 패키지).
- 디렉터리는 기능 범주별로 깊게 나눈다. 예: `common/resilience/circuit_breaker/`, `common/network/fastapi/`, `common/workflow/saga_coordinator/`.
- **/backend/common 폴더**
  - 재사용 가능한 인프라 컴포넌트 작성
- **/backend/app 폴더**
  - 만들려는 시스템에 관련된 기능
- **하위 폴더 구성**
  - /backend/common 폴더와 /backend/app 폴더의 내부는 기능 집합 단위로 폴더를 분리한다.
  - 구체적 폴더명/파일명은 개발자가 결정하되, 단일 폴더에 무관한 기능이 섞이지 않게 한다.
- **의존 방향**
  - /backend/common 폴더 내의 모듈은 /backend/app 폴더 내의 모듈을 import하지 않는다.
  - /backend/app 폴더 내의 폴더 간 의존은 단방향, 순환 import가 발생하지 않도록 한다.
- **파일 하나에 클래스 하나**를 원칙으로 한다. 파일명은 클래스명의 snake_case다.
  - `saga_coordinator.py` → `SagaCoordinator`
  - `retry_configuration.py` → `RetryConfiguration`
- 사용 예제는 같은 폴더에 `demo_*.py` 파일로 만들고, `if __name__ == "__main__":` 블록 안에 작성한다.
  - 예: `task_helper.py` 옆에 `demo_task_helper.py`.
- 패키지 관리는 **uv**를 사용하고, Python은 **3.12 이상**이다.

## 임포트 규칙

- **한 줄에 하나의 이름만 임포트한다.** `from typing import Dict, List` 같은 다중 임포트는 금지한다 (코드베이스 전체에서 0건).

```python
import inspect
import asyncio

from typing   import Dict
from typing   import Optional
from typing   import Any
from datetime import datetime
from datetime import timezone

from common.workflow.saga_coordinator.saga_definition import SagaDefinition
from common.workflow.saga_coordinator.saga_execution  import SagaExecution
```

- 임포트 그룹 순서는 다음과 같고, 그룹 사이는 빈 줄로 구분한다.
  1. `import x` 형태의 표준/외부 라이브러리
  2. `from x import y` 형태의 표준/외부 라이브러리
  3. 프로젝트 내부 절대 임포트 (`from common....`, `from app....`)
- 같은 그룹 안에서는 **`import` 키워드의 컬럼 위치를 공백으로 정렬**한다.
- 내부 모듈은 항상 **절대 경로**로 임포트한다 (`from common.task.task_status import TaskStatus`). 상대 임포트는 사용하지 않는다.
- 외부 패키지를 처음 사용하는 파일 최상단에는 설치 명령을 주석으로 남긴다.

```python
# uv add httpx
import httpx
```

- 타입 힌트는 `typing` 모듈을 사용한다 (`Dict`, `List`, `Optional`, `Tuple`, `Union`). Python 3.12 환경이지만 내장 제네릭(`dict[str, Any]`) 대신 `typing` 스타일을 유지한다.

## 명명 규칙

### 타입을 드러내는 접미사 (핵심 규칙)

변수명에 자료형/의미를 축약 없이 명시한다.

| 접미사 | 용도 | 예 |
|---|---|---|
| `_list` | 리스트 | `step_list`, `required_field_list`, `log_table_list` |
| `_dictionary` | 딕셔너리 (`_dict` 금지) | `header_dictionary`, `context_dictionary`, `response_dictionary` |
| `_tuple` | 튜플 | `jitter_range_tuple` |
| `_count` | 개수 | `attempt_count`, `maximum_worker_count`, `total_item_count` |
| `_callable` | 함수/콜러블 | `forward_transaction_callable` |
| `_id` | 식별자 | `master_id`, `execution_id` |

### 축약어 금지

- `max`/`min` 대신 `maximum`/`minimum` — `maximum_attempt_count`, `minimum_connection_count`
- `config` 대신 클래스명은 `Configuration` — `RetryConfiguration`, `TimeoutConfiguration`
- 단위를 변수명에 포함한다 — `delay_second_count`, `timeout_second_count`, `base_delay`

### 클래스명 역할 접미사

| 접미사 | 역할 | 예 |
|---|---|---|
| `Helper` | 정적 유틸리티 클래스 | `FileHelper`, `TaskHelper`, `AesHelper` |
| `Configuration` | 설정 dataclass | `RetryConfiguration`, `BulkheadConfiguration` |
| `Status` | 상태 Enum | `TaskStatus`, `SagaStatus` |
| `Error` | 예외 클래스 | `CircuitBreakerError`, `TimeoutError` |
| `Coordinator` / `Handler` / `Executor` / `Worker` | 동작 주체 클래스 | `SagaCoordinator`, `CompensationHandler`, `BackgroundWorker` |
| `Middleware` | FastAPI 미들웨어 | `RateLimitMiddleware` |
| `Agent` | LLM 에이전트 | `FederationAgent`, `ReactAgent` |

### 기타

- boolean은 `is_` / `has_` 접두사를 쓴다 — `is_success()`, `has_done_signal`.
- private 메서드는 `_` 접두사 — `_execute_saga_steps()`, `_validate_openai_response()`.
- `except` 변수명은 `exception`을 쓰고, 중첩되면 `exception1`, `exception2`로 번호를 붙인다. 타입이 구체적이면 그 이름을 쓴다 (`request_error`).
- 비동기 메서드는 LangChain 관례대로 `a` 접두사를 붙인다 — `ainvoke()`, `astream()`, `async_execute_with_timeout()`.

## 포매팅 (이 프로젝트 고유 스타일)

**주의: 이 프로젝트는 PEP 8 표준 포매팅과 다른 고유 규칙을 쓴다. black/ruff 자동 포매팅을 적용하지 않는다.**

### 타입 어노테이션 콜론 양쪽에 공백

```python
def read_string_from_text_file(source_file_path : str, encoding : str = "utf-8") -> str:
```

### 키워드 인자의 `=` 양쪽에 공백

```python
open(target_file_path, "w", encoding = encoding)
SagaStepExecution(step_id = saga_step.id)
TaskHelper.retry(maximum_attempt_count = 3, delay_second_count = 0.5)
```

### 연속된 대입문은 `=` 컬럼을 정렬

```python
self.base_url          = base_url
self.async_client      = async_client
self.default_timeout   = default_timeout
self.header_dictionary = {"Content-Type" : "application/json"}
```

### dict 리터럴은 `:` 컬럼을 정렬 (키는 큰따옴표)

```python
return {
    "host"                     : postgresql_config_dict.host,
    "port"                     : postgresql_config_dict.port,
    "minimum_connection_count" : postgresql_config_dict.minimum_connection_count,
    "enabled"                  : postgresql_config_dict.enabled
}
```

### Enum 값도 `=` 컬럼을 정렬

```python
class TaskStatus(Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
```

- 문자열은 큰따옴표(`"`)를 사용한다.
- 들여쓰기는 공백 4칸이다.
- 시그니처가 길어도 한 줄로 쓴다. 함수 호출 인자가 많을 때만 줄을 나누고, 나눌 경우 키워드 인자를 정렬한다.

## 주석과 문서화

- **주석은 한국어로 작성한다.**
- **docstring은 원칙적으로 쓰지 않는다.** 예외는 LangChain `@tool` 함수다. 이 docstring은 LLM이 읽는 도구 설명이므로 반드시 한국어 한 줄로 작성한다.

```python
@tool
def divide(a : float, b : float) -> float:
    """두 숫자를 나눕니다."""
    if b == 0:
        raise ValueError("0으로 나눌 수 없습니다")
    return a / b
```

- 복잡한 클래스 파일은 최상단에 `#` 50개 블록으로 한국어 설명 헤더를 단다.

```python
##################################################
# 사가 코디네이터
# 분산 트랜잭션 관리를 위한 사가 패턴을 구현하며, 장애 복구를 위한 보상 로직을 포함한다.
##################################################
```

- 클래스 내부의 메서드 그룹은 같은 형식의 구분선으로 나눈다.

```python
    ##################################################
    # 텍스트 파일
    ##################################################
```

- dataclass 필드는 우측에 한국어 인라인 주석으로 의미와 기본값을 설명한다.

```python
maximum_attempt_count : int   = 3    # 최대 시도 횟수 (기본값 : 3)
base_delay            : float = 1.0  # 기본 대기 시간(초) (기본값 : 1.0)
```

## 클래스 설계 패턴

### 정적 유틸리티는 Helper 클래스

모듈 수준 함수 대신 `@staticmethod`만 모은 `*Helper` 클래스를 만든다.

```python
class FileHelper:
    @staticmethod
    def read_binary_file(source_file_path : str) -> bytes:
        with open(source_file_path, "rb") as buffered_reader:
            source_bytes = buffered_reader.read()
            return source_bytes
```

### 설정은 @dataclass

```python
@dataclass
class RetryConfiguration:
    maximum_attempt_count : int  = 3     # 최대 시도 횟수 (기본값 : 3)
    jitter                : bool = True  # Jitter 추가 여부 (기본값 : True)
    total_attempt_count   : int  = field(default = 0, init = False)
```

### 상태는 Enum (값은 소문자 문자열)

```python
class SagaStatus(Enum):
    RUNNING   = "running"
    COMPLETED = "completed"
```

### 단순 예외는 pass 한 줄

```python
class CircuitBreakerError(Exception):
    pass
```

### 결과 객체는 상태 판별 메서드와 `__repr__`을 갖는다

```python
class TaskResult:
    def is_success(self) -> bool:
        return self.task_status == TaskStatus.COMPLETED

    def __repr__(self) -> str:
        return f"TaskResult(task_status={self.task_status.value}, execution_time={self.execution_time:.3f}s)"
```

### 클래스 내부 코드는 전역 변수를 참조하지 않는다

- 전역 변수를 클래스 내에서 사용하지 않는다.
- 클래스 생성자나 메소드에 반드시 데이터를 명시적으로 전달해서 처리한다.

### 클래스 내부에서 함수들 중에서 생성자 함수가 제일 먼저 표시된다.

### 클래스 내부에서 함수들의 배치 순서는 호출되는 함수는 호출하는 함수의 앞에 표시된다.

## 에러 처리

- 파일 삭제 같은 단순 유틸리티는 예외를 던지지 않고 **`bool` 반환**으로 성공/실패를 알린다.

```python
@staticmethod
def delete_file(target_file_path : str) -> bool:
    try:
        ...
        return True
    except Exception:
        return False
```

- 로깅처럼 본 기능을 막으면 안 되는 부수 작업은 `try / except: pass`로 침묵 처리한다 (`LogHelper` 패턴).
- 외부 API를 중계하는 게이트웨이 코드는 예외를 **구체적인 것부터 일반적인 것 순서로** 잡고, 예외를 다시 던지지 않고 **표준 에러 응답 dict를 반환**한다.

```python
except httpx.TimeoutException:
    error_response_dictionary = LLMErrorHelper.get_error_response_dictionary(message = "Request timed out", error_type = "api_error", code = "timeout")
    return {"status_code" : 504, "content" : error_response_dictionary}
except httpx.RequestError as request_error:
    ...
    return {"status_code" : 503, "content" : error_response_dictionary}
except Exception as exception:
    ...
    return {"status_code" : 500, "content" : error_response_dictionary}
```

- 워크플로우 엔진(사가 등) 내부 단계 실패는 상태를 기록한 뒤 `raise`로 다시 던져 상위에서 보상 로직을 트리거한다.
- 검증 실패는 `ValueError`에 **대문자 영어 메시지 + ` : ` 구분자** 형식으로 던진다.

```python
raise ValueError(f"SAGA NOT FOUND : {saga_id}")
```

## 출력과 로깅

- `common` 라이브러리와 데모 코드는 `print()`를 쓰고, 메시지는 **대문자 영어 + ` : ` 구분자**로 쓴다.

```python
print(f"COMPLETED SAGA EXECUTION : {saga_execution.id}")
print(f"SAGA STEP FAILED : {step.id} - {exception}")
```

- 데모 파일의 섹션 구분은 `print("-" * 50)`과 대문자 제목으로 한다.
- 운영(app) 코드의 로깅은 `LogHelper` / `LogBatchWriter`(PostgreSQL 배치 기록)를 사용한다.

## 비동기 코드

- sync/async 콜러블을 모두 받아야 하는 실행기는 `inspect.iscoroutinefunction()`으로 분기하고, sync는 `run_in_executor`로 실행한다.

```python
if inspect.iscoroutinefunction(step.forward_transaction_callable):
    result = await step.forward_transaction_callable(saga_execution.context_dictionary)
else:
    loop   = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, step.forward_transaction_callable, saga_execution.context_dictionary)
```

- 시간은 `datetime.now(timezone.utc)`로 기록한다 (워크플로우/실행 기록 계열).
- 타임아웃 파라미터는 호출 시 재정의 가능하게 하고, `None`이면 인스턴스 기본값을 쓴다.

```python
actual_timeout = timeout if timeout is not None else self.default_timeout
```

## 새 모듈 추가 절차 요약

1. 기능 범주에 맞는 폴더를 찾거나 만든다 (`common/<범주>/<세부범주>/`). `__init__.py`는 만들지 않는다.
2. 클래스 하나당 파일 하나, 파일명은 클래스명의 snake_case로 만든다.
3. 파일 첫 줄(또는 블록 헤더)에 한국어로 역할을 설명한다.
4. 상태가 필요하면 `*_status.py`(Enum), 설정이 필요하면 `*_configuration.py`(dataclass), 예외가 필요하면 `*_error.py`를 별도 파일로 분리한다.
5. 임포트는 한 줄에 하나, 그룹별 정렬을 지킨다.
6. 사용 예제를 `demo_*.py`로 같은 폴더에 추가한다.
7. 새 외부 의존성은 `uv add <패키지>`로 추가하고, 사용 파일 상단에 `# uv add <패키지>` 주석을 남긴다.
