"""Initial schema.

Revision ID: 20260507_01
Revises:
Create Date: 2026-05-07 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260507_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "klauw_behandelingen",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("halsbandnummer", sa.Integer(), nullable=False),
        sa.Column("behandeldatum", sa.DateTime(), nullable=False),
        sa.Column("notatie", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        comment="Registratie van klauwbehandelingen bij koeien, inclusief bekappen en behandeling van klauwproblemen.",
    )

    op.create_table(
        "koeien",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("animal_id", sa.Uuid(), nullable=False),
        sa.Column("sex", sa.String(), nullable=False),
        sa.Column("eartag", sa.String(), nullable=False),
        sa.Column("birth_date", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("collar_number", sa.Integer(), nullable=False),
        sa.Column("dam_eartag", sa.String(), nullable=True),
        sa.Column("hair_color", sa.String(), nullable=False),
        sa.Column("eartag_short", sa.String(), nullable=False),
        sa.Column("in_current_herd", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("animal_id"),
        comment="Kerngegevens van alle koeien in het bedrijf. Uitgebreide informatie wordt opgeslagen in koe_details tabel.",
    )
    op.create_index(op.f("ix_koeien_eartag"), "koeien", ["eartag"], unique=True)

    op.create_table(
        "koe_details",
        sa.Column("animal_id", sa.Uuid(), nullable=False),
        sa.Column("previous_number", sa.Integer(), nullable=True),
        sa.Column("transponder_number", sa.BigInteger(), nullable=True),
        sa.Column("feeding_group_name", sa.String(), nullable=True),
        sa.Column("feeding_group_number", sa.Integer(), nullable=True),
        sa.Column("barn_group_name", sa.String(), nullable=True),
        sa.Column("barn_group_number", sa.Integer(), nullable=True),
        sa.Column("animal_type", sa.String(), nullable=False),
        sa.Column("animal_type_text", sa.String(), nullable=True),
        sa.Column("herd_name", sa.String(), nullable=True),
        sa.Column("last_herd_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("status_days", sa.Integer(), nullable=True),
        sa.Column("last_calving_date", sa.DateTime(), nullable=True),
        sa.Column("expected_calving_date", sa.DateTime(), nullable=True),
        sa.Column("expected_dry_off_date", sa.DateTime(), nullable=True),
        sa.Column("expected_calving_interval", sa.Integer(), nullable=True),
        sa.Column("last_insemination_date", sa.DateTime(), nullable=True),
        sa.Column("last_insemination_days", sa.Integer(), nullable=True),
        sa.Column("insemination_count", sa.Integer(), nullable=True),
        sa.Column("lactation_number", sa.Integer(), nullable=True),
        sa.Column("current_dim", sa.Integer(), nullable=True),
        sa.Column("last_milk", sa.Float(), nullable=True),
        sa.Column("lactation_total_milk", sa.Float(), nullable=True),
        sa.Column("is_dead", sa.Boolean(), nullable=False),
        sa.Column("is_young_stock", sa.Boolean(), nullable=False),
        sa.Column("to_be_culled", sa.Boolean(), nullable=False),
        sa.Column("aborted", sa.Boolean(), nullable=False),
        sa.Column("barren", sa.Boolean(), nullable=False),
        sa.Column("is_beef", sa.Boolean(), nullable=False),
        sa.Column("dam", sa.String(), nullable=True),
        sa.Column("sire", sa.String(), nullable=True),
        sa.Column("breed_text", sa.String(), nullable=True),
        sa.Column("age", sa.String(), nullable=True),
        sa.Column("long_name", sa.String(), nullable=True),
        sa.Column("comment", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["animal_id"], ["koeien.animal_id"]),
        sa.PrimaryKeyConstraint("animal_id"),
        comment="Uitgebreide koe-informatie zoals lactatie, inseminatie, groepsindeling en fokkerijgegevens. Gekoppeld aan koeien tabel.",
    )

    op.create_table(
        "melkingen",
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("animal_id", sa.Uuid(), nullable=False),
        sa.Column("shift_date", sa.DateTime(), nullable=False),
        sa.Column("shift_number", sa.Integer(), nullable=False),
        sa.Column("date_time", sa.DateTime(), nullable=False),
        sa.Column("dim", sa.Integer(), nullable=False),
        sa.Column("milk", sa.Float(), nullable=False),
        sa.Column("kind", sa.Integer(), nullable=False),
        sa.Column("milk_speed", sa.Float(), nullable=True),
        sa.Column("milk_duration", sa.Integer(), nullable=True),
        sa.Column("milk_stand_no", sa.Integer(), nullable=True),
        sa.Column("cond_value_lf", sa.Integer(), nullable=True),
        sa.Column("cond_avg_last_21_lf", sa.Float(), nullable=True),
        sa.Column("cond_std_dev_last_21_lf", sa.Float(), nullable=True),
        sa.Column("cond_attn_lf", sa.Boolean(), nullable=False),
        sa.Column("cond_attn_rf", sa.Boolean(), nullable=False),
        sa.Column("cond_attn_lr", sa.Boolean(), nullable=False),
        sa.Column("cond_attn_rr", sa.Boolean(), nullable=False),
        sa.Column("process_computer_type", sa.Integer(), nullable=True),
        sa.Column("indicatie_alternerend", sa.Boolean(), nullable=False),
        sa.Column("can_edit", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["animal_id"], ["koeien.animal_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_melkingen_animal_id"), "melkingen", ["animal_id"], unique=False)
    op.create_index(op.f("ix_melkingen_date_time"), "melkingen", ["date_time"], unique=False)
    op.create_index(op.f("ix_melkingen_shift_date"), "melkingen", ["shift_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_melkingen_shift_date"), table_name="melkingen")
    op.drop_index(op.f("ix_melkingen_date_time"), table_name="melkingen")
    op.drop_index(op.f("ix_melkingen_animal_id"), table_name="melkingen")
    op.drop_table("melkingen")
    op.drop_table("koe_details")
    op.drop_index(op.f("ix_koeien_eartag"), table_name="koeien")
    op.drop_table("koeien")
    op.drop_table("klauw_behandelingen")
