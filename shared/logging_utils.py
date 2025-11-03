"""Logging utilities for Azure Automation runbooks."""

import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any
import json


def setup_logging(
    name: str = __name__,
    level: str = "INFO",
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Setup logging for runbooks with Azure Automation compatible format.
    
    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string
        
    Returns:
        Configured logger
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))
    
    # Create formatter
    formatter = logging.Formatter(format_string)
    handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(handler)
    
    return logger


def log_operation(
    logger: logging.Logger,
    operation: str,
    resource_id: str = "",
    status: str = "START",
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log operation with structured format for Azure monitoring.
    
    Args:
        logger: Logger instance
        operation: Operation name
        resource_id: Azure resource ID
        status: Operation status (START, SUCCESS, ERROR, WARNING)
        details: Additional operation details
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "operation": operation,
        "resource_id": resource_id,
        "status": status
    }
    
    if details:
        log_entry["details"] = details
    
    # Choose log level based on status
    if status == "ERROR":
        logger.error(json.dumps(log_entry))
    elif status == "WARNING":
        logger.warning(json.dumps(log_entry))
    elif status == "SUCCESS":
        logger.info(json.dumps(log_entry))
    else:  # START, INFO, etc.
        logger.info(json.dumps(log_entry))


def log_azure_operation_result(
    logger: logging.Logger,
    operation: str,
    result: Any,
    resource_id: str = ""
) -> None:
    """
    Log Azure operation result with error handling.
    
    Args:
        logger: Logger instance
        operation: Operation name
        result: Operation result object
        resource_id: Azure resource ID
    """
    try:
        if hasattr(result, 'status_code'):
            # HTTP response
            if 200 <= result.status_code < 300:
                log_operation(logger, operation, resource_id, "SUCCESS", 
                            {"status_code": result.status_code})
            else:
                log_operation(logger, operation, resource_id, "ERROR", 
                            {"status_code": result.status_code, "response": str(result)})
        else:
            # Other operation result
            log_operation(logger, operation, resource_id, "SUCCESS", 
                        {"result": str(result)[:500]})  # Truncate long results
    except Exception as e:
        log_operation(logger, operation, resource_id, "ERROR", 
                    {"error": str(e)})