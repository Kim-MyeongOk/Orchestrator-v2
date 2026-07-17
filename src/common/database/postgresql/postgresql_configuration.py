from dataclasses import dataclass

@dataclass(frozen = True, slots = True)
class PostgresqlConfiguration:
    host                     : str = "localhost" # 호스트 (기본값 : localhost)
    port                     : int = 5432        # 포트 (기본값 : 5432)
    database_name            : str = "postgres"  # 데이터베이스명 (기본값 : postgres)
    user_name                : str = "postgres"  # 사용자명 (기본값 : postgres)
    password                 : str = "postgres"  # 비밀번호 (기본값 : postgres)
    minimum_connection_count : int = 1           # 최소 커넥션 수 (기본값 : 1)
    maximum_connection_count : int = 10          # 최대 커넥션 수 (기본값 : 10)
