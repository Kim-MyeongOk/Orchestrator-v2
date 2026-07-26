from dataclasses             import dataclass
from typing                  import List
from typing                  import Dict
from typing                  import Any
from typing                  import Optional
from dataclasses             import field
from langchain_core.messages import BaseMessage

@dataclass(frozen = True, slots = True)
class NormalizedChunk:
    sequence          : int                                                     # 실행 내 단조 증가 시퀀스 (SSE id / Last-Event-ID 기준)
    chunk_type        : str                                                     # tasks | messages | custom
    namespace_list    : List[str]                                               # 네임스페이스 경로 리스트 ([] = 메인 에이전트)
    namespace_path    : str                                                     # ns_list의 '/' 결합 ('' = 메인 에이전트)
    data_dictionary   : Dict[str, Any]                                          # JSON 직렬화 가능한 정규화 데이터
    created_at        : str                                                     # 생성 시각 (ISO8601 UTC)
    task_id           : Optional[str]         = field(default = None          ) # 현재 LangGraph task id
    parent_task_id    : Optional[str]         = field(default = None          ) # 부모 LangGraph task id
    task_link_type    : Optional[str]         = field(default = None          ) # explicit | metadata | namespace | inferred | unassigned
    stream_version    : str                   = field(default = "langgraph-v2") # 스트림 계약 버전
    schema_version    : int                   = field(default = 1             ) # 저장 schema 버전
    projection_status : str                   = field(default = "pending"     ) # projection 처리 상태
    message           : Optional[BaseMessage] = field(default = None          ) # 병합용 원본 메시지 객체 (직렬화 제외)
