#!/usr/bin/env python3
"""Info endpoint plugin.

The core app already provides basic info endpoints; this plugin is mainly to
satisfy the entry-point referenced in `setup.py`.
"""

from typing import Any, Dict
from fastapi import FastAPI


class InfoEndpointPlugin:
    plugin_params: Dict[str, Any] = {}
    plugin_debug_vars = []

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def set_params(self, **kwargs):
        self.config.update(kwargs)

    def register(self, app: FastAPI):
        return
