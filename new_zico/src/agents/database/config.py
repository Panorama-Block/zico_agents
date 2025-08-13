import os

class Config:
    # Use clickhouse+http:// for HTTP interface or clickhouse+native:// for native interface
    CLICKHOUSE_URI = "clickhouse+http://default:@localhost:8123/default"
    
    CLICKHOUSE_HOST = 'localhost'
    CLICKHOUSE_PORT = 8123  # HTTP port
    CLICKHOUSE_USER = 'default'
    CLICKHOUSE_PASSWORD = ''
    CLICKHOUSE_DATABASE = 'default'
    # Alternative native connection (faster, recommended for production)
    # CLICKHOUSE_URI = "clickhouse+native://default:@localhost:9000/default"
    GLACIER_API_KEY = os.getenv("GLACIER_API_KEY")