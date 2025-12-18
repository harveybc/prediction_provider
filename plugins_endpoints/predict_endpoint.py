#!/usr/bin/env python3
"""Predict endpoint plugin.

This repo currently implements the main prediction API directly in
`plugins_core.default_core`. This endpoint plugin exists so the entry-point
declared in `setup.py` is valid and loadable.
"""

from typing import Any, Dict
from fastapi import FastAPI


class PredictEndpointPlugin:
	plugin_params: Dict[str, Any] = {}
	plugin_debug_vars = []

	def __init__(self, config: dict | None = None):
		self.config = config or {}

	def set_params(self, **kwargs):
		self.config.update(kwargs)

	def register(self, app: FastAPI):
		# Core already provides `/api/v1/predict`.
		# Keep this as a no-op to avoid double-registering routes.
		return

