"""Explicit classification with conservative compatibility for historical snapshots."""

from app.modules.fit.compatibility import is_compatibility_requirement


def criterion_kind(item):
    explicit = getattr(item, "criterion_type", None)
    if explicit:
        return str(explicit)
    if is_compatibility_requirement(item):
        return "PRACTICAL_CONDITION"
    if item.category == "RESPONSIBILITY":
        return "ROLE_CAPABILITY"
    if item.priority == "MUST_HAVE":
        return "ESSENTIAL"
    if item.priority == "NICE_TO_HAVE":
        return "DESIRABLE"
    return "UNCLASSIFIED"
