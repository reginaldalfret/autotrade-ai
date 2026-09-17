import json
from typing import Tuple, Optional, Dict, Any
from mobitrade.domain.llm_models import LLMAction, ValidationStatus

class DecisionValidator:
    """
    Strict validation gate for raw LLM JSON responses.
    Does NOT allow malformed JSON, invalid actions, invalid stop-loss logic,
    or out-of-range confidence scores.
    """
    def validate_response(
        self,
        raw_text: str,
        expected_symbol: str,
        expected_snapshot_id: str,
        current_price: float
    ) -> Tuple[bool, ValidationStatus, Optional[str], Optional[Dict[str, Any]]]:
        # 1. Clean and extract JSON substring
        cleaned = raw_text.strip() if raw_text else ""
        if "</think>" in cleaned:
            cleaned = cleaned.split("</think>")[-1].strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
            cleaned = cleaned[start_idx:end_idx + 1]

        try:
            data = json.loads(cleaned)
        except Exception as e:
            return False, ValidationStatus.INVALID_FORMAT, f"Malformed JSON: {e}", None

        if not isinstance(data, dict):
            return False, ValidationStatus.INVALID_FORMAT, "Response is not a JSON object", None

        # 2. Action Validation
        action_str = str(data.get("action", "")).upper()
        if action_str not in ("BUY", "SELL", "HOLD", "NO_ACTION"):
            return False, ValidationStatus.INVALID_ACTION, f"Invalid action: {action_str}", data

        # 3. Confidence Validation
        confidence = data.get("confidence")
        if confidence is None or not isinstance(confidence, (int, float)):
            return False, ValidationStatus.INVALID_CONFIDENCE, "Confidence is missing or non-numeric", data
        if confidence < 0.0 or confidence > 1.0:
            return False, ValidationStatus.INVALID_CONFIDENCE, f"Confidence {confidence} outside [0.0, 1.0]", data

        # 4. Stop-loss validation if provided
        stop_loss = data.get("proposed_stop_loss")
        if stop_loss is not None and isinstance(stop_loss, (int, float)):
            if stop_loss <= 0:
                return False, ValidationStatus.INVALID_STOP_LOSS, "Stop-loss must be positive", data
            if action_str == "BUY" and stop_loss >= current_price:
                return False, ValidationStatus.INVALID_STOP_LOSS, f"For BUY, stop-loss ({stop_loss}) must be < entry ({current_price})", data
            if action_str == "SELL" and stop_loss <= current_price:
                return False, ValidationStatus.INVALID_STOP_LOSS, f"For SELL, stop-loss ({stop_loss}) must be > entry ({current_price})", data

        # 5. Required reasoning fields
        rationale = str(data.get("entry_rationale", "")).strip()
        summary = str(data.get("reasoning_summary", "")).strip()
        if not rationale and not summary:
            return False, ValidationStatus.INVALID_FORMAT, "Missing required reasoning summary/rationale", data

        return True, ValidationStatus.VALID, None, data
