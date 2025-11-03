"""Simplified configuration using only environment variables."""

import os
import logging
from typing import Any, Optional


def get_env_setting(key: str, default: Any = None) -> Any:
    """
    Get setting from environment variables with optional type conversion.
    
    Args:
        key: Environment variable name
        default: Default value if not found
        
    Returns:
        Environment variable value or default
    """
    value = os.getenv(key, default)
    
    # Convert string representations of booleans
    if isinstance(value, str):
        if value.lower() in ('true', 'yes', '1', 'on'):
            return True
        elif value.lower() in ('false', 'no', '0', 'off'):
            return False
        # Convert string numbers
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except (ValueError, TypeError):
            pass
    
    return value


def get_azure_config() -> dict:
    """Get all Azure configuration from environment variables."""
    return {
        'subscription_id': os.getenv('AZURE_SUBSCRIPTION_ID'),
        'tenant_id': os.getenv('AZURE_TENANT_ID'),
        'client_id': os.getenv('AZURE_CLIENT_ID'),
        'client_secret': os.getenv('AZURE_CLIENT_SECRET'),
        'resource_group': os.getenv('AZURE_RESOURCE_GROUP'),
        'location': os.getenv('AZURE_LOCATION', 'East US'),
        'automation_account': os.getenv('AZURE_AUTOMATION_ACCOUNT'),
        'automation_resource_group': os.getenv('AZURE_AUTOMATION_RESOURCE_GROUP'),
        'environment': os.getenv('AZURE_ENVIRONMENT', 'dev'),
    }


def get_networking_config() -> dict:
    """Get networking configuration from environment variables."""
    return {
        'default_nsg_name': os.getenv('AZURE_DEFAULT_NSG_NAME', 'default-nsg'),
        'default_vnet_name': os.getenv('AZURE_DEFAULT_VNET_NAME', 'default-vnet'),
    }


def get_storage_config() -> dict:
    """Get storage configuration from environment variables."""
    return {
        'storage_account': os.getenv('AZURE_STORAGE_ACCOUNT'),
        'connection_string': os.getenv('AZURE_STORAGE_CONNECTION_STRING'),
    }


def validate_required_config() -> bool:
    """
    Validate that required configuration is present.
    
    Returns:
        True if all required config is present
    """
    required_vars = [
        'AZURE_SUBSCRIPTION_ID',
        'AZURE_RESOURCE_GROUP',
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        logger = logging.getLogger(__name__)
        logger.error(f"Missing required environment variables: {missing}")
        return False
    
    return True


# Convenience functions for common settings
def get_subscription_id() -> str:
    """Get Azure subscription ID."""
    return get_env_setting('AZURE_SUBSCRIPTION_ID')


def get_resource_group() -> str:
    """Get Azure resource group."""
    return get_env_setting('AZURE_RESOURCE_GROUP')


def get_location() -> str:
    """Get Azure location."""
    return get_env_setting('AZURE_LOCATION', 'East US')


def use_managed_identity() -> bool:
    """Check if should use managed identity."""
    return get_env_setting('USE_MANAGED_IDENTITY', False)


def get_log_level() -> str:
    """Get logging level."""
    return get_env_setting('LOG_LEVEL', 'INFO')