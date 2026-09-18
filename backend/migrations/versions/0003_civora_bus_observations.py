"""add Civora bus observations and Urban Issue evidence

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-18 00:00:00
"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Additive columns preserve all existing Civora incidents and their
    # report/ticket relationships while making each incident usable as a
    # Civora Urban Issue aggregate.
    op.add_column("incidents", sa.Column("observation_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("incidents", sa.Column("distinct_bus_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("incidents", sa.Column("reobservation_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("incidents", sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("incidents", sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "buses",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("bus_id", sa.Text(), nullable=False, unique=True),
        sa.Column("route_id", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "observations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", sa.Text(), nullable=False, unique=True),
        sa.Column("bus_id", sa.Text(), sa.ForeignKey("buses.bus_id"), nullable=False),
        sa.Column("route_id", sa.Text(), nullable=True),
        sa.Column("urban_issue_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id"), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", geoalchemy2.Geography(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("detected_class", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("severity", sa.Text(), nullable=True),
        sa.Column("source_metadata", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("gnss_accuracy_meters", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute("CREATE INDEX ix_observations_location ON observations USING GIST (location)")
    op.create_index("ix_observations_issue_observed", "observations", ["urban_issue_id", "observed_at"])
    op.create_index("ix_observations_class_observed", "observations", ["detected_class", "observed_at"])
    op.create_table(
        "issue_reobservations",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("urban_issue_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("observation_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("observations.id"), nullable=False, unique=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prior_issue_status", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("issue_reobservations")
    op.drop_index("ix_observations_class_observed", table_name="observations")
    op.drop_index("ix_observations_issue_observed", table_name="observations")
    op.execute("DROP INDEX IF EXISTS ix_observations_location")
    op.drop_table("observations")
    op.drop_table("buses")
    op.drop_column("incidents", "last_observed_at")
    op.drop_column("incidents", "first_observed_at")
    op.drop_column("incidents", "reobservation_count")
    op.drop_column("incidents", "distinct_bus_count")
    op.drop_column("incidents", "observation_count")
