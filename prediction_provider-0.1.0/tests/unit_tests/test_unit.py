
import pytest
from unittest.mock import patch, MagicMock

from app.plugin_loader import get_plugin
from app.config_handler import get_config, get_config_value
from app.data_handler import fetch_data

@pytest.mark.unit
@patch('importlib.import_module')
def test_get_plugin(mock_import):
    """
    Unit test for the get_plugin function.
    """
    mock_module = MagicMock()
    MockPluginClass = MagicMock()
    mock_module.TestPlugin = MockPluginClass
    mock_import.return_value = mock_module

    plugin = get_plugin("test_plugins", "test_plugin")

    mock_import.assert_called_once_with("app.test_plugins.test_plugin")
    assert plugin is MockPluginClass

@pytest.mark.unit
@patch('app.config_handler.config', {"test_key": "test_value"})
def test_get_config_value():
    """
    Unit test for get_config_value.
    """
    value = get_config_value("test_key")
    assert value == "test_value"

    default_value = get_config_value("non_existent_key", "default")
    assert default_value == "default"

@pytest.mark.unit
@patch('requests.get')
def test_fetch_data(mock_get):
    """
    Unit test for the fetch_data function.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [1, 2, 3]}
    mock_get.return_value = mock_response

    data = fetch_data("EUR_USD", "H1", {"provider": "test_provider", "url": "http://test.com"})

    mock_get.assert_called_once()
    assert data == [1, 2, 3]

@pytest.mark.unit
@patch('requests.get')
def test_fetch_data_failure(mock_get):
    """
    Unit test for a failed fetch_data call.
    """
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    with pytest.raises(Exception):
        fetch_data("EUR_USD", "H1", {"provider": "test_provider", "url": "http://test.com"})
