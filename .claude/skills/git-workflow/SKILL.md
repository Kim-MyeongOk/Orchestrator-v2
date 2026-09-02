---
name: git-workflow
description: 이 저장소의 브랜치 이름 · 커밋 메시지 · PR 제목과 본문 · 작업 완료 보고를 규칙대로 만든다. "커밋 메시지 뽑아줘", "PR 올려줘", "브랜치명 추천해줘", "작업 끝났어", "커밋해줘" 같은 말이 나오면 반드시 이 스킬을 쓴다. 사용자가 따로 요청하지 않아도, 코드 수정을 끝낸 시점이면 브랜치 · 커밋 · PR 을 함께 제안한다. 버전 번호와 브랜치 접두사를 추측하면 기존 이력과 어긋나므로 이 스킬 없이 만들지 않는다.
---

# Git 작업 표준

이 저장소가 **실제로 쓰고 있는** 규칙이다. `references/` 의 문서는 일반론(Git Flow · Conventional Commits)이라
이 본문과 어긋나는 부분이 있다. **충돌하면 이 본문을 따른다.**

## 커밋 메시지

```
<major>.<minor>.<build>.<YYYY.MM.DD> <type>: <한국어 요약>
```

`type` 은 `feat` · `fix` · `refactor` 중 하나다. 요약은 한국어 명사형으로 끝낸다.

**반드시 `git log --oneline -1` 로 직전 번호를 확인하고 `build` 를 1 올린다.**
확인 없이 추측하면 번호가 어긋난다 — 실제로 그렇게 틀린 적이 있다.
`major`·`minor` 는 작업 성격이 바뀔 때만 올린다.

실제 이력:

```
1.27.53.2026.07.30 feat: 이미지 첨부 시 비전 모델 자동 전환 및 비전 답변 인계
1.27.52.2026.07.30 fix: llama3.2-vision 답변 반복과 이미지 미인식 문제 수정
1.26.50.2026.07.30 refactor: 파라미터 프리셋을 생각 정도로 통합
1.24.47.2026.07.28 refactor: llm_* 테이블 DDL 을 테이블별 파일로 분리
```

작성자 이름은 `MyeongOk-Kim` 이다.

```bash
git config user.name "MyeongOk-Kim"
```

## 브랜치 이름

```
<type>/<kebab-case-주제>
```

`type` 은 커밋과 같은 세 가지. 주제는 영어 2~4단어. **이슈 번호는 넣지 않는다.**

실제 이력:

```
fix/vision-image-handling          refactor/merge-preset-into-reasoning-effort
fix/llama32-vision-support         refactor/split-server-by-domain
feat/vision-pipeline-e2e           feat/multi-reference-and-web-icon
```

브랜치가 `master` 면 먼저 새 브랜치를 판다. 커밋과 push 는 사용자가 요청할 때만 한다.

## 작업 완료 보고

코드 수정을 마치면 **요청이 없어도** 아래 세 가지를 함께 낸다.

1. 추천 브랜치명 — `git branch -m` 또는 `git checkout -b` 명령까지
2. 커밋 메시지 — 위 형식대로, 번호를 확인한 뒤
3. PR 제목과 본문

PR 본문은 `## 배경` → `## 변경` → `## 검증` → `## 영향` 순서로 쓴다.
무엇을 왜 바꿨는지가 먼저고, 어떻게는 코드가 설명한다.

## 이 저장소의 주의점

- **`.claude` 폴더는 커밋하지 않는다.** `.gitignore` 대상이며 로컬 전용이다.
  실수로 staged 되면 `git restore --staged .claude` 로 뺀다.
- `.env` 에 MinIO 자격증명과 `AUTH_TOKEN_SECRET` 이 있다. 커밋 파일이나 문서에 값이 들어가지 않게 한다.
- 인터랙티브 플래그(`git rebase -i`, `git add -i`)는 이 환경에서 동작하지 않는다.

## 참조 문서

일반론이 필요할 때만 읽는다. 이 저장소 규칙은 위 본문이 전부다.

| 상황 | 파일 |
|---|---|
| Git Flow 기반 브랜치 전략 전반 | `references/branch-naming.md` |
| Conventional Commits 규격 전반 | `references/commit-message.md` |
| PR 본문 상세 템플릿과 체크리스트 | `references/pr-generator.md` |
| 작업 완료 보고 상세 형식 | `references/task-completion-report.md` |
