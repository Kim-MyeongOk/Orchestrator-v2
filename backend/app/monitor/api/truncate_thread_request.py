from pydantic import BaseModel


class TruncateThreadRequest(BaseModel):
    # 유지할 사용자 메시지 개수. 그 다음 사용자 메시지부터 이후 전부를 체크포인트에서 제거한다.
    # (특정 질문을 수정해 그 지점부터 대화를 다시 이어갈 때 사용)
    #
    # 개수 기준인 이유 : 실패/중단된 턴은 프론트 목록에는 남지만 체크포인트에는 기록되지 않아
    # 양쪽 순번이 어긋난다. 개수 기준이면 어긋나도 "제거할 것 없음"으로 안전하게 끝난다.
    keep_human_message_count : int
