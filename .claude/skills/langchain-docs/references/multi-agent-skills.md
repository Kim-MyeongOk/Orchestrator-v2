# 스킬 (Skills)

원문 : https://docs.langchain.com/oss/python/langchain/multi-agent/skills

스킬 아키텍처에서는 특화된 능력을 호출 가능한 "스킬"로 패키징하여 에이전트 동작을 보강한다. 스킬은 주로 **프롬프트 주도(prompt-driven) 특화**로, 에이전트가 온디맨드로 호출한다. 내장 스킬 지원은 Deep Agents를 참조.

이 패턴은 개념적으로 Agent Skills, llms.txt(Jeremy Howard 도입)와 동일하다. 도구 호출을 통한 문서의 점진적 공개(progressive disclosure)를 활용한다. 스킬 패턴은 단순 문서 페이지가 아니라 특화 프롬프트와 도메인 지식에 점진적 공개를 적용한다.

## 핵심 특성

- **프롬프트 주도 특화** : 스킬은 주로 특화 프롬프트로 정의된다.
- **점진적 공개** : 스킬은 컨텍스트나 사용자 필요에 따라 가용해진다.
- **팀 분산** : 서로 다른 팀이 스킬을 독립적으로 개발/유지보수한다.
- **경량 조합** : 스킬은 완전한 서브에이전트보다 단순하다.
- **참조 인식(Reference awareness)** : 스킬은 스크립트, 템플릿, 기타 리소스를 참조할 수 있다.

## 언제 사용하나

가능한 특화가 많은 단일 에이전트를 원할 때, 스킬 간 특정 제약을 강제할 필요가 없을 때, 서로 다른 팀이 독립적으로 능력을 개발해야 할 때 사용한다. 흔한 예 : 코딩 어시스턴트(언어/작업별 스킬), 지식 베이스(도메인별 스킬), 창작 어시스턴트(포맷별 스킬).

## 기본 구현

```python
from langchain.tools import tool
from langchain.agents import create_agent

@tool
def load_skill(skill_name: str) -> str:
    """Load a specialized skill prompt.

    Available skills:
    - write_sql: SQL query writing expert
    - review_legal_doc: Legal document reviewer

    Returns the skill's prompt and context.
    """
    # 파일/데이터베이스에서 스킬 내용 로드
    ...

agent = create_agent(
    model="gpt-5.4",
    tools=[load_skill],
    system_prompt=(
        "You are a helpful assistant. "
        "You have access to two skills: write_sql and review_legal_doc. "
        "Use load_skill to access them."
    ),
)
```

## 패턴 확장

커스텀 구현 시 기본 스킬 패턴을 여러 방식으로 확장할 수 있다.

- **동적 도구 등록(Dynamic tool registration)** : 점진적 공개와 상태 관리를 결합하여 스킬 로드 시 새 도구를 등록한다. 예를 들어 "database_admin" 스킬 로드가 특화 컨텍스트를 추가하면서 데이터베이스 전용 도구(backup, restore, migrate)도 등록할 수 있다. 멀티 에이전트 패턴 전반에서 쓰는 도구-상태 메커니즘과 동일하다.

- **계층적 스킬(Hierarchical skills)** : 스킬이 트리 구조로 다른 스킬을 정의하여 중첩된 특화를 만든다. 예를 들어 "data_science" 스킬을 로드하면 "pandas_expert", "visualization", "statistical_analysis" 같은 서브 스킬이 가용해진다. 각 서브 스킬은 필요에 따라 독립적으로 로드되어 도메인 지식의 세밀한 점진적 공개가 가능하다. 큰 지식 베이스를 논리적 그룹으로 조직하는 데 유용하다.

- **참조 인식(Reference awareness)** : 각 스킬은 프롬프트 하나만 갖지만, 이 프롬프트가 다른 자산의 위치와 언제 그것을 써야 하는지를 참조할 수 있다. 자산이 관련될 때 에이전트는 그 파일이 존재함을 알고 작업 완료를 위해 필요할 때 메모리로 읽어들인다. 이 역시 점진적 공개 패턴을 따르며 컨텍스트 윈도우의 정보를 제한한다.
