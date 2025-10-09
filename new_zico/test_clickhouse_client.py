import clickhouse_connect

CLICKHOUSE_HOST = 'localhost'
CLICKHOUSE_PORT = 8123  # HTTP port
CLICKHOUSE_USER = 'default'
CLICKHOUSE_PASSWORD = ''
CLICKHOUSE_DATABASE = 'default'

# Initialize the client
client = clickhouse_connect.get_client(
    host=CLICKHOUSE_HOST,
    port=CLICKHOUSE_PORT,
    username=CLICKHOUSE_USER,
    password=CLICKHOUSE_PASSWORD,
    database=CLICKHOUSE_DATABASE
)

# Define your SQL query
sql_query = """SELECT "chain_id", "name" FROM "chains" LIMIT 5"""

# Execute the query
result = client.query(sql_query)

# Print the result
print("Query result:", result.result_rows)