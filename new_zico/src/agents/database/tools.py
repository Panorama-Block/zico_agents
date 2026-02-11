from langchain_core.messages.tool import ToolCall
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool, BaseTool
from src.agents.database.client import get_client
import requests
from src.agents.database.config import Config

@tool(parse_docstring=True)
def list_tables(reasoning: str) -> list[str]:
    """
    List all tables in the database.

    Args:
        reasoning: A string with the reasoning for the tool call

    Returns:
        A list of table names
    """
    print("reasoning:", reasoning)
    client = get_client()
    result = client.query("SHOW TABLES")
    response = result.result_rows
    print("response:", response)
    return response

@tool(parse_docstring=True)
def sample_table(reasoning: str, table_name: str) -> str:
    """
    Sample the data from a table.

    Args:
        reasoning: A string with the reasoning for the tool call
        table_name: The name of the table to sample

    Returns:
        A string with the sampled data
    """
    print("reasoning:", reasoning)
    client = get_client()
    result = client.query(f"SELECT * FROM {table_name} LIMIT 10")
    response = result.result_rows
    print("response:", response)
    return response

@tool(parse_docstring=True)
def describe_table(reasoning: str, table_name: str) -> str:
    """
    Describe the schema of a table.

    Args:
        reasoning: A string with the reasoning for the tool call
        table_name: The name of the table to describe

    Returns:
        A string with the schema of the table
    """
    print("reasoning:", reasoning)
    client = get_client()
    result = client.query(f"DESCRIBE TABLE {table_name}")
    response = result.result_rows
    print("response:", response)
    return response

@tool(parse_docstring=True)
def execute_sql(reasoning: str, sql: str) -> str:
    """
    Execute a SQL query and return the result.

    Args:
        reasoning: A string with the reasoning for the tool call
        sql: The SQL query to execute

    Returns:
        A string with the result of the query
    """
    print("reasoning: ", reasoning)
    client = get_client()
    result = client.query(sql)
    response = result.result_rows
    print("response:", response)
    return response

@tool(parse_docstring=True)
def get_recent_transactions(reasoning: str, blockchainId: str = "c-chain") -> str:
    """
    Get the recent transactions from the AVAX blockchain database.

    Args:
        reasoning: A string with the reasoning for the tool call
        blockchainId: The blockchain ID to get the transactions from (default: c-chain)

    Returns:
        A string with the recent transactions
    """
    print("reasoning: ", reasoning)
    network = "mainnet"
    url = f"https://glacier-api.avax.network/v1/networks/{network}/blockchains/{blockchainId}/transactions"

    headers = {"x-glacier-api-key": Config.GLACIER_API_KEY}

    response = requests.get(url, headers=headers)

    print("response: ", response.json())
    return str(response.json())

@tool(parse_docstring=True)
def get_recent_active_addresses(reasoning: str, blockchainId: str = "c-chain") -> str:
    """
    Get the recent active addresses from the AVAX blockchain database.

    Args:
        reasoning: A string with the reasoning for the tool call
        blockchainId: The blockchain ID to get the active addresses from (default: c-chain)

    Returns:
        A string with the recent transactions and active addresses
    """
    print("reasoning: ", reasoning)
    network = "mainnet"
    url = f"https://glacier-api.avax.network/v1/networks/{network}/blockchains/{blockchainId}/transactions"
    headers = {"x-glacier-api-key": Config.GLACIER_API_KEY}
    response = requests.get(url, headers=headers)
    print("response: ", response.json())
    return str(response.json())

@tool(parse_docstring=True)
def get_network_info(reasoning: str) -> str:
    """
    Gets AVAX mainnet network details such as validator and delegator stats.

    Args:
        reasoning: A string with the reasoning for the tool call

    Returns:
        A string with the network details
    """
    print("reasoning: ", reasoning)
    network = "mainnet"
    url = f"https://glacier-api.avax.network/v1/networks/{network}"
    headers = {"x-glacier-api-key": Config.GLACIER_API_KEY}
    response = requests.get(url, headers=headers)
    print("response: ", response.json())
    return str(response.json())

@tool(parse_docstring=True)
def get_total_active_addresses(reasoning: str, ) -> str:
    """
    Gets the total active addresses from the AVAX network. Use this tool to get the total number of active addresses on the network.

    Args:
        reasoning: A string with the reasoning for the tool call

    Returns:
        A string with the cumulative active addresses
    """
    print("reasoning: ", reasoning)
    chainId = "total"
    metric = "cumulativeAddresses"
    url = f"https://metrics.avax.network/v2/chains/{chainId}/metrics/{metric}"
    headers = {"x-glacier-api-key": Config.GLACIER_API_KEY}
    response = requests.get(url, headers=headers)
    print("response: ", response.json())
    return str(response.json())

def get_tools() -> list[BaseTool]:
    """
    Build and return the list of LangChain Tools for use in an agent.

    Each Tool wraps one of the user-facing helper functions above.
    """

    return [list_tables, sample_table, describe_table, execute_sql, get_recent_transactions, get_recent_active_addresses, get_network_info, get_total_active_addresses]

def call_tool(tool_call: ToolCall) -> any:
    print(tool_call)
    tools_by_name = {tool.name: tool for tool in get_tools()}
    tool = tools_by_name[tool_call["name"]]
    response = tool.invoke(tool_call["args"])
    return ToolMessage(content=response, tool_call_id=tool_call["id"])
