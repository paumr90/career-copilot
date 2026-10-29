"""Deterministic safeguards for factual eligibility and work conditions."""

import re
import unicodedata

from app.domain.enums import MatchStatus


def normalized(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value.lower())
        if not unicodedata.combining(char)
    )


def requirement_text(requirement) -> str:
    return normalized(
        " ".join(
            [
                requirement.description,
                requirement.evidence_text or "",
            ]
        )
    )


def is_vehicle_requirement(requirement) -> bool:
    # A shared source sentence may mention education and a vehicle. Route by the
    # extracted criterion's meaning, not incidental words in its source excerpt.
    category = str(requirement.category)
    if category not in {"OTHER", "WORK_MODE", "LOCATION"}:
        return False
    subject = normalized(
        requirement.description
        + " "
        + getattr(requirement, "requirement_key", "").replace("_", " ")
    )
    return bool(
        re.search(
            r"own(?: a| your)? vehicle|vehicle ownership|vehiculo propio|vehicle propi", subject
        )
    )


def is_compatibility_requirement(requirement) -> bool:
    category = getattr(requirement.category, "value", requirement.category)
    return category in {"LOCATION", "WORK_MODE", "COMPENSATION"} or is_vehicle_requirement(
        requirement
    )


def salary_amounts(text: str) -> list[float]:
    values = []
    for number, suffix in re.findall(r"(\d+(?:[.,]\d+)?)\s*(k\b|eur\b|€)", normalized(text)):
        # Interpret explicit k/EUR amounts only; do not convert currencies or periods.
        if re.search(r"[.,]\d{3}$", number):
            amount = float(number.replace(".", "").replace(",", ""))
        else:
            amount = float(number.replace(",", "."))
        values.append(amount * 1000 if suffix == "k" else amount)
    return values


class CompatibilityAssessmentRules:
    VERSION = "0.2"

    def validate(self, *, request, proposal) -> None:
        if proposal.proposed_status == MatchStatus.UNKNOWN:
            return
        requirement = request.requirement
        category = requirement.category.value
        text = requirement_text(requirement)
        cited_ids = {item.profile_fact_id for item in proposal.evidence}
        facts = [
            item.value_json for item in request.ranked_evidence if item.profile_fact_id in cited_ids
        ]
        if is_vehicle_requirement(requirement):
            flags = [
                fact["owns_vehicle"] for fact in facts if type(fact.get("owns_vehicle")) is bool
            ]
            if not flags:
                raise ValueError(
                    "Vehicle ownership needs an explicit owns_vehicle fact; use UNKNOWN."
                )
            if proposal.proposed_status == MatchStatus.MATCH and True not in flags:
                raise ValueError("A false owns_vehicle fact cannot support MATCH.")

        if category == "LOCATION" and re.search(r"resid", text):
            cities = [
                normalized(fact["current_city"])
                for fact in facts
                if isinstance(fact.get("current_city"), str) and fact["current_city"].strip()
            ]
            provinces = [
                normalized(fact["current_province"])
                for fact in facts
                if isinstance(fact.get("current_province"), str)
                and fact["current_province"].strip()
            ]

            def matches(values):
                return any(
                    re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", text) for value in values
                )

            if re.search(r"\b(province|provincia)\b", text):
                if not provinces:
                    raise ValueError(
                        "Province residency needs an explicit province fact; use UNKNOWN."
                    )
                if not matches(provinces) and proposal.proposed_status != MatchStatus.GAP:
                    raise ValueError(
                        "Confirmed province mismatch cannot support MATCH or PARTIAL_MATCH."
                    )
            else:
                if not cities:
                    raise ValueError(
                        "A preferred location cannot establish actual residency; use UNKNOWN."
                    )
                if not matches(cities):
                    if not re.search(r"\b(city|ciudad|ciutat)\b", text):
                        raise ValueError(
                            "Different municipality with unspecified city/province scope requires UNKNOWN."
                        )
                    if proposal.proposed_status != MatchStatus.GAP:
                        raise ValueError(
                            "Confirmed city mismatch cannot support MATCH or PARTIAL_MATCH."
                        )

        if (
            category == "WORK_MODE"
            and proposal.proposed_status == MatchStatus.MATCH
            and any(
                isinstance(fact.get("onsite_days_acceptance"), dict)
                and fact["onsite_days_acceptance"].get("status") == "CONDITIONAL"
                for fact in facts
            )
        ):
            raise ValueError("Conditional onsite acceptance is PARTIAL_MATCH, not MATCH.")

        if category == "COMPENSATION" and re.search(
            r"\b(usd|gbp|monthly|month|mensual|mes)\b", text
        ):
            raise ValueError("Currency or pay-period conversion is not established; use UNKNOWN.")

        if category == "COMPENSATION" and proposal.proposed_status == MatchStatus.MATCH:
            amounts = salary_amounts(text)
            minima = [
                fact["minimum_fixed_salary_eur"]
                for fact in facts
                if type(fact.get("minimum_fixed_salary_eur")) in {int, float}
            ]
            if len(amounts) >= 2 and minima:
                lower, upper = min(amounts), max(amounts)
                if lower < max(minima) <= upper:
                    raise ValueError(
                        "Only part of the salary range reaches the minimum; use PARTIAL_MATCH "
                        "and do not imply a concrete offer at its upper end."
                    )
