# Skill: Code Index Document Synchronizer (코드 인덱스 문서 동기화)

## Description
백엔드(Python) 및 프론트엔드(React)의 단일 기능 단위 파일(클래스, 컴포넌트, 모듈, Hook 등)이 생성되거나 수정될 때마다, 프로젝트 디렉터리 트리 구조를 반영하여 지정된 인덱스 폴더에 `.md` 파일 형태로 인덱스 문서를 자동 생성하고 최신 상태로 관리하는 스킬입니다.

이를 통해 클로드(AI)가 코드베이스 전체를 스캔하지 않고도 인덱스 문서를 통해 필요한 코드의 위치와 역할을 빠르게 파악하고 수정할 수 있도록 돕습니다.

---

## Target Directory Path (인덱스 저장 기본 경로)
- `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\.claude\index\`

---

## Index File Naming & Directory Rules (인덱스 파일 위치 규칙)

소스 코드의 상대 경로 구조를 인덱스 폴더(`\.claude\index\`) 하위에 동일한 트리 구조로 대응시켜 생성합니다 (`.py`, `.tsx`, `.jsx`, `.ts`, `.js` 등 소스 확장자에 상관없이 `.md`로 매핑).

- **백엔드 소스 예시**:
  `backend/app/orchestrator/saga_coordinator.py`
  ➔ `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\.claude\index\backend\app\orchestrator\saga_coordinator.md`

- **프론트엔드 소스 예시**:
  `frontend/src/components/Chat/ChatBox.tsx`
  ➔ `C:\Users\kmo97\PycharmProjects\vLLM_Orchestrator_Deep_Agent\.claude\index\frontend\src\components\Chat\ChatBox.md`

---

## Trigger Condition (발동 조건)

다음 경우 중 하나라도 해당할 때 인덱스 생성 및 업데이트 작업이 수행됩니다:

1. **최초 작업/확인 시 해당 소스 파일에 대응하는 인덱스 `.md` 파일이 존재하지 않을 때**
2. **신규 모듈, 클래스, 컴포넌트, Hook 파일이 추가되었을 때**
3. **기존 파일의 역할이나 내부 함수, 메서드, 상태(State) 처리 로직이 변경되었을 때**
4. **소스 파일의 위치(경로)가 이동되었을 때**

---

## File Format & Structure (인덱스 문서 양식)

### 1. 백엔드 (Python / Class / Module)
```markdown
파일 위치: {소스 코드의 절대 경로}

클래스/모듈 기능: {해당 클래스/모듈의 역할과 목적을 한 줄로 간략하게 기재}
하위 함수 기능:
- `{함수/메서드명_1}()`: {해당 함수의 역할과 목적을 한 줄로 간략하게 기재}
- `{함수/메서드명_2}()`: {해당 함수의 역할과 목적을 한 줄로 간략하게 기재}