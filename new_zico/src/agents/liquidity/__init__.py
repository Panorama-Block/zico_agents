"""Liquidity agent — speaks the `liquidity` capability vocabulary (add/remove LP, claim rewards).

Provider selection per chain is owned by the backend's `liquidity-service` registry. The agent
never names a provider in user-facing text — see `new_zico/docs/agent-capability-contract.md`
§3 (HARD output rules).
"""
