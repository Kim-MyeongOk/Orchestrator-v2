# Skill: System Design Document Synchronizer (시스템 설계서 동기화)

## Description
프로젝트 코딩 작업(API 엔드포인트 수정, 데이터 모델/테이블 변경, 미들웨어/파이프라인 추가, 주요 환경 변수 수정 등)이 이루어질 때마다 `SYSTEM_DESIGN.md` 문서가 최신 구현 상태를 정확히 반영하도록 자동으로 검토하고 업데이트 수정을 함께 수행하도록 지시하는 스킬입니다.

---

## Target File Path (대상 문서 경로)
- `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\.claude\SYSTEM_DESIGN.md`

---

## Trigger Condition (발동 조건)
아래 항목 중 하나라도 해당하는 코드 변경 작업이 발생하거나 완료되었을 때 즉시 발동합니다:

1. **API 엔드포인트 및 요청/응답 스키마 변경** (`server.py`, `*_api_router.py` 등)
2. **LangGraph 그래프 구조, 미들웨어, 처리 흐름(Pipeline) 변경**
3. **PostgreSQL 스키마 및 Redis 버퍼링 키/구조 변경**
4. **대화 압축(Context Compression) 규칙 및 주요 임계치(Threshold) 변경**
5. **새로운 환경 변수(Environment Variable) 추가 또는 변경**
6. **주요 클래스, 컴포넌트 추가/삭제 및 역할 변경**

---

## Actions Required for Claude (클로드 수행 지침)

1. **영향도 분석**:
   - 수정된 코드 내역이 `SYSTEM_DESIGN.md` 항목 중 어디에 영향을 미치는지 확인합니다.
     - 예: 엔드포인트 파라미터 변경 ➔ `1️⃣ 클라이언트 → 백엔드 API 요청` 및 `StreamRequest 모델` 업데이트
     - 예: 미들웨어 추가 ➔ `4️⃣ LLM 그래프 조회` 및 `6️⃣ LLM 추론 시작` 미들웨어 순서 업데이트
     - 예: DB/Redis 데이터 구조 변경 ➔ `8️⃣ 청크 저장`, `9️⃣ 체크포인트` 및 데이터 흐름 다이어그램 업데이트

2. **문서 동시 수정 수행**:
   - 코드 수정을 제공하는 답변 시점에 `SYSTEM_DESIGN.md` 파일의 해당 섹션도 **동시에 함께 수정**하거나, 수정할 마크다운 블록/전체 내용을 제시합니다.

3. **변경 내역 명시**:
   - 코드 수정 사항 외에도 `SYSTEM_DESIGN.md` 문서의 어떤 섹션이 어떻게 업데이트되었는지 답변 상단 또는 하단에 명확히 안내합니다.

---

## Guidelines for Document Format (문서 스타일 준수)

- `SYSTEM_DESIGN.md`의 기존 작성 방식(이모지 타이틀, 코드 블록, 마크다운 표, ASCII 데이터 흐름 다이어그램 포맷)을 일관되게 유지합니다.
- 변수명, 클래스명, 메서드명, 라인 번호 범위 및 환경 변수명을 실제 수정된 코드와 정확하게 일치시킵니다.