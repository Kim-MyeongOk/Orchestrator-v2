from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware

from common.security.auth_token_helper import AuthTokenHelper

##################################################
# 인증 토큰 자동 연장 미들웨어 (Silent Refresh)
#
# 인증된 요청이 지나갈 때 토큰의 남은 수명을 보고, 절반 아래로 떨어졌으면
# 새 토큰을 만들어 X-Refreshed-Auth-Token 응답 헤더로 함께 내려준다.
# 프론트는 이 헤더가 오면 저장된 토큰을 조용히 갈아끼운다 → 쓰는 동안에는 로그아웃되지 않는다.
#
# 별도의 Refresh Token 을 두지 않는 이유 :
#   이 서비스의 토큰은 서명만으로 검증하는 무상태 토큰이고, Access/Refresh 를 나눠도
#   둘 다 같은 localStorage 에 놓이므로 탈취 위험이 줄지 않는다. 반면 갱신 엔드포인트·회전·폐기
#   관리가 새로 생긴다. "쓰는 동안 만료되지 않게 한다"는 목적에는 슬라이딩 갱신으로 충분하다.
##################################################
class AuthTokenRenewalMiddleware(BaseHTTPMiddleware):
    REFRESHED_TOKEN_HEADER_NAME = "X-Refreshed-Auth-Token"
    AUTHORIZATION_PREFIX        = "Bearer "

    def __init__(self, application, secret : str, ttl_second_count : int, renewal_ratio : float = 0.5) -> None:
        super().__init__(application)
        self.secret           = secret
        self.ttl_second_count = ttl_second_count
        # 남은 수명이 전체의 이 비율 아래로 내려가면 갱신한다 (기본 0.5 = 절반)
        self.renewal_ratio    = renewal_ratio

    @staticmethod
    def _extract_bearer_token(authorization_header : Optional[str]) -> Optional[str]:
        if not authorization_header:
            return None
        if not authorization_header.startswith(AuthTokenRenewalMiddleware.AUTHORIZATION_PREFIX):
            return None
        token = authorization_header[len(AuthTokenRenewalMiddleware.AUTHORIZATION_PREFIX):].strip()
        return token or None

    def _build_refreshed_token(self, token : str) -> Optional[str]:
        # 아직 유효하고 남은 수명이 기준 아래인 토큰만 새로 발급한다.
        # 이미 만료된 토큰은 여기서 되살리지 않는다 — 그러면 만료가 사실상 무한정 미뤄진다.
        remaining_second_count = AuthTokenHelper.read_remaining_second_count(token, self.secret)
        if remaining_second_count is None:
            return None
        if remaining_second_count > self.ttl_second_count * self.renewal_ratio:
            return None
        user_id = AuthTokenHelper.verify_token(token, self.secret)
        if not user_id:
            return None
        return AuthTokenHelper.create_token(user_id, self.secret, self.ttl_second_count)

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # 갱신 실패가 본 요청을 망치면 안 된다 (응답은 이미 만들어져 있다)
        try:
            token = AuthTokenRenewalMiddleware._extract_bearer_token(request.headers.get("authorization"))
            if token:
                refreshed_token = self._build_refreshed_token(token)
                if refreshed_token:
                    response.headers[AuthTokenRenewalMiddleware.REFRESHED_TOKEN_HEADER_NAME] = refreshed_token
        except Exception as exception:
            print(f"AUTH TOKEN RENEWAL SKIPPED : {exception}", flush = True)
        return response
