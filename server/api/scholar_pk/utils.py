"""
Scholar PK Utilities

This module contains utility functions for scholar PK.
"""

import json
from typing import Dict, Any, List

from server.utils.stream_protocol import create_event

def polish_author_info(author_info: List[Any]) -> str:
    """
    Polish author information for comparison by converting all elements to strings,
    including handling nested lists like research fields.

    Args:
        author_info (list): List containing author information

    Returns:
        str: Polished author information as a comma-separated string
    """
    polished_info = []
    for item in author_info:
        if isinstance(item, list):
            # Join list items with semicolons
            polished_info.append(';'.join(str(x) for x in item))
        else:
            # Convert non-list items to string
            polished_info.append(str(item))

    return ",".join(polished_info)

def format_pk_event_message(event_type: str, data: Dict[str, Any]) -> str:
    """Format an event message for PK

    Args:
        event_type: Type of event
        data: Event data

    Returns:
        Formatted event message
    """
    event_data = {
        "event": event_type,
        "event_type": event_type,
        "source": "scholar",
        "data": data,
    }
    # 统一 SSE 协议：只输出 data 行
    return f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

def create_pk_state_message(content: str, state: str = "thinking") -> Dict[str, Any]:
    """Create a state message for PK process

    Args:
        content: Message content
        state: Message state (thinking, completed, error)

    Returns:
        State message dictionary
    """
    return {
        "type": "pkState",
        "content": content,
        "state": state
    }

def create_pk_data_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a data message for PK results

    Args:
        data: PK data

    Returns:
        Data message dictionary
    """
    event = create_event(
        source="scholar",
        event_type="data",
        message="PK result generated",
        payload=data,
        legacy_type="pkData",
        step="pk_result",
    )
    # 兼容旧前端
    event["content"] = data
    return event

def create_pk_report_data_message(report_urls: Dict[str, str]) -> Dict[str, Any]:
    """Create a report data message for PK

    Args:
        report_urls: Dictionary containing PK report URLs

    Returns:
        Report data message dictionary
    """
    content = {
        "jsonUrl": report_urls["pk_json_url"],
        "researcher1Name": report_urls["researcher1_name"],
        "researcher2Name": report_urls["researcher2_name"]
    }

    # Add scholar IDs if available
    if "scholar_id1" in report_urls:
        content["scholarId1"] = report_urls["scholar_id1"]
    if "scholar_id2" in report_urls:
        content["scholarId2"] = report_urls["scholar_id2"]

    event = create_event(
        source="scholar",
        event_type="data",
        message="PK report generated",
        payload=content,
        legacy_type="reportData",
        step="pk_report",
    )
    # 兼容旧前端
    event["content"] = content
    return event
