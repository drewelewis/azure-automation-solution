"""Configuration management utilities for runbooks."""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigManager:
    """Configuration manager for Azure Automation runbooks."""
    
    def __init__(self, config_dir: str = "config", environment: str = "prod"):
        """
        Initialize configuration manager.
        
        Args:
            config_dir: Directory containing configuration files
            environment: Environment name (dev, staging, prod)
        """
        self.config_dir = Path(config_dir)
        self.environment = environment
        self._config_cache = {}
        
    def load_config(self, config_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration from file (optional - will return empty dict if file doesn't exist).
        
        Args:
            config_name: Configuration file name (without .json extension)
                        If None, uses environment name
            
        Returns:
            Configuration dictionary (empty if file not found)
        """
        if config_name is None:
            config_name = self.environment
            
        # Check cache first
        cache_key = f"{config_name}_{self.environment}"
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]
        
        config_file = self.config_dir / f"{config_name}.json"
        
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    
                # Cache the configuration
                self._config_cache[cache_key] = config
                logging.info(f"Loaded configuration from {config_file}")
                return config
            else:
                # Return empty config instead of warning - environment variables will be used
                empty_config = {}
                self._config_cache[cache_key] = empty_config
                logging.info(f"No configuration file found at {config_file}, using environment variables only")
                return empty_config
                
        except Exception as e:
            logging.error(f"Failed to load configuration from {config_file}: {str(e)}")
            return {}
    
    def get_setting(self, key: str, default: Any = None, config_name: Optional[str] = None) -> Any:
        """
        Get specific setting from environment variables first, then configuration files.
        
        Args:
            key: Setting key (supports dot notation for nested keys)
            default: Default value if key not found
            config_name: Configuration file name (ignored if env var exists)
            
        Returns:
            Setting value or default
        """
        # First check environment variables for common mappings
        env_mappings = {
            'azure.subscription_id': 'AZURE_SUBSCRIPTION_ID',
            'azure.tenant_id': 'AZURE_TENANT_ID',
            'azure.resource_group': 'AZURE_RESOURCE_GROUP',
            'azure.location': 'AZURE_LOCATION',
            'azure.automation_account': 'AZURE_AUTOMATION_ACCOUNT',
            'logging.level': 'LOG_LEVEL',
            'networking.nsg_name': 'AZURE_NSG_NAME',
        }
        
        # Check if there's a direct environment variable mapping
        env_var = env_mappings.get(key)
        if env_var:
            env_value = os.getenv(env_var)
            if env_value is not None:
                return env_value
        
        # Also check for direct environment variable (replace dots with underscores and uppercase)
        env_key = key.upper().replace('.', '_')
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value
        
        # Fallback to JSON config if environment variable not found
        config = self.load_config(config_name)
        
        # Support dot notation for nested keys
        keys = key.split('.')
        value = config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_azure_settings(self) -> Dict[str, str]:
        """
        Get Azure-specific settings prioritizing environment variables over config files.
        
        Returns:
            Dictionary with Azure settings
        """
        # Get from environment variables first, with JSON config as fallback
        config = self.load_config() if os.path.exists(self.config_dir / f"{self.environment}.json") else {}
        azure_config = config.get('azure', {})
        
        # Common Azure settings with environment variable priority
        settings = {
            'subscription_id': os.getenv('AZURE_SUBSCRIPTION_ID') or azure_config.get('subscription_id'),
            'tenant_id': os.getenv('AZURE_TENANT_ID') or azure_config.get('tenant_id'),
            'client_id': os.getenv('AZURE_CLIENT_ID') or azure_config.get('client_id'),
            'resource_group': os.getenv('AZURE_RESOURCE_GROUP') or azure_config.get('resource_group'),
            'location': os.getenv('AZURE_LOCATION') or azure_config.get('location', 'East US'),
            'automation_account': os.getenv('AZURE_AUTOMATION_ACCOUNT') or azure_config.get('automation_account'),
        }
        
        return {k: v for k, v in settings.items() if v is not None}


# Global configuration manager instance
_config_manager = None


def get_config_manager(config_dir: str = "config", environment: str = None) -> ConfigManager:
    """
    Get or create global configuration manager instance.
    
    Args:
        config_dir: Configuration directory
        environment: Environment name
        
    Returns:
        ConfigManager instance
    """
    global _config_manager
    
    if environment is None:
        environment = os.getenv('AZURE_ENVIRONMENT', 'prod')
    
    if _config_manager is None:
        _config_manager = ConfigManager(config_dir, environment)
    
    return _config_manager


def load_config(config_name: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration using global config manager."""
    return get_config_manager().load_config(config_name)


def get_setting(key: str, default: Any = None, config_name: Optional[str] = None) -> Any:
    """Get setting using global config manager."""
    return get_config_manager().get_setting(key, default, config_name)