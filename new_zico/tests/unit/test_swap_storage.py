from importlib import reload

import pytest


@pytest.fixture
def swap_repository(tmp_path, monkeypatch):
    monkeypatch.setenv("SWAP_STATE_PATH", str(tmp_path / "swap_state.json"))
    import src.agents.swap.storage as storage

    storage.SwapStateRepository.reset()
    storage = reload(storage)
    storage.SwapStateRepository.reset()
    repo = storage.SwapStateRepository.instance()
    try:
        yield repo
    finally:
        storage.SwapStateRepository.reset()


def test_persist_and_history(swap_repository):
    repo = swap_repository
    intent = {
        "user_id": "user-1",
        "conversation_id": "conv-1",
        "from_network": "avalanche",
        "from_token": "AVAX",
        "to_network": "ethereum",
        "to_token": "USDC",
        "amount": "10",
        "updated_at": 0.0,
    }
    pending_meta = {
        "event": "swap_intent_pending",
        "status": "collecting",
        "user_id": "user-1",
        "conversation_id": "conv-1",
    }

    history = repo.persist_intent(
        "user-1",
        "conv-1",
        intent,
        pending_meta,
        done=False,
        summary=None,
    )
    assert history == []
    stored = repo.load_intent("user-1", "conv-1")
    assert stored["from_network"] == "avalanche"

    ready_meta = pending_meta | {"event": "swap_intent_ready", "status": "ready"}
    summary = {
        "status": "ready",
        "from_network": "avalanche",
        "from_token": "AVAX",
        "to_network": "ethereum",
        "to_token": "USDC",
        "amount": "10",
    }

    history = repo.persist_intent(
        "user-1",
        "conv-1",
        intent,
        ready_meta,
        done=True,
        summary=summary,
    )
    assert repo.load_intent("user-1", "conv-1") is None
    assert history
    assert history[0]["status"] == "ready"
    assert history[0]["from_token"] == "AVAX"
