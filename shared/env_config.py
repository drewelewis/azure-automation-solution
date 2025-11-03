"""Environment configuration loader and validator."""

import os
import logging
from typing import Dict, List, Optional
from pathlib import Path


class EnvironmentConfig:
    """Environment configuration manager."""
    
    def __init__(self, env_file: str = ".env"):
        """
        Initialize environment configuration.
        
        Args:
            env_file: Path to environment file
        """
        self.env_file = Path(env_file)
        self.logger = logging.getLogger(__name__)
        self._load_env_file()
    
    def _load_env_file(self) -> None:
        """Load environment variables from .env file."""
        if self.env_file.exists():
            try:
                with open(self.env_file, 'r') as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        
                        # Skip empty lines and comments
                        if not line or line.startswith('#'):
                            continue
                        
                        # Parse KEY=VALUE format
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            
                            # Remove quotes if present
                            if value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]
                            elif value.startswith("'") and value.endswith("'"):
                                value = value[1:-1]
                            
                            # Only set if not already in environment
                            if key not in os.environ:
                                os.environ[key] = value
                        else:
                            self.logger.warning(f"Invalid line format in {self.env_file}:{line_num}: {line}")
                            
            except Exception as e:
                self.logger.error(f"Failed to load environment file {self.env_file}: {str(e)}")
        else:
            self.logger.warning(f"Environment file {self.env_file} not found")
    
    def get_required_vars(self) -> List[str]:
        """Get list of required environment variables."""
        return [
            'AZURE_SUBSCRIPTION_ID',
            'AZURE_RESOURCE_GROUP',
        ]
    
    def get_optional_vars(self) -> Dict[str, str]:
        """Get dictionary of optional environment variables with defaults."""
        return {
            'AZURE_ENVIRONMENT': 'dev',
            'AZURE_LOCATION': 'East US',
            'LOG_LEVEL': 'INFO',
            'USE_MANAGED_IDENTITY': 'false',
            'AZURE_CLI_AUTH': 'true',
            'PYTHON_PATH': '.',
        }
    
    def validate_environment(self) -> Dict[str, any]:
        """
        Validate that all required environment variables are set.
        
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            'valid': True,
            'missing_required': [],
            'missing_optional': [],
            'warnings': []
        }
        
        # Check required variables
        for var in self.get_required_vars():
            if not os.getenv(var):
                validation_result['missing_required'].append(var)
                validation_result['valid'] = False
        
        # Check optional variables and set defaults
        for var, default_value in self.get_optional_vars().items():
            if not os.getenv(var):
                validation_result['missing_optional'].append(var)
                os.environ[var] = default_value
                self.logger.info(f"Set default value for {var}: {default_value}")
        
        # Specific validations
        self._validate_azure_auth(validation_result)
        self._validate_automation_config(validation_result)
        
        return validation_result
    
    def _validate_azure_auth(self, validation_result: Dict) -> None:
        """Validate Azure authentication configuration."""
        use_managed_identity = os.getenv('USE_MANAGED_IDENTITY', 'false').lower() == 'true'
        azure_cli_auth = os.getenv('AZURE_CLI_AUTH', 'true').lower() == 'true'
        
        has_service_principal = all([
            os.getenv('AZURE_CLIENT_ID'),
            os.getenv('AZURE_CLIENT_SECRET'),
            os.getenv('AZURE_TENANT_ID')
        ])
        
        if not use_managed_identity and not azure_cli_auth and not has_service_principal:
            validation_result['warnings'].append(
                "No authentication method configured. Consider setting up service principal or enabling Azure CLI auth."
            )
    
    def _validate_automation_config(self, validation_result: Dict) -> None:
        """Validate Azure Automation specific configuration."""
        automation_account = os.getenv('AZURE_AUTOMATION_ACCOUNT')
        automation_rg = os.getenv('AZURE_AUTOMATION_RESOURCE_GROUP')
        
        if not automation_account:
            validation_result['warnings'].append(
                "AZURE_AUTOMATION_ACCOUNT not set. This is required for deploying runbooks."
            )
        
        if not automation_rg:
            validation_result['warnings'].append(
                "AZURE_AUTOMATION_RESOURCE_GROUP not set. Using default resource group."
            )
    
    def print_validation_report(self, validation_result: Dict) -> None:
        """Print environment validation report."""
        print("=" * 60)
        print("ENVIRONMENT CONFIGURATION VALIDATION")
        print("=" * 60)
        
        if validation_result['valid']:
            print("✅ All required environment variables are set")
        else:
            print("❌ Missing required environment variables:")
            for var in validation_result['missing_required']:
                print(f"   - {var}")
        
        if validation_result['missing_optional']:
            print("\n📋 Optional variables set to defaults:")
            for var in validation_result['missing_optional']:
                default_value = self.get_optional_vars()[var]
                print(f"   - {var} = {default_value}")
        
        if validation_result['warnings']:
            print("\n⚠️  Warnings:")
            for warning in validation_result['warnings']:
                print(f"   - {warning}")
        
        print("\n📊 Current Configuration:")
        important_vars = [
            'AZURE_SUBSCRIPTION_ID',
            'AZURE_RESOURCE_GROUP', 
            'AZURE_ENVIRONMENT',
            'AZURE_LOCATION',
            'AZURE_AUTOMATION_ACCOUNT',
            'USE_MANAGED_IDENTITY',
            'LOG_LEVEL'
        ]
        
        for var in important_vars:
            value = os.getenv(var, 'Not Set')
            # Mask sensitive values
            if 'KEY' in var or 'SECRET' in var or 'PASSWORD' in var:
                value = '*' * len(value) if value != 'Not Set' else value
            print(f"   {var}: {value}")
        
        print("=" * 60)


def validate_environment(env_file: str = ".env") -> bool:
    """
    Validate environment configuration and print report.
    
    Args:
        env_file: Path to environment file
        
    Returns:
        True if validation passed, False otherwise
    """
    config = EnvironmentConfig(env_file)
    validation_result = config.validate_environment()
    config.print_validation_report(validation_result)
    
    return validation_result['valid']


if __name__ == "__main__":
    # Run validation when script is executed directly
    is_valid = validate_environment()
    exit(0 if is_valid else 1)