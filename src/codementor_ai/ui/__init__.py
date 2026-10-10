"""Gradio IDE for CodeMentor AI.

Gradio is imported only when the IDE is built or launched, so the command-line workflow
starts without loading it.
"""

from __future__ import annotations

from typing import Any


def create_app(*args: Any, **kwargs: Any) -> Any:
    from .app import create_app as _create_app

    return _create_app(*args, **kwargs)


def launch(*args: Any, **kwargs: Any) -> None:
    from .app import launch as _launch

    _launch(*args, **kwargs)


__all__ = ["create_app", "launch"]
