from sqlalchemy.orm import Session

from app.domain.rules.source_authority import (
    SourceAuthorityPolicy,
)
from app.infrastructure.db.session import engine
from app.modules.audit.service import (
    RuleEvaluationService,
)


def test_source_authority_decision_can_be_audited() -> None:
    policy = SourceAuthorityPolicy()
    audit_service = RuleEvaluationService()

    input_payload = {
        "domain": "professional_profile",
        "source_type_a": "PROFILE",
        "source_type_b": "CV",
    }

    winner = policy.compare_sources(
        domain=input_payload["domain"],
        source_type_a=input_payload["source_type_a"],
        source_type_b=input_payload["source_type_b"],
    )

    result_json = {
        "winner": winner,
        "priority_a": policy.get_priority(
            input_payload["domain"],
            input_payload["source_type_a"],
        ),
        "priority_b": policy.get_priority(
            input_payload["domain"],
            input_payload["source_type_b"],
        ),
    }

    with Session(engine) as session:
        evaluation = audit_service.record(
            session,
            rule_set="source_authority",
            ruleset_version=policy.version,
            input_payload=input_payload,
            result_json=result_json,
            entity_type="professional_profile",
        )

        assert evaluation.evaluation_id is not None
        assert evaluation.rule_set == "source_authority"
        assert evaluation.ruleset_version == "0.1"
        assert (
            evaluation.entity_type
            == "professional_profile"
        )

        assert len(evaluation.input_hash) == 64

        assert evaluation.input_json == input_payload

        assert evaluation.input_hash == (
            audit_service.calculate_input_hash(
                evaluation.input_json
            )
        )

        assert evaluation.result_json == {
            "winner": "PROFILE",
            "priority_a": 100,
            "priority_b": 80,
        }

        session.rollback()