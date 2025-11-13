"""DCA agent package exposing helper factories."""

from __future__ import annotations

__all__ = ["DcaAgent", "get_tools"]


def __getattr__(name: str):
    if name == "DcaAgent":
        from .agent import DcaAgent as _DcaAgent

        return _DcaAgent
    if name == "get_tools":
        from .tools import get_tools as _get_tools

        return _get_tools
    raise AttributeError(name)
