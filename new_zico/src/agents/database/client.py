import clickhouse_connect
from src.agents.database.config import Config

_client = None

def _create_client():
    return clickhouse_connect.get_client(
        host=Config.CLICKHOUSE_HOST,
        port=Config.CLICKHOUSE_PORT,
        username=Config.CLICKHOUSE_USER,
        password=Config.CLICKHOUSE_PASSWORD,
        database=Config.CLICKHOUSE_DATABASE
    )

def get_client():
    global _client
    if _client is None:
        _client = _create_client()
    return _client

def try_get_client():
    try:
        return get_client()
    except Exception:
        return None

def is_database_available() -> bool:
    try:
        client = get_client()
        client.query("SELECT 1")
        return True
    except Exception:
        return False

def execute_query(query: str):
    return get_client().query(query)
