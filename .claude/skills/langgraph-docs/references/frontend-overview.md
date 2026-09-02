# Frontend Overview

원문 : https://docs.langchain.com/oss/python/langgraph/frontend/overview

LangGraph 파이프라인을 실시간으로 시각화하는 프론트엔드 빌드. 노드별 상태와 커스텀 `StateGraph`
워크플로우의 스트리밍 콘텐츠를 렌더링한다.

**핵심 장점** : UI가 그래프와 같은 구조를 따를 수 있다. 노드, 상태 키, 체크포인트, interrupt, 서브그래프,
스트리밍 메시지가 모두 가시적 런타임 개념이라, 실행을 하나의 어시스턴트 메시지 뒤에 숨기는 대신
시스템이 무엇을 하는지 설명하는 인터페이스를 만들 수 있다.

> v1 프론트엔드 SDK 패키지 사용. (React/Vue/Svelte/Angular 마이그레이션 가이드 별도)

## 아키텍처

그래프는 엣지로 연결된 명명된 노드로 구성. 각 노드가 한 스텝(classify/research/analyze/synthesize)을
실행하고 특정 상태 키에 출력을 쓴다. 프론트엔드 SDK의 stream 핸들이 노드 출력·스트리밍 토큰·발견된
서브그래프에 reactive하게 접근하게 해 각 노드를 UI 카드로 매핑한다.

```python
# 백엔드 그래프
class State(MessagesState):
    classification: str
    research: str
    analysis: str
    synthesis: str

graph = StateGraph(State)
graph.add_node("classify", classify_node)
graph.add_node("do_research", research_node)
# ... 순차 엣지
app = graph.compile()
```

```ts
// 프론트엔드 (React)
import { useStream } from "@langchain/react";

function Pipeline() {
  const stream = useStream<typeof graph>({
    apiUrl: "http://localhost:2024",
    assistantId: "pipeline",
  });
  const classification = stream.values?.classification;
  const graphNodes = [...stream.subgraphs.values()];
}
```

`useStream`(Angular은 `injectStream`)은 `stream.subgraphs`(노드 발견)와 `useMessages(stream, node)`
(노드 범위 스트리밍 콘텐츠) 같은 셀렉터를 노출. `stream.values`는 전체 그래프 상태(최종 `synthesis` 등).

## 채팅 스트림과 다른 점

커스텀 그래프는 제품 워크플로우(리서치 파이프라인, 승인 흐름, 데이터 파이프라인, 코드 리뷰, 계획,
다단계 분석)를 구동한다. 그래프 네이티브 신호로 렌더링 :

| 런타임 개념 | 프론트엔드 UX |
|---|---|
| **명명된 노드** | 노드당 카드/타임라인 스텝/상태 배지 |
| **상태 키** | 타입드 출력별 전용 UI 영역(classification, sources, analysis, synthesis) |
| **스트리밍 메타데이터** | 부분 메시지를 생산 노드로 라우팅 |
| **체크포인트** | 이전 상태 검사·재개(디버그·감사) |
| **Interrupts** | 노드 정지 후 사람 입력·승인·교정 → 계속 |
| **서브그래프** | 사용자가 더 필요할 때만 중첩 실행 노출 |

백엔드 프로토콜 변경 없이 단순 채팅 패널 → 전체 워크플로우 디버거로 확장 가능.

## 패턴

- **Graph execution** : 노드별 상태·스트리밍으로 다단계 파이프라인 시각화 → `frontend-graph-execution.md`
- **Custom stream channels** : 커스텀 서버 데이터를 `useExtension`/`useChannel`로 읽기 → `frontend-custom-stream-channels.md`

> LangChain 프론트엔드 패턴(markdown 메시지, 도구 호출, HITL, resumable 스트림, time travel)은 어떤
> LangGraph 그래프와도 동작한다. `createAgent`/`createDeepAgent`/커스텀 `StateGraph` 모두 같은 데이터 모델.
