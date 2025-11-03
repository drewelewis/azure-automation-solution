"""
Azure Automation Runbook: Update Network Security Group Rules

This runbook updates NSG rules to allow traffic from the edge gateway IP specified
in the EDGE_GATEWAY_IP environment variable. It creates security rules for:
- HTTPS (port 443)
- SSH (port 22) 
- HTTP (port 80)

The script loads the edge gateway IP from the .env file and creates specific
allow rules with appropriate priorities and descriptions.
"""

import sys
import os
from typing import Dict, Any, List

# Add the shared modules to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared import setup_logging, log_operation, get_azure_credential, get_setting
from shared.common_operations import AzureOperations
from shared.env_config import EnvironmentConfig
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import SecurityRule
from azure.core.exceptions import AzureError


# Configuration for edge gateway security rules
EDGE_GATEWAY_RULES = [
    {
        "name": "AllowEdgeGatewayHTTPS",
        "port": "443",
        "priority": 1000,
        "purpose": "HTTPS traffic",
        "enabled": True
    },
    {
        "name": "AllowEdgeGatewaySSH", 
        "port": "22",
        "priority": 1001,
        "purpose": "SSH management",
        "enabled": True
    },
    {
        "name": "AllowEdgeGatewayHTTP",
        "port": "80", 
        "priority": 1002,
        "purpose": "HTTP traffic",
        "enabled": True
    },
    {
        "name": "AllowEdgeGatewayRDP",
        "port": "3389",
        "priority": 1003,
        "purpose": "RDP management",
        "enabled": False  # Disabled by default for security
    }
]


def main():
    """Main runbook execution function."""
    
    # Load environment configuration first
    env_config = EnvironmentConfig(".env")
    validation_result = env_config.validate_environment()
    
    # Setup logging
    logger = setup_logging("update-nsg", level="INFO")
    
    try:
        log_operation(logger, "update_nsg_runbook", status="START")
        
        # Get configuration
        subscription_id = get_setting('azure.subscription_id')
        if not subscription_id:
            raise ValueError("Azure subscription ID not configured")
        
        # Initialize Azure operations
        azure_ops = AzureOperations(subscription_id)
        
        # Get NSG configuration from environment variables
        resource_group = os.getenv('AZURE_NSG_RESOURCE_GROUP') or get_setting('azure.resource_group', 'default-rg')
        nsg_name = os.getenv('AZURE_NSG_NAME') or get_setting('networking.nsg_name', 'default-nsg')
        edge_gateway_ip = os.getenv('EDGE_GATEWAY_IP')
        
        logger.info(f"Target NSG: {nsg_name} in resource group: {resource_group}")
        
        if not edge_gateway_ip:
            logger.warning("EDGE_GATEWAY_IP not found in environment variables")
        else:
            logger.info(f"Configuring NSG to allow traffic from edge gateway: {edge_gateway_ip}")
        
        update_nsg_rules(azure_ops, resource_group, nsg_name, edge_gateway_ip, logger)
        
        log_operation(logger, "update_nsg_runbook", status="SUCCESS")
        logger.info("NSG update runbook completed successfully")
        
    except Exception as e:
        log_operation(logger, "update_nsg_runbook", status="ERROR", 
                     details={"error": str(e)})
        logger.error(f"Runbook failed: {str(e)}")
        raise


def create_edge_gateway_security_rule(
    name: str,
    port: str,
    priority: int,
    edge_gateway_ip: str,
    protocol: str = "Tcp",
    description: str = None
) -> SecurityRule:
    """
    Create a security rule for edge gateway access.
    
    Args:
        name: Rule name
        port: Destination port
        priority: Rule priority
        edge_gateway_ip: Source IP address
        protocol: Protocol (Tcp/Udp)
        description: Rule description
        
    Returns:
        SecurityRule object
    """
    if description is None:
        description = f"Allow {protocol.upper()} port {port} from edge gateway {edge_gateway_ip}"
    
    return SecurityRule(
        name=name,
        protocol=protocol,
        source_port_range="*",
        destination_port_range=port,
        source_address_prefix=f"{edge_gateway_ip}/32",
        destination_address_prefix="*",
        access="Allow",
        priority=priority,
        direction="Inbound",
        description=description
    )


