"""0002 governance check constraints

Revision ID: 4837e3cf7f48
Revises: 76ffe6c593ce
Create Date: 2026-08-19 13:52:14.959083

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "4837e3cf7f48"
down_revision: Union[str, Sequence[str], None] = "76ffe6c593ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add governance check constraints."""

    op.create_check_constraint(
        "ck_sources_source_type_valid",
        "sources",
        "source_type IN ('PROFILE', 'CV', 'JD', 'EMAIL', 'ATS', 'USER', 'INTERVIEW', 'FEEDBACK')",
    )

    op.create_check_constraint(
        "ck_profile_facts_evidence_state_valid",
        "profile_facts",
        "evidence_state IN ('CONFIRMED', 'INFERRED', 'UNKNOWN')",
    )


def downgrade() -> None:
    """Remove governance check constraints."""

    op.drop_constraint(
        "ck_profile_facts_evidence_state_valid",
        "profile_facts",
        type_="check",
    )

    op.drop_constraint(
        "ck_sources_source_type_valid",
        "sources",
        type_="check",
    )