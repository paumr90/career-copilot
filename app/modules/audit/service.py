import hashlib
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.modules.audit.models import RuleEvaluation


class RuleEvaluationService:
    @staticmethod
    def calculate_input_hash(input_payload: dict[str, Any]) -> str:
        canonical_input = json.dumps(
            input_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )

        return hashlib.sha256(
            canonical_input.encode("utf-8")
        ).hexdigest()

    def record(
        self,
        session: Session,
        *,
        rule_set: str,
        ruleset_version: str,
        input_payload: dict[str, Any],
        result_json: dict[str, Any],
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
    ) -> RuleEvaluation:
        evaluation = RuleEvaluation(
            rule_set=rule_set,
            ruleset_version=ruleset_version,
            entity_type=entity_type,
            entity_id=entity_id,
            input_hash=self.calculate_input_hash(input_payload),
            result_json=result_json,
        )

        session.add(evaluation)
        session.flush()

        return evaluation