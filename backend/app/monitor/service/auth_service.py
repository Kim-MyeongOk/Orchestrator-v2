##################################################
# 인증 서비스 (사용자 등록 / 로그인 / 토큰 검증 / 스레드 소유권)
#
# 토큰은 무상태 HMAC 서명 방식이라 별도 세션 저장소가 없다.
# 비밀키가 바뀌면 발급해 둔 토큰이 전부 검증에 실패하므로 AuthSecretHelper 로 고정 값을 확보해 주입받는다.
##################################################

from typing import Any
from typing import Dict
from typing import Optional

from fastapi import HTTPException

from app.auth.user_repository              import UserRepository
from app.monitor.api.login_request         import LoginRequest
from app.monitor.api.register_request      import RegisterRequest
from common.security.auth_token_helper     import AuthTokenHelper
from common.security.password_helper       import PasswordHelper


class AuthService:
    AUTHORIZATION_PREFIX     = "Bearer "
    MINIMUM_PASSWORD_LENGTH  = 4
    DUPLICATE_USER_MESSAGE   = "이미 등록된 유저입니다."   # 회원가입 중복 ID 안내 (409 응답 본문에 그대로 실린다)

    def __init__(self,
                 user_repository            : UserRepository,
                 checkpoint_connection_pool : Any,
                 token_secret               : str,
                 token_ttl_second_count     : int) -> None:
        self.user_repository            = user_repository
        self.checkpoint_connection_pool = checkpoint_connection_pool
        self.token_secret               = token_secret
        self.token_ttl_second_count     = token_ttl_second_count

    ##################################################
    # 토큰
    ##################################################

    def issue_token(self, user_id : str) -> str:
        return AuthTokenHelper.create_token(user_id, self.token_secret, self.token_ttl_second_count)

    def require_authenticated_user_id(self, authorization : Optional[str]) -> str:
        # Authorization: Bearer <token> 를 검증하고 인증된 user_id 를 반환한다 (없거나 무효면 401)
        if not authorization or not authorization.startswith(AuthService.AUTHORIZATION_PREFIX):
            raise HTTPException(status_code = 401, detail = "AUTHENTICATION REQUIRED")
        token   = authorization[len(AuthService.AUTHORIZATION_PREFIX):].strip()
        user_id = AuthTokenHelper.verify_token(token, self.token_secret)
        if user_id is None:
            raise HTTPException(status_code = 401, detail = "INVALID OR EXPIRED TOKEN")
        return user_id

    async def assert_thread_accessible_async(self, user_id : str, thread_id : str) -> None:
        # 스레드 소유권 검증 : 다른 사용자가 소유(chat_room)한 thread_id 면 403.
        # 미등록(신규) 스레드나 본인 소유 스레드는 허용한다.
        async with self.checkpoint_connection_pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT 1 FROM chat_room WHERE thread_id = %s AND user_id <> %s LIMIT 1", (thread_id, user_id))
            if await cursor.fetchone() is not None:
                raise HTTPException(status_code = 403, detail = "THREAD ACCESS DENIED")

    ##################################################
    # 라우트 핸들러
    ##################################################

    async def register_user_async(self, register_request : RegisterRequest) -> Dict[str, Any]:
        # 신규 사용자 등록 : user_id 중복이면 409, 유효성 실패면 400. 성공 시 인증 토큰 발급
        user_id  = register_request.user_id.strip()
        password = register_request.password
        if not user_id or not password:
            raise HTTPException(status_code = 400, detail = "USER ID AND PASSWORD ARE REQUIRED")
        if len(password) < AuthService.MINIMUM_PASSWORD_LENGTH:
            raise HTTPException(status_code = 400, detail = "PASSWORD TOO SHORT : MINIMUM 4 CHARACTERS")

        password_hash = PasswordHelper.hash_password(password)
        is_created    = await self.user_repository.create_user_async(user_id, password_hash)
        if not is_created:
            # 화면에 그대로 띄우는 문구라 한국어로 내려준다 (다른 오류 메시지는 개발자용이라 영어를 유지).
            # 응답에 user_id 를 되싣지 않는다 — 아무나 가입 API 를 두드려 계정 존재 여부를 확인할 수 있게 되기 때문.
            raise HTTPException(status_code = 409, detail = AuthService.DUPLICATE_USER_MESSAGE)
        return {"user_id" : user_id, "token" : self.issue_token(user_id), "status" : "registered"}

    async def login_user_async(self, login_request : LoginRequest) -> Dict[str, Any]:
        # 로그인 검증 : user_id 없음/비밀번호 불일치는 동일하게 401 (계정 존재 여부 노출 방지). 성공 시 인증 토큰 발급
        user_id     = login_request.user_id.strip()
        stored_hash = await self.user_repository.get_password_hash_async(user_id)
        if stored_hash is None or not PasswordHelper.verify_password(login_request.password, stored_hash):
            raise HTTPException(status_code = 401, detail = "INVALID USER ID OR PASSWORD")
        return {"user_id" : user_id, "token" : self.issue_token(user_id), "status" : "ok"}
