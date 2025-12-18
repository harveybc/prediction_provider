#!/usr/bin/env python3
"""Metrics endpoint plugin.

Core exposes system/state endpoints; this plugin is a minimal loadable stub.
"""

from typing import Any, Dict
from fastapi import FastAPI


class MetricsEndpointPlugin:
	plugin_params: Dict[str, Any] = {}
	plugin_debug_vars = []

	def __init__(self, config: dict | None = None):
		self.config = config or {}

	def set_params(self, **kwargs):
		self.config.update(kwargs)

	def register(self, app: FastAPI):
		return

