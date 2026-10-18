"""
Rules API Router
Endpoints for parsing natural language rules and managing structured detection rules.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import logging
from anomaly.rule_engine import parse_natural_language_rule
from database import (
    save_rule,
    get_rules,
    delete_rule,
    toggle_rule
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ParseRuleRequest(BaseModel):
    text: str


class CreateRuleRequest(BaseModel):
    name: str
    rule_type: str
    config: Dict[str, Any]
    natural_language: Optional[str] = None


class ToggleRuleRequest(BaseModel):
    is_active: bool


@router.post("/parse")
async def parse_rule(payload: ParseRuleRequest):
    """
    Parse a natural-language rule string into structured parameters.
    Returns validation status and technical explanations.
    """
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Rule text cannot be empty")
        
    result = parse_natural_language_rule(payload.text)
    return result


@router.get("/")
async def list_rules(active_only: bool = Query(False)):
    """List all configured anomaly detection rules."""
    try:
        return get_rules(active_only=active_only)
    except Exception as e:
        logger.error(f"Failed to fetch rules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch rules")


@router.post("/")
async def create_rule(payload: CreateRuleRequest):
    """Save and activate a new detection rule."""
    try:
        rule = save_rule(
            name=payload.name,
            rule_type=payload.rule_type,
            config=payload.config,
            natural_language=payload.natural_language
        )
        return {"success": True, "rule": rule}
    except Exception as e:
        logger.error(f"Failed to create rule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create rule")


@router.patch("/{rule_id}/toggle")
async def toggle(rule_id: str, payload: ToggleRuleRequest):
    """Toggle rule active state."""
    success = toggle_rule(rule_id, payload.is_active)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"success": True, "rule_id": rule_id, "is_active": payload.is_active}


@router.delete("/{rule_id}")
async def remove_rule(rule_id: str):
    """Delete a detection rule."""
    success = delete_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"success": True, "rule_id": rule_id, "message": "Rule deleted"}
