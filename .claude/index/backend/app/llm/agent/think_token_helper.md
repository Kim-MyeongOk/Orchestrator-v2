파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\agent\think_token_helper.py`

클래스 기능: `ThinkTokenHelper` - 생각 토큰(reasoning) 감지/트리밍 정적 유틸리티

> 서빙 조합마다 생각 토큰이 실려 오는 자리가 다르다 —
> 인라인 `<think>` 태그 / ollama `additional_kwargs.reasoning_content` / google `thinking` 블록.
> 세 경로를 모두 알아보고 걷어내야 다음 턴 프롬프트가 생각 토큰으로 부풀지 않는다.

상수: `THINK_TAG_PATTERN` — `<think>(.*?)</think>` (DOTALL)

하위 함수 기능:
- `count_think_byte(message)`: 메시지 1건의 생각 토큰 바이트 수 (체크포인트 진단 `/diagnose` 용)
- `prepare_model_input(message_list, window_message_count)`: 트리밍 + 최근 N개 윈도잉 (기본 20)
- `extract_message_texts(message)`: `(본문 텍스트, 생각 텍스트)` 추출.
  `ThreadService` 의 표시 규칙과 `ReferenceContextBuilder` 의 답변 순번이 이 함수를 공유해야 서로 어긋나지 않는다
