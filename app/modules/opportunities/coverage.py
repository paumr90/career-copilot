"""Source bullet inventory for reviewers; no semantic completeness claim."""

import re

from app.modules.opportunities.schemas import JobDescriptionInput


def extraction_coverage(job: JobDescriptionInput) -> dict:
    def strip_bullet(value):
        return re.sub(r"^[•*\-]\s*", "", value.strip())

    bullets = [
        strip_bullet(line)
        for line in job.raw_text.splitlines()
        if re.match(r"^\s*[•*\-]\s+\S", line)
    ]
    represented, unrepresented = [], []
    for bullet in dict.fromkeys(bullets):
        keys = [
            item.requirement_key
            for item in job.requirements
            if item.evidence_text
            and (
                strip_bullet(item.evidence_text) in bullet
                or bullet in strip_bullet(item.evidence_text)
            )
        ]
        if keys:
            represented.append({"source_excerpt": bullet, "requirement_keys": keys})
        else:
            unrepresented.append(bullet)
    return {
        "method": "literal_source_bullet_inventory_v1",
        "represented_bullets": represented,
        "unrepresented_bullets": unrepresented,
        "requires_source_review": bool(unrepresented),
        "limitation": (
            "Literal evidence-span coverage does not prove semantic completeness. "
            "Unrepresented bullets may be context or benefits; review them explicitly."
        ),
    }
