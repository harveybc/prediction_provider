"""Shared DB reset logic for test sub-modules.

Imports and reuses the root conftest's engine and session factory
to avoid SQLite multi-connection issues.
"""


def reset_db():
    """Reset DB with standard test data using root conftest infrastructure."""
    # Import lazily to avoid circular import issues during collection
    from tests.conftest import setup_test_data
    setup_test_data()
