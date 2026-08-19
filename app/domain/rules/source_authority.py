from pathlib import Path
from typing import Any

import yaml


DEFAULT_RULES_PATH = Path("rules/source_authority.yaml")


class SourceAuthorityPolicy:
    def __init__(self, rules_path: Path = DEFAULT_RULES_PATH) -> None:
        self.rules_path = rules_path
        self._rules = self._load_rules()

    def _load_rules(self) -> dict[str, Any]:
        with self.rules_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        if not isinstance(data, dict):
            raise ValueError("Source authority rules must contain a YAML object.")

        if "domains" not in data:
            raise ValueError("Source authority rules must define 'domains'.")

        return data

    @property
    def version(self) -> str:
        return str(self._rules["version"])

    def get_priority(self, domain: str, source_type: str) -> int:
        domain_config = self._get_domain(domain)
        priorities = domain_config.get("priority", {})

        return int(priorities.get(source_type, 0))

    def compare_sources(
        self,
        domain: str,
        source_type_a: str,
        source_type_b: str,
    ) -> str:
        priority_a = self.get_priority(domain, source_type_a)
        priority_b = self.get_priority(domain, source_type_b)

        if priority_a > priority_b:
            return source_type_a

        if priority_b > priority_a:
            return source_type_b

        return "TIE"

    def get_domain_rules(self, domain: str) -> list[str]:
        domain_config = self._get_domain(domain)
        rules = domain_config.get("rules", [])

        return [str(rule) for rule in rules]

    def _get_domain(self, domain: str) -> dict[str, Any]:
        domains = self._rules["domains"]

        if domain not in domains:
            raise ValueError(f"Unknown authority domain: {domain}")

        domain_config = domains[domain]

        if not isinstance(domain_config, dict):
            raise ValueError(f"Invalid configuration for domain: {domain}")

        return domain_config