# Project Instructions (Local Only)

이 파일은 세션 시작 시 자동으로 읽힌다. 상세 규칙은 `.claude/skills/` 의 스킬로 나뉘어 있고,
스킬은 필요한 시점에 열린다. **여기에는 항상 지켜야 할 것만 둔다.**

## 항상 지킬 것

1. **`.claude` 폴더는 커밋하지 않는다.** `.gitignore` 대상인 로컬 전용 파일이다.
   내용은 갱신하되 staged 되면 `git restore --staged .claude` 로 뺀다.
2. **백엔드는 프로젝트 루트에서 실행한다.** `MODEL_CATALOG_PATH` 가 상대 경로라
   `backend/` 에서 띄우면 카탈로그를 못 찾고 `.env` 폴백으로 떨어져
   `OPENAI_API_KEY` 오류로 위장된 기동 실패가 난다.
3. **Ollama 는 0.24.x 에 고정한다.** 0.30.0+ 는 `mllama` 아키텍처를 버려
   `llama3.2-vision` 이 로드조차 되지 않는다. 업그레이드를 제안하지 않는다.
4. **코드를 고치면 문서도 같은 답변에서 함께 고친다.** → `doc-sync` 스킬
5. **코드 수정을 마치면 요청이 없어도 브랜치 · 커밋 · PR 을 제안한다.** → `git-workflow` 스킬

## 작업별로 여는 스킬

| 언제 | 스킬 |
|---|---|
| `backend/` 의 `.py` 를 만들거나 고치기 전 | `python-style` |
| 코드 변경 후 인덱스 · 설계서 · 사용자 설명서 갱신 | `doc-sync` |
| 브랜치 · 커밋 · PR · 작업 완료 보고 | `git-workflow` |
| deepagents 로 에이전트를 짤 때 | `deepagents-docs` |
| LangChain v1.x API 를 쓸 때 | `langchain-docs` |
| LangGraph 그래프 · 체크포인터 · 스트리밍을 다룰 때 | `langgraph-docs` |

스킬은 `description` 이 걸릴 때 자동으로 열린다. 걸리지 않았는데 위 표에 해당하는 작업이라면
해당 스킬을 직접 불러서 읽고 시작한다.

## 산출물 문서

`SYSTEM_DESIGN.md` 와 `USER_GUIDE.md` 는 규칙이 아니라 **결과물**이다.
갱신 방법은 `doc-sync` 스킬에 있다. 시스템 구조를 파악해야 할 때 읽는다.
