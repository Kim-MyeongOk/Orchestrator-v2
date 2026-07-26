from dataclasses import dataclass


##################################################
# 대화 압축 설정
# 임계치와 보존 개수를 한곳에 모은다. 값을 바꾸면 압축 시점과 강도가 달라진다.
##################################################
@dataclass
class ContextCompressionConfiguration:
    recent_message_keep_count : int  = 10     # 원본 그대로 보낼 최근 메시지 개수 (기본값 : 10)
    trigger_message_count     : int  = 14     # 이 개수를 넘으면 압축을 시도한다 (기본값 : 14 = 보존 10 + 요약 대상 최소 4)
    trigger_token_count       : int  = 3000   # 메시지 개수가 적어도 토큰이 이만큼 넘으면 압축한다 (기본값 : 3000)
    summary_line_count        : int  = 4      # 요약문 목표 줄 수 (기본값 : 4)
    summary_maximum_token_count : int = 512   # 요약 생성 시 생성 상한 (기본값 : 512)
    is_enabled                : bool = True   # False 면 압축을 완전히 끈다 (기본값 : True)
