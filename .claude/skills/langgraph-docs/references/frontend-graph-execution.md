# Frontend: Graph Execution

원문 : https://docs.langchain.com/oss/python/langgraph/frontend/graph-execution

명명된 노드(classify, research, analyze, synthesize)로 구성된 다단계 파이프라인을 노드별 카드로
시각화한다. 각 카드가 상태를 표시하고 콘텐츠를 실시간 스트리밍하며 전체 워크플로우 완료를 추적.
run을 단일 어시스턴트 응답으로 보지 않고, LangGraph가 내부적으로 쓰는 체크포인트·노드명·상태 키·
스트림 메타데이터를 그대로 노출한다.

## 노드→UI 카드 매핑

각 노드는 특정 상태 키에 출력을 쓴다. 프론트엔드는 매핑을 하드코딩하지 않는다 — `useStream`이 실행
중 `stream.subgraphs`로 각 노드를 자동 발견하고 관찰된 스텝마다 `SubgraphDiscoverySnapshot`을 노출한다.

```ts
const graphNodes = [...stream.subgraphs.values()];   // 자동 발견, 하드코딩 불필요
graphNodes.forEach((node) => {
  console.log(node.nodeName, node.status);   // "classify", "running"
});
```

`node.nodeName`은 진행바·카드 헤더 레이블. 각 스냅샷을 `useMessages(stream, node)`에 넘기면 상태 키
이름에 결합하지 않고 노드 범위 스트리밍 콘텐츠를 렌더링한다.

## useStream 설정

```tsx
import { useStream } from "@langchain/react";

export function PipelineChat() {
  const stream = useStream<typeof myAgent>({
    apiUrl: "http://localhost:2024",
    assistantId: "graph_execution_cards",
  });
  const graphNodes = [...stream.subgraphs.values()];
  return (
    <div>
      <PipelineProgress nodes={graphNodes} isLoading={stream.isLoading} />
      <NodeCardList nodes={graphNodes} stream={stream} isLoading={stream.isLoading} />
    </div>
  );
}
```

(Vue `useStream`, Svelte `useStream`, Angular `injectStream` 동일 형태)

## 스트리밍 토큰을 노드로 라우팅

```tsx
import { useMessages, type SubgraphDiscoverySnapshot } from "@langchain/react";

function NodeCard({ node, stream }) {
  const messages = useMessages(stream, node);
  const lastAIMessage = messages.find(AIMessage.isInstance);
  const streamingContent = lastAIMessage?.text ?? "";
  return <NodeCardBody node={node} content={streamingContent} />;
}
```

첫 마운트된 셀렉터가 그 노드 네임스페이스에 범위 구독을 연다. 카드 언마운트 시 자동 해제.

## 노드 상태

`node.status`는 `"pending"` / `"running"` / `"complete"` / `"error"`.

## 스트리밍 vs 완료 콘텐츠

| 소스 | 사용 시점 |
|---|---|
| `useMessages(stream, node)` | 노드 범위 스트리밍·최종 메시지 (상태 키 이름과 분리) |
| `stream.values` | 전체 그래프 상태(최종 `synthesis` 등), 실제 상태 키로 읽기 |

노드명이 상태 키와 같다고 가정하지 않는다(예: `do_research` 노드가 `research` 키에 씀). 범위 메시지가
생산 노드에 묶이므로 메시지 순서 추측 없이 병렬 경로를 지원한다.

> 스트리밍 콘텐츠는 부분 토큰·미완성 markdown을 포함할 수 있다. 렌더러가 미완성 문법(닫히지 않은 `**` 등)을 우아하게 처리해야 함.

## 동적 파이프라인

`stream.subgraphs`는 현재 스레드에서 관찰된 노드만 담는다. 조건부 분기로 건너뛴 노드는 나타나지
않으므로 빈 placeholder 카드를 피한다.

## 베스트 프랙티스

- 스트림에서 노드 발견(`stream.subgraphs`) — 예상 노드 하드코딩 금지.
- 상태 키를 UI 계약으로 취급 — 안정적 키를 그래프 정의 옆에 문서화.
- 노드 카드엔 범위 메시지 사용(스트리밍 중·완료 후 모두 동작).
- 완료 노드 자동 접기, 추정 시간 표시, 전역 진행 표시기 추가.
- 노드별 에러 처리 — 한 노드 실패 시 전체 파이프라인 접지 말고 해당 카드에 에러 표시.
