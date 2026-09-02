파일 위치: `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\backend\app\llm\compression\conversation_summarizer.py`

클래스 기능: `ConversationSummarizer` - LLM 기반 대화 요약 생성기 (토큰 절약용)

하위 함수 기능:
- `compress_if_needed_async()`: 메시지 수/토큰 수 임계치 도달 시 요약 생성 및 반환
- `_generate_summary_async()`: LLM을 호출하여 대화 요약 생성 (reasoning 비활성화)
- `_is_compression_needed()`: 메시지 수와 토큰 수를 확인하여 압축 필요 여부 판정
- `_format_message_for_summary()`: 메시지를 요약용 프롬프트 형식으로 변환
