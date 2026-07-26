import os
import hmac
import hashlib

##################################################
# 비밀번호 해시 헬퍼
# PBKDF2-HMAC-SHA256 으로 비밀번호를 해시/검증한다 (외부 의존성 없이 stdlib 만 사용).
# 저장 형식 : pbkdf2_sha256$<반복횟수>$<salt_hex>$<hash_hex>
##################################################
class PasswordHelper:
    ALGORITHM_NAME  = "pbkdf2_sha256"
    ITERATION_COUNT = 200000   # PBKDF2 반복 횟수 (기본값 : 200000)
    SALT_BYTE_COUNT = 16       # salt 바이트 수 (기본값 : 16)

    @staticmethod
    def hash_password(plain_password : str) -> str:
        salt_bytes    = os.urandom(PasswordHelper.SALT_BYTE_COUNT)
        derived_bytes = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt_bytes, PasswordHelper.ITERATION_COUNT)
        return f"{PasswordHelper.ALGORITHM_NAME}${PasswordHelper.ITERATION_COUNT}${salt_bytes.hex()}${derived_bytes.hex()}"

    @staticmethod
    def verify_password(plain_password : str, stored_hash : str) -> bool:
        # 저장된 해시와 입력 비밀번호를 상수 시간 비교로 검증한다 (형식 불일치는 False)
        if not isinstance(stored_hash, str):
            return False
        stored_part_list = stored_hash.split("$")
        if len(stored_part_list) != 4:
            return False
        algorithm_name, iteration_text, salt_hex, hash_hex = stored_part_list
        if algorithm_name != PasswordHelper.ALGORITHM_NAME:
            return False
        try:
            derived_bytes = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), bytes.fromhex(salt_hex), int(iteration_text))
        except (ValueError, TypeError):
            return False
        return hmac.compare_digest(derived_bytes.hex(), hash_hex)
