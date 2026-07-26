import os
import secrets

from typing import Optional

##################################################
# 인증 비밀키 헬퍼
# 토큰 서명용 비밀키를 "서버를 재시작해도 같은 값"으로 유지한다.
#
# 매 기동마다 새 비밀키를 만들면 이전에 발급한 토큰이 전부 서명 검증에 실패해
# 사용자는 재시작할 때마다 로그아웃된다 (개발 중 코드 저장으로 리로드될 때마다 튕기는 원인).
#
# 우선순위 : 환경변수(AUTH_TOKEN_SECRET) > 로컬 비밀키 파일 > 새로 만들어 파일에 저장
#   - 운영    : 환경변수로 주입한다 (여러 인스턴스가 같은 키를 써야 하므로 파일 방식은 부적합)
#   - 개발    : 파일에 한 번 만들어 두고 계속 재사용한다 (별도 설정 없이도 로그인이 유지된다)
##################################################
class AuthSecretHelper:
    SECRET_BYTE_COUNT = 32   # token_hex 입력 바이트 수 (결과는 64자 16진 문자열)

    @staticmethod
    def _read_secret_file(secret_file_path : str) -> Optional[str]:
        # 파일이 없거나 비어 있거나 읽을 수 없으면 None (호출부가 새로 만든다)
        try:
            if not os.path.exists(secret_file_path):
                return None
            with open(secret_file_path, "r", encoding = "utf-8") as secret_file:
                stored_secret = secret_file.read().strip()
            return stored_secret or None
        except OSError:
            return None

    @staticmethod
    def _write_secret_file(secret_file_path : str, secret : str) -> bool:
        # 저장에 실패해도 서버 기동을 막지 않는다 (이번 프로세스 동안은 메모리의 값으로 동작한다)
        try:
            directory_path = os.path.dirname(secret_file_path)
            if directory_path:
                os.makedirs(directory_path, exist_ok = True)
            with open(secret_file_path, "w", encoding = "utf-8") as secret_file:
                secret_file.write(secret)
            return True
        except OSError:
            return False

    @staticmethod
    def resolve_secret(environment_secret : Optional[str], secret_file_path : str) -> str:
        # 환경변수가 있으면 그대로 쓴다 (운영 경로)
        trimmed_environment_secret = (environment_secret or "").strip()
        if trimmed_environment_secret:
            return trimmed_environment_secret

        # 이전 기동에서 만들어 둔 파일이 있으면 재사용한다 → 재시작해도 토큰이 살아 있다
        stored_secret = AuthSecretHelper._read_secret_file(secret_file_path)
        if stored_secret:
            print(f"AUTH TOKEN SECRET LOADED FROM FILE : {secret_file_path}", flush = True)
            return stored_secret

        # 최초 1회 : 새로 만들어 파일에 남긴다
        generated_secret = secrets.token_hex(AuthSecretHelper.SECRET_BYTE_COUNT)
        if AuthSecretHelper._write_secret_file(secret_file_path, generated_secret):
            print(f"AUTH TOKEN SECRET GENERATED AND SAVED : {secret_file_path}", flush = True)
        else:
            print(f"WARNING : AUTH TOKEN SECRET FILE WRITE FAILED : {secret_file_path} - "
                  f"TOKENS WILL INVALIDATE ON RESTART", flush = True)
        return generated_secret
