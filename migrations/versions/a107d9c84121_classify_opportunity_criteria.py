"""Classify criteria without rewriting historical reviews."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a107d9c84121"
down_revision = "0810eb4a8bb4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("job_requirements", sa.Column("criterion_type", sa.String(50), nullable=True))
    op.add_column(
        "job_requirements", sa.Column("classification_reason", sa.String(2000), nullable=True)
    )
    op.add_column(
        "job_requirements", sa.Column("source_excerpts", postgresql.JSONB(), nullable=True)
    )
    op.create_check_constraint(
        "ck_job_requirements_criterion_type",
        "job_requirements",
        "criterion_type IS NULL OR criterion_type IN ('CONTEXT','ROLE_CAPABILITY','ESSENTIAL','DESIRABLE','UNCLASSIFIED','PRACTICAL_CONDITION')",
    )


def downgrade():
    op.drop_constraint("ck_job_requirements_criterion_type", "job_requirements", type_="check")
    for column in ("source_excerpts", "classification_reason", "criterion_type"):
        op.drop_column("job_requirements", column)
