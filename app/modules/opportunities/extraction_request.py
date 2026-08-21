from app.domain.rules.jd_extraction import (
    JDExtractionPolicy,
)
from app.modules.opportunities.schemas import (
    JDExtractionRequest,
    RawJobDescriptionInput,
)


class JDExtractionRequestBuilder:
    def __init__(
        self,
        policy: JDExtractionPolicy | None = None,
    ) -> None:
        self.policy = (
            policy or JDExtractionPolicy()
        )

    def build(
        self,
        *,
        raw_job: RawJobDescriptionInput,
    ) -> JDExtractionRequest:
        return JDExtractionRequest(
            extraction_rule_version=(
                self.policy.version
            ),
            company=raw_job.company,
            role_title=raw_job.role_title,
            location=raw_job.location,
            raw_text=raw_job.raw_text,
        )