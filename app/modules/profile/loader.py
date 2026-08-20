import hashlib
import json
from pathlib import Path
from typing import Any

from app.modules.profile.schemas import (
    CareerProfileSeed,
    ProfileFactSeed,
    SeedManifest,
)


class CareerProfileSeedLoader:
    def load(
        self,
        manifest_path: Path,
        profile_path: Path,
    ) -> CareerProfileSeed:
        manifest_data = self._read_json(manifest_path)
        profile_data = self._read_json(profile_path)

        manifest = SeedManifest.model_validate(manifest_data)

        if not isinstance(profile_data, list):
            raise ValueError(
                "Profile seed must contain a JSON array of facts."
            )

        facts = [
            ProfileFactSeed.model_validate(fact)
            for fact in profile_data
        ]

        calculated_hash = self.calculate_content_hash(
            manifest_data=manifest_data,
            profile_data=profile_data,
        )

        if (
            manifest.content_hash is not None
            and manifest.content_hash != calculated_hash
        ):
            raise ValueError(
                "Career Master seed content hash does not match the manifest."
            )

        manifest_with_hash = manifest.model_copy(
            update={
                "content_hash": calculated_hash,
            }
        )

        return CareerProfileSeed(
            manifest=manifest_with_hash,
            facts=facts,
        )

    @staticmethod
    def calculate_content_hash(
        *,
        manifest_data: dict[str, Any],
        profile_data: list[Any],
    ) -> str:
        hashable_manifest = dict(manifest_data)
        hashable_manifest["content_hash"] = None

        canonical_payload = {
            "manifest": hashable_manifest,
            "facts": profile_data,
        }

        canonical_json = json.dumps(
            canonical_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )

        return hashlib.sha256(
            canonical_json.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _read_json(path: Path) -> Any:
        if not path.exists():
            raise FileNotFoundError(
                f"Seed file not found: {path}"
            )

        return json.loads(
            path.read_text(encoding="utf-8")
        )