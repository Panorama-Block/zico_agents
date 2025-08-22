from langchain_core.tools import tool
from src.agents.metadata import metadata
from src.agents.swap.config import SwapConfig

@tool
def swap_avax(amount: float, from_token: str, to_token: str):
    """
    Swap AVAX for a given amount of tokens

    Args:
        amount: The amount of tokens to swap
        from_token: The token to swap from
        to_token: The token to swap to

    Returns:
        The amount of tokens received
    """
    try:
        canonical_from = SwapConfig.validate_or_raise(from_token)
        canonical_to = SwapConfig.validate_or_raise(to_token)
    except ValueError as e:
        return str(e)

    print(f"Swapping {amount} {canonical_from} for {canonical_to}")
    meta = {
        "from_token": canonical_from,
        "to_token": canonical_to,
        "amount": amount
    }
    metadata.set_swap_agent(meta)
    return f'Swapped {amount} {canonical_from} for {canonical_to}'

@tool
def get_avaialble_tokens():
    """
    Get the available tokens for swapping
    """
    return SwapConfig.list_supported()

@tool
def default_response():
    """
    Normal response when the user asks for a swap
    """
    return f'What would you like to swap? The available agents are{SwapConfig.list_supported}'


def get_tools():
    return [swap_avax, get_avaialble_tokens, default_response]