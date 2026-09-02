# Structured output

원문 : https://docs.langchain.com/oss/python/langchain/structured-output

에이전트가 특정한 예측 가능한 형식(JSON 객체, Pydantic 모델, dataclass)으로 데이터를 반환하게
한다. `create_agent`가 자동 처리하며, 모델이 구조화 데이터를 생성하면 캡처/검증되어 상태의
`'structured_response'` 키로 반환된다. (모델에 직접 구조화 출력 적용은 references/models.md 참고)

## response_format

```python
def create_agent(
    ...
    response_format: Union[
        ToolStrategy[StructuredResponseT],
        ProviderStrategy[StructuredResponseT],
        type[StructuredResponseT],
        None,
    ]
)
```

- **`ToolStrategy`** : 도구 호출로 구조화 출력.
- **`ProviderStrategy`** : 프로바이더 네이티브 구조화 출력.
- **스키마 타입 직접 전달** : 모델 역량에 따라 자동 선택(네이티브 지원 시 `ProviderStrategy`,
  아니면 `ToolStrategy`). OpenAI/Anthropic/xAI 등이 네이티브 지원.
- **`None`** : 명시적으로 요청 안 함.

`langchain>=1.1`에선 모델 프로파일 데이터로 네이티브 지원 여부를 동적으로 읽는다. 데이터 없으면
`profile={"structured_output": True}` 등으로 수동 지정. 도구 지정 시 모델이 도구와 구조화 출력
동시 사용을 지원해야 한다.

## Provider strategy

가장 신뢰성 높은 방법(가능할 때 사용). 프로바이더가 스키마를 강제.

```python
class ProviderStrategy(Generic[SchemaT]):
    schema: type[SchemaT]
    strict: bool | None = None   # strict는 langchain>=1.2
```

스키마 지원 : Pydantic(검증된 인스턴스 반환), Dataclass/TypedDict/JSON Schema(dict 반환).

```python
from pydantic import BaseModel, Field
from langchain.agents import create_agent

class ContactInfo(BaseModel):
    name: str = Field(description="The name")
    email: str = Field(description="The email")
    phone: str = Field(description="The phone")

agent = create_agent(model="gpt-5.5", response_format=ContactInfo)  # ProviderStrategy 자동 선택
result = agent.invoke({"messages": [{"role": "user", "content": "..."}]})
print(result["structured_response"])  # ContactInfo(...)
```

`response_format=ContactInfo`와 `response_format=ProviderStrategy(ContactInfo)`는 네이티브
지원 시 기능적으로 동등. 미지원 시 둘 다 ToolStrategy로 폴백.

## Tool calling strategy

네이티브 미지원 모델용. 도구 호출을 지원하는 대부분의 모델에서 작동.

```python
class ToolStrategy(Generic[SchemaT]):
    schema: type[SchemaT]
    tool_message_content: str | None
    handle_errors: Union[bool, str, type[Exception], tuple[...], Callable[[Exception], str]]
```

스키마 지원에 **Union 타입** 추가(모델이 컨텍스트에 따라 적절한 스키마 선택).

```python
from langchain.agents.structured_output import ToolStrategy
from typing import Literal

class ProductReview(BaseModel):
    rating: int | None = Field(description="...", ge=1, le=5)
    sentiment: Literal["positive", "negative"]
    key_points: list[str]

agent = create_agent(model="gpt-5.5", tools=tools,
                     response_format=ToolStrategy(ProductReview))
# Union: response_format=ToolStrategy(Union[ProductReview, CustomerComplaint])
```

### 커스텀 도구 메시지 콘텐츠

`tool_message_content`로 구조화 출력 생성 시 대화 히스토리에 나타나는 메시지를 커스터마이즈.

```python
response_format=ToolStrategy(
    schema=MeetingAction,
    tool_message_content="Action item captured and added to meeting notes!"
)
# 기본값: "Returning structured response: {...}"
```

### 에러 처리

도구 호출 기반 구조화 출력 생성 시 모델 실수를 자동 재시도로 처리.

- **다중 구조화 출력 에러** : 모델이 여러 구조화 출력 도구를 호출하면 `ToolMessage`로 피드백 후
  재시도 유도.
- **스키마 검증 에러** : 출력이 스키마와 불일치하면 구체적 피드백(예: rating>5는 검증 오류).

`handle_errors` 전략(기본 `True`) :

```python
ToolStrategy(schema=ProductRating, handle_errors=True)   # 기본 템플릿으로 모든 에러 처리
ToolStrategy(schema=ProductRating, handle_errors="커스텀 메시지")  # 항상 고정 메시지로 재시도
ToolStrategy(schema=ProductRating, handle_errors=ValueError)  # 해당 예외만 재시도, 나머지는 raise
ToolStrategy(schema=ProductRating, handle_errors=(ValueError, TypeError))  # 다중 예외
ToolStrategy(schema=ProductRating, handle_errors=custom_handler_fn)  # 커스텀 핸들러
ToolStrategy(schema=ProductRating, handle_errors=False)  # 재시도 없음, 모든 예외 전파
```

커스텀 핸들러 예 :

```python
from langchain.agents.structured_output import (
    StructuredOutputValidationError, MultipleStructuredOutputsError)

def custom_error_handler(error: Exception) -> str:
    if isinstance(error, StructuredOutputValidationError):
        return "There was an issue with the format. Try again."
    elif isinstance(error, MultipleStructuredOutputsError):
        return "Multiple structured outputs were returned. Pick the most relevant one."
    return f"Error: {str(error)}"
```