def update_nsg_rules(
    azure_ops: AzureOperations, 
    resource_group: str, 
    nsg_name: str, 
    edge_gateway_ip: str,
    logger
) -> None:
    """
    Update Network Security Group rules to allow edge gateway traffic.
    
    Args:
        azure_ops: Azure operations instance
        resource_group: Resource group name
        nsg_name: NSG name
        edge_gateway_ip: Edge gateway IP address to allow
        logger: Logger instance
    """
    nsg_id = f"/subscriptions/{azure_ops.subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Network/networkSecurityGroups/{nsg_name}"
    
    try:
        # Get network client
        network_client = azure_ops.get_client('network')
        
        log_operation(logger, "get_nsg", nsg_id, status="START")
        
        # Get existing NSG
        nsg = network_client.network_security_groups.get(resource_group, nsg_name)
        
        log_operation(logger, "get_nsg", nsg_id, status="SUCCESS")
        
        # Create security rules for edge gateway
        rules_to_create = []
        
        if edge_gateway_ip:
            # Create rules based on configuration
            for rule_config in EDGE_GATEWAY_RULES:
                if rule_config.get("enabled", True):
                    description = f"Allow {rule_config['purpose']} from edge gateway {edge_gateway_ip}"
                    rule = create_edge_gateway_security_rule(
                        name=rule_config["name"],
                        port=rule_config["port"],
                        priority=rule_config["priority"],
                        edge_gateway_ip=edge_gateway_ip,
                        description=description
                    )
                    rules_to_create.append(rule)
                    logger.info(f"Prepared rule: {rule_config['name']} for port {rule_config['port']}")
        else:
            logger.warning("No edge gateway IP provided, skipping rule creation")
        
        # Create or update each rule
        for new_rule in rules_to_create:
            # Check if rule already exists
            existing_rule = next(
                (rule for rule in nsg.security_rules if rule.name == new_rule.name),
                None
            )
            
            if existing_rule:
                # Update existing rule if source IP has changed
                if existing_rule.source_address_prefix != new_rule.source_address_prefix:
                    logger.info(f"Updating security rule '{new_rule.name}' with new source IP")
                    log_operation(logger, "update_security_rule", nsg_id, status="START", 
                                details={"rule_name": new_rule.name, "new_source": new_rule.source_address_prefix})
                    
                    operation = network_client.security_rules.begin_create_or_update(
                        resource_group, nsg_name, new_rule.name, new_rule
                    )
                    operation.result()
                    
                    log_operation(logger, "update_security_rule", nsg_id, status="SUCCESS", 
                                details={"rule_name": new_rule.name, "source_ip": edge_gateway_ip})
                    logger.info(f"Successfully updated security rule: {new_rule.name}")
                else:
                    logger.info(f"Security rule '{new_rule.name}' already exists with correct configuration")
                    log_operation(logger, "update_security_rule", nsg_id, status="SUCCESS", 
                                details={"rule_name": new_rule.name, "action": "skipped_existing"})
            else:
                # Add the new rule
                log_operation(logger, "add_security_rule", nsg_id, status="START", 
                            details={"rule_name": new_rule.name, "source_ip": edge_gateway_ip})
                
                operation = network_client.security_rules.begin_create_or_update(
                    resource_group, nsg_name, new_rule.name, new_rule
                )
                
                # Wait for completion
                result = operation.result()
                
                log_operation(logger, "add_security_rule", nsg_id, status="SUCCESS", 
                            details={"rule_name": new_rule.name, "priority": new_rule.priority, "source_ip": edge_gateway_ip})
                
                logger.info(f"Successfully added security rule: {new_rule.name}")
        
        # List all current rules for verification
        list_nsg_rules(network_client, resource_group, nsg_name, logger)
        
    except AzureError as e:
        log_operation(logger, "update_nsg_rules", nsg_id, status="ERROR", 
                     details={"error": str(e)})
        logger.error(f"Failed to update NSG rules: {str(e)}")
        raise


def list_nsg_rules(
    network_client: NetworkManagementClient, 
    resource_group: str, 
    nsg_name: str, 
    logger
) -> None:
    """
    List all security rules in an NSG.
    
    Args:
        network_client: Network management client
        resource_group: Resource group name
        nsg_name: NSG name
        logger: Logger instance
    """
    try:
        nsg = network_client.network_security_groups.get(resource_group, nsg_name)
        
        logger.info(f"Security rules in NSG '{nsg_name}':")
        
        for rule in nsg.security_rules:
            rule_info = {
                "name": rule.name,
                "priority": rule.priority,
                "direction": rule.direction,
                "access": rule.access,
                "protocol": rule.protocol,
                "source_port": rule.source_port_range,
                "destination_port": rule.destination_port_range,
                "source_address": rule.source_address_prefix,
                "destination_address": rule.destination_address_prefix
            }
            
            logger.info(f"  Rule: {rule_info}")
            
    except Exception as e:
        logger.error(f"Failed to list NSG rules: {str(e)}")


if __name__ == "__main__":
    main()
