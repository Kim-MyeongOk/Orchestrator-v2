# Frontend: Custom Stream Channels

원문 : https://docs.langchain.com/oss/python/langgraph/frontend/custom-stream-channels

에이전트는 메시지·도구 호출 외에도 스트리밍할 수 있다. 서버측 **stream transformer**가 클라이언트로
흐르는 프로토콜을 검사·재작성하고, 명명된 **custom channel**에 자체 구조화 데이터를 발행한다.
프론트엔드는 두 셀렉터로 읽는다 : `useExtension`(최신 페이로드), `useChannel`(원시 이벤트 escape hatch).

예시 : 고객 지원 에이전트의 transformer가 모든 이벤트에서 PII(이메일·전화·SSN·카드번호·IP)를 브라우저
도달 전 레닥션하고, `redaction-stats` 채널에 누적 카운트를 발행한다. 사이드 패널이 실시간 렌더링.

> **stream transformer와 `StreamChannel`은 langgraph>=1.2 필요.**

## 동작 원리

custom channel은 양 끝을 가진다. 서버에서 `StreamTransformer`가 명명된 `StreamChannel`을 열고
페이로드를 push. 클라이언트에서 셀렉터가 매칭되는 `custom:<name>` 채널을 구독해 reactive 상태로 노출.

transformer의 `process` 메서드는 모든 프로토콜 이벤트에 대해 실행. 이벤트를 in-place로 변경(여기선
`messages`/`tools`/`values` 데이터에서 PII 제거)하고, 보고할 게 있을 때 side-channel 업데이트를 push.

```python
# 서버측 transformer (icodebroker의 Redis fan-out 스트리밍 인프라와 관련성 높음)
import time
from langgraph.stream import ProtocolEvent, StreamChannel, StreamTransformer

class RedactionStatsTransformer(StreamTransformer):
    def __init__(self, scope: tuple[str, ...] = ()) -> None:
        super().__init__(scope)
        self.redaction_stats = StreamChannel("redaction-stats")   # "redaction-stats" 채널 개방
        self.counts = empty_counts()

    def init(self) -> dict[str, StreamChannel]:
        return {"redactionStats": self.redaction_stats}

    def process(self, event: ProtocolEvent) -> bool:
        delta = redact_in_place(event, self.counts)   # event["params"]["data"] in-place 레닥션·집계
        if delta:
            self.redaction_stats.push({               # 채널에 페이로드 발행
                "kind": "update",
                "at": int(time.time() * 1000),
                "delta": delta,
                "counts": dict(self.counts),
                "total": sum(self.counts.values()),
            })
        return True   # (레닥션된) 이벤트를 스트림에 유지

def create_redaction_stats_transformer() -> RedactionStatsTransformer:
    return RedactionStatsTransformer()
```

```python
# 에이전트 빌드 시 transformer 부착
agent = create_agent(
    model="anthropic:claude-haiku-4-5",
    tools=[...],
    transformers=[create_redaction_stats_transformer],
)
```

클라이언트 페이로드 타입(transformer가 push하는 모양) :
```ts
type RedactionStatsEvent = {
  kind: "update";
  at: number;
  delta: Partial<Record<PiiType, number>>;
  counts: Record<PiiType, number>;
  total: number;
};
```

## useExtension — 최신 페이로드

`useExtension`은 `custom:<name>` 채널을 구독해 transformer가 push한 **가장 최근 페이로드**를 언래핑·타입된
형태로 반환. 라이브 카운터·진행률·상태 배지처럼 현재 값만 필요할 때 적합. **bare 채널명**(`custom:` 접두사 없이) 전달.

```tsx
import { useExtension } from "@langchain/react";
const latest = useExtension<RedactionStatsEvent>(stream, "redaction-stats");
// latest?.total, latest?.counts.email, latest?.delta
```

반환값은 프레임워크 reactivity를 따른다 : React/Svelte는 plain 값, Vue는 `Ref`(`latest.value`),
Angular는 signal(`latest()`). 첫 페이로드 전엔 `undefined`. 선택적 세 번째 `target` 인자로 네임스페이스 범위 지정(`useMessages(stream, node)`처럼).

## useChannel — 원시 이벤트 버퍼

`useChannel`은 raw-events escape hatch. 하나 이상 채널을 구독해 단일 언래핑 값 대신 프로토콜 이벤트의
**경계 버퍼**를 반환. 최신값이 아닌 이력(이벤트 로그·감사 추적)이나 상위 셀렉터가 안 다루는 채널이
필요할 때. **full 채널 id**(`custom:redaction-stats`) 전달.

```tsx
import { useChannel } from "@langchain/react";
const rawEvents = useChannel(stream, ["custom:redaction-stats"]);
```

각 엔트리는 raw 프로토콜 이벤트라 페이로드가 `event.params.data` 아래 있다. 직접 언래핑 :
```ts
function parseRedactionStatsEvents(rawEvents) {
  const out = [];
  for (const event of rawEvents) {
    const data = event.params?.data;
    const payload = data?.payload ?? data;
    if (payload?.kind === "update") out.push(payload);
  }
  return out;
}
```

버퍼 옵션(4번째 인자) :
```ts
const rawEvents = useChannel(stream, ["custom:redaction-stats"], undefined,
                             { bufferSize: 200, replay: true });
```

| 옵션 | 기본 | 효과 |
|---|---|---|
| `bufferSize` | `"default"` | 최대 버퍼 이벤트 수. 초과 시 오래된 것 드롭 |
| `replay` | `true` | 마운트 시 채널에서 이미 본 이벤트 재생(라이브만이 아니라) |

## 둘 중 선택

| | `useExtension` | `useChannel` |
|---|---|---|
| **반환** | 최신 페이로드(`T \| undefined`) | raw 이벤트 경계 버퍼(`Event[]`) |
| **모양** | 언래핑·타입됨 | raw 프로토콜 이벤트, `event.params.data` 직접 언래핑 |
| **구독 키** | 채널명(`"redaction-stats"`) | full id(`["custom:redaction-stats"]`) |
| **사용 시** | 현재 값 필요 | 이력·로그·다중 채널 |
| **옵션** | — | `bufferSize`, `replay` |

흔한 패턴 : 같은 채널에 둘 다 사용 — `useExtension`이 라이브 요약(현재 합계), `useChannel`이 스레드 전체
업데이트의 스크롤 이벤트 로그. (공통 케이스엔 상위 셀렉터 `useExtension`/`useMessages`/`useToolCalls`/`useValues` 선호)

## 사용 사례

메시지·도구 호출·그래프 상태에 깔끔히 매핑되지 않는 서버측 신호 : 컴플라이언스·레닥션 통계, 진행률
보고, 라이브 메트릭(토큰·지연·비용), 소스·인용(검색 문서를 사이드 패널로), 도메인 이벤트.
