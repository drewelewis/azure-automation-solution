"""Shared utilities package for Azure Automation runbooks."""

__version__ = "1.0.0"
__author__ = "Azure Automation Team"

# Import commonly used utilities
from .azure_auth import get_azure_credential, get_management_client
from .logging_utils import setup_logging, log_operation
from .config_manager import load_config, get_setting

__all__ = [
    'get_azure_credential',
    'get_management_client', 
    'setup_logging',
    'log_operation',
    'load_config',
    'get_setting'
]