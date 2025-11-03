"""
Azure Automation Runbook: Rotate Key Vault Secrets

This runbook automates the rotation of secrets in Azure Key Vault including:
- Database connection strings
- API keys and tokens
- Certificates
- Service principal secrets

The script identifies secrets that need rotation based on age and policy,
creates new versions, and optionally notifies dependent services.
"""

import sys
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import json

# Add the shared modules to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared import setup_logging, log_operation, get_azure_credential, get_setting
from shared.common_operations import AzureOperations
from shared.env_config import EnvironmentConfig
from azure.keyvault.secrets import SecretClient
from azure.core.exceptions import AzureError


# Secret rotation configuration
ROTATION_POLICIES = {
    "database_connection": {
        "max_age_days": 90,
        "warning_days": 7,
        "auto_rotate": False,
        "notification_required": True
    },
    "api_key": {
        "max_age_days": 60,
        "warning_days": 5,
        "auto_rotate": False,
        "notification_required": True
    },
    "ssl_certificate": {
        "max_age_days": 365,
        "warning_days": 30,
        "auto_rotate": False,
        "notification_required": True
    },
    "service_principal": {
        "max_age_days": 180,
        "warning_days": 14,
        "auto_rotate": False,
        "notification_required": True
    }
}


def main():
    """Main runbook execution function."""
    
    # Load environment configuration first
    env_config = EnvironmentConfig(".env")
    validation_result = env_config.validate_environment()
    
    # Setup logging
    logger = setup_logging("rotate-secrets", level="INFO")
    
    try:
        log_operation(logger, "rotate_secrets_runbook", status="START")
        
        # Get configuration
        subscription_id = get_setting('azure.subscription_id')
        if not subscription_id:
            raise ValueError("Azure subscription ID not configured")
        
        # Initialize Azure operations
        azure_ops = AzureOperations(subscription_id)
        
        # Get Key Vault configuration from environment variables
        keyvault_name = os.getenv('AZURE_KEYVAULT_NAME') or get_setting('security.keyvault_name', 'default-kv')
        vault_url = f"https://{keyvault_name}.vault.azure.net/"
        
        logger.info(f"Checking secrets for rotation in Key Vault: {vault_url}")
        
        # Perform secret rotation check
        rotation_report = check_and_rotate_secrets(vault_url, azure_ops, logger)
        
        # Generate rotation report
        generate_rotation_report(rotation_report, logger)
        
        log_operation(logger, "rotate_secrets_runbook", status="SUCCESS")
        logger.info("Secret rotation runbook completed successfully")
        
    except Exception as e:
        log_operation(logger, "rotate_secrets_runbook", status="ERROR", 
                     details={"error": str(e)})
        logger.error(f"Runbook failed: {str(e)}")
        raise


def check_and_rotate_secrets(vault_url: str, azure_ops: AzureOperations, logger) -> Dict[str, Any]:
    """
    Check all secrets for rotation requirements and perform rotation if needed.
    
    Args:
        vault_url: Key Vault URL
        azure_ops: Azure operations instance
        logger: Logger instance
        
    Returns:
        Dictionary with rotation report
    """
    rotation_report = {
        "checked": [],
        "rotated": [],
        "warnings": [],
        "errors": [],
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # Get secret client
        secret_client = SecretClient(vault_url=vault_url, credential=azure_ops.credential)
        
        log_operation(logger, "check_secrets_rotation", vault_url, status="START")
        
        # Get all secrets
        for secret_properties in secret_client.list_properties_of_secrets():
            if secret_properties.enabled:
                secret_status = check_individual_secret(secret_client, secret_properties, logger)
                rotation_report["checked"].append(secret_status)
                
                if secret_status["needs_rotation"]:
                    if secret_status["auto_rotate"]:
                        try:
                            rotate_secret(secret_client, secret_properties.name, secret_status["policy"], logger)
                            rotation_report["rotated"].append(secret_status)
                            logger.info(f"Automatically rotated secret: {secret_properties.name}")
                        except Exception as e:
                            error_info = {"secret": secret_properties.name, "error": str(e)}
                            rotation_report["errors"].append(error_info)
                            logger.error(f"Failed to rotate secret {secret_properties.name}: {str(e)}")
                    else:
                        rotation_report["warnings"].append(secret_status)
                        logger.warning(f"Secret '{secret_properties.name}' needs manual rotation")
        
        log_operation(logger, "check_secrets_rotation", vault_url, status="SUCCESS",
                     details={"checked": len(rotation_report["checked"]), 
                             "rotated": len(rotation_report["rotated"]),
                             "warnings": len(rotation_report["warnings"])})
        
        return rotation_report
        
    except Exception as e:
        log_operation(logger, "check_secrets_rotation", vault_url, status="ERROR",
                     details={"error": str(e)})
        logger.error(f"Failed to check secrets for rotation: {str(e)}")
        raise


def check_individual_secret(
    secret_client: SecretClient, 
    secret_properties: Any, 
    logger
) -> Dict[str, Any]:
    """
    Check if an individual secret needs rotation.
    
    Args:
        secret_client: Secret client instance
        secret_properties: Secret properties from list
        logger: Logger instance
        
    Returns:
        Dictionary with secret status information
    """
    secret_name = secret_properties.name
    
    try:
        # Get secret details
        secret = secret_client.get_secret(secret_name)
        
        # Determine secret type from tags or name patterns
        secret_type = determine_secret_type(secret_name, secret.properties.tags or {})
        policy = ROTATION_POLICIES.get(secret_type, ROTATION_POLICIES["api_key"])
        
        # Calculate age
        created_date = secret.properties.created_on
        if created_date:
            age = datetime.now(created_date.tzinfo) - created_date
            age_days = age.days
        else:
            age_days = 0
        
        # Check rotation requirements
        needs_rotation = age_days >= policy["max_age_days"]
        needs_warning = age_days >= (policy["max_age_days"] - policy["warning_days"])
        
        secret_status = {
            "name": secret_name,
            "type": secret_type,
            "age_days": age_days,
            "created": created_date.isoformat() if created_date else None,
            "needs_rotation": needs_rotation,
            "needs_warning": needs_warning,
            "auto_rotate": policy["auto_rotate"],
            "policy": policy,
            "content_type": secret.properties.content_type,
            "tags": secret.properties.tags or {}
        }
        
        if needs_rotation:
            logger.warning(f"Secret '{secret_name}' needs rotation (age: {age_days} days)")
        elif needs_warning:
            logger.info(f"Secret '{secret_name}' approaching rotation (age: {age_days} days)")
        
        return secret_status
        
    except Exception as e:
        logger.error(f"Failed to check secret '{secret_name}': {str(e)}")
        return {
            "name": secret_name,
            "error": str(e),
            "needs_rotation": False,
            "auto_rotate": False
        }


def determine_secret_type(secret_name: str, tags: Dict[str, str]) -> str:
    """
    Determine secret type from name patterns and tags.
    
    Args:
        secret_name: Name of the secret
        tags: Secret tags
        
    Returns:
        Secret type string
    """
    # Check tags first
    if "type" in tags:
        return tags["type"]
    
    # Check name patterns
    name_lower = secret_name.lower()
    
    if any(pattern in name_lower for pattern in ["connection", "conn", "database", "db"]):
        return "database_connection"
    elif any(pattern in name_lower for pattern in ["api", "key", "token"]):
        return "api_key"
    elif any(pattern in name_lower for pattern in ["cert", "certificate", "ssl", "tls"]):
        return "ssl_certificate"
    elif any(pattern in name_lower for pattern in ["principal", "sp", "client"]):
        return "service_principal"
    else:
        return "api_key"  # Default


def rotate_secret(
    secret_client: SecretClient, 
    secret_name: str, 
    policy: Dict[str, Any], 
    logger
) -> None:
    """
    Rotate a secret by creating a new version.
    
    Args:
        secret_client: Secret client instance
        secret_name: Name of the secret to rotate
        policy: Rotation policy for the secret
        logger: Logger instance
    """
    try:
        log_operation(logger, "rotate_secret", secret_name, status="START")
        
        # Get current secret
        current_secret = secret_client.get_secret(secret_name)
        
        # Generate new secret value (this is where you'd integrate with your secret generation logic)
        new_secret_value = generate_new_secret_value(secret_name, current_secret.value, logger)
        
        # Create new version of the secret
        if new_secret_value and new_secret_value != current_secret.value:
            # Add rotation metadata to tags
            rotation_tags = (current_secret.properties.tags or {}).copy()
            rotation_tags.update({
                "last_rotated": datetime.now().isoformat(),
                "rotated_by": "automation",
                "previous_version": current_secret.properties.version
            })
            
            # Set new secret version
            new_secret = secret_client.set_secret(
                secret_name,
                new_secret_value,
                content_type=current_secret.properties.content_type,
                tags=rotation_tags
            )
            
            logger.info(f"Created new version of secret '{secret_name}': {new_secret.properties.version}")
            
            # Schedule notification if required
            if policy.get("notification_required", False):
                schedule_rotation_notification(secret_name, new_secret.properties.version, logger)
        else:
            logger.warning(f"No new value generated for secret '{secret_name}', skipping rotation")
        
        log_operation(logger, "rotate_secret", secret_name, status="SUCCESS")
        
    except Exception as e:
        log_operation(logger, "rotate_secret", secret_name, status="ERROR",
                     details={"error": str(e)})
        logger.error(f"Failed to rotate secret '{secret_name}': {str(e)}")
        raise


def generate_new_secret_value(secret_name: str, current_value: str, logger) -> Optional[str]:
    """
    Generate a new secret value for rotation.
    
    Args:
        secret_name: Name of the secret
        current_value: Current secret value
        logger: Logger instance
        
    Returns:
        New secret value or None if generation failed
    """
    try:
        # This is a placeholder implementation
        # In practice, you would:
        # 1. For API keys: Call the external service to generate a new key
        # 2. For connection strings: Update password component
        # 3. For certificates: Generate new certificate
        # 4. For service principals: Create new client secret
        
        logger.info(f"Generating new value for secret '{secret_name}' (placeholder implementation)")
        
        # Placeholder: Return None to prevent actual rotation in demo
        # In real implementation, you would generate actual new values
        return None
        
    except Exception as e:
        logger.error(f"Failed to generate new value for secret '{secret_name}': {str(e)}")
        return None


def schedule_rotation_notification(secret_name: str, new_version: str, logger) -> None:
    """
    Schedule notification about secret rotation.
    
    Args:
        secret_name: Name of the rotated secret
        new_version: New version identifier
        logger: Logger instance
    """
    try:
        # This is where you would integrate with your notification system
        # Examples: Teams webhook, email, ServiceNow ticket, etc.
        
        notification_info = {
            "secret_name": secret_name,
            "new_version": new_version,
            "rotated_at": datetime.now().isoformat(),
            "action_required": "Update dependent services with new secret version"
        }
        
        logger.info(f"Notification scheduled for secret rotation: {notification_info}")
        
        # Placeholder for actual notification implementation
        # send_teams_notification(notification_info)
        # create_servicenow_ticket(notification_info)
        # send_email_notification(notification_info)
        
    except Exception as e:
        logger.error(f"Failed to schedule notification for secret '{secret_name}': {str(e)}")


def generate_rotation_report(rotation_report: Dict[str, Any], logger) -> None:
    """
    Generate and log rotation report.
    
    Args:
        rotation_report: Rotation report data
        logger: Logger instance
    """
    try:
        logger.info("=" * 60)
        logger.info("SECRET ROTATION REPORT")
        logger.info("=" * 60)
        
        logger.info(f"Report generated: {rotation_report['timestamp']}")
        logger.info(f"Secrets checked: {len(rotation_report['checked'])}")
        logger.info(f"Secrets rotated: {len(rotation_report['rotated'])}")
        logger.info(f"Rotation warnings: {len(rotation_report['warnings'])}")
        logger.info(f"Rotation errors: {len(rotation_report['errors'])}")
        
        if rotation_report["warnings"]:
            logger.info("\n⚠️  SECRETS REQUIRING MANUAL ROTATION:")
            for warning in rotation_report["warnings"]:
                logger.info(f"  - {warning['name']} (age: {warning['age_days']} days)")
        
        if rotation_report["errors"]:
            logger.info("\n❌ ROTATION ERRORS:")
            for error in rotation_report["errors"]:
                logger.info(f"  - {error['secret']}: {error['error']}")
        
        if rotation_report["rotated"]:
            logger.info("\n✅ SUCCESSFULLY ROTATED:")
            for rotated in rotation_report["rotated"]:
                logger.info(f"  - {rotated['name']}")
        
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Failed to generate rotation report: {str(e)}")


if __name__ == "__main__":
    main()