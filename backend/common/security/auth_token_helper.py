import time
import json
import hmac
import base64
import hashlib

from typing import Optional

##################################################
# 인증 토큰 헬퍼
# HMAC-SHA256 서명 기반 무상태 토큰을 발급/검증한다 (외부 의존성 없이 stdlib 만 사용).
# 형식 : base64url(payload_json).base64url(signature)  — payload : {"user_id", "exp"}
# 서버 비밀키로 서명하므로 위조 불가하며, 별도 세션 저장소가 필요 없다.
##################################################
class AuthTokenHelper:
    @staticmethod
    def _base64url_encode(raw_bytes : bytes) -> str:
        return base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode("ascii")

    @staticmethod
    def _base64url_decode(encoded_text : str) -> bytes:
        padding_length = (-len(encoded_text)) % 4
        return base64.urlsafe_b64decode(encoded_text + ("=" * padding_length))

    @staticmethod
    def _sign(payload_segment : str, secret : str) -> str:
        signature_bytes = hmac.new(secret.encode("utf-8"), payload_segment.encode("ascii"), hashlib.sha256).digest()
        return AuthTokenHelper._base64url_encode(signature_bytes)

    @staticmethod
    def create_token(user_id : str, secret : str, ttl_second_count : int) -> str:
        payload_dictionary = {"user_id" : user_id, "exp" : int(time.time()) + ttl_second_count}
        payload_segment    = AuthTokenHelper._base64url_encode(json.dumps(payload_dictionary, separators = (",", ":")).encode("utf-8"))
        signature_segment  = AuthTokenHelper._sign(payload_segment, secret)
        return f"{payload_segment}.{signature_segment}"

    @staticmethod
    def _read_verified_payload(token : str, secret : str) -> Optional[dict]:
        # 서명·형식을 검증하고 payload 를 돌려준다 (만료 여부는 판단하지 않는다). 무효면 None.
        if not isinstance(token, str) or token.count(".") != 1:
            return None
        payload_segment, signature_segment = token.split(".")
        expected_signature = AuthTokenHelper._sign(payload_segment, secret)
        if not hmac.compare_digest(expected_signature, signature_segment):
            return None
        try:
            return json.loads(AuthTokenHelper._base64url_decode(payload_segment))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def read_remaining_second_count(token : str, secret : str) -> Optional[int]:
        # 남은 유효 시간(초). 무효·만료 토큰은 None — 슬라이딩 갱신 시점을 판단하는 데 쓴다.
        payload_dictionary = AuthTokenHelper._read_verified_payload(token, secret)
        if payload_dictionary is None:
            return None
        remaining_second_count = int(payload_dictionary.get("exp", 0)) - int(time.time())
        return remaining_second_count if remaining_second_count > 0 else None

    @staticmethod
    def verify_token(token : str, secret : str) -> Optional[str]:
        # 서명·만료를 검증하고 user_id 를 반환한다. 무효/만료/형식오류는 None.
        if not isinstance(token, str) or token.count(".") != 1:
            return None
        payload_segment, signature_segment = token.split(".")
        expected_signature = AuthTokenHelper._sign(payload_segment, secret)
        if not hmac.compare_digest(expected_signature, signature_segment):
            return None
        try:
            payload_dictionary = json.loads(AuthTokenHelper._base64url_decode(payload_segment))
        except (ValueError, TypeError):
            return None
        if int(payload_dictionary.get("exp", 0)) < int(time.time()):
            return None
        user_id = payload_dictionary.get("user_id")
        return user_id if isinstance(user_id, str) and user_id else None
