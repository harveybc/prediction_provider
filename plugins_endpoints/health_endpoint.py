#!/usr/bin/env python3
"""Health endpoint plugin.

Core already exposes `/health`; this plugin is kept for entry-point validity.
"""

from typing import Any, Dict
from fastapi import FastAPI


class HealthEndpointPlugin:
	plugin_params: Dict[str, Any] = {}
	plugin_debug_vars = []

	def __init__(self, config: dict | None = None):
		self.config = config or {}

	def set_params(self, **kwargs):
		self.config.update(kwargs)

	def register(self, app: FastAPI):
		# No-op: `/health` is provided by core.
		return

