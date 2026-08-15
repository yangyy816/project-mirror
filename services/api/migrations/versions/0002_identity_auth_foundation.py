"""Append identity and authentication foundation persistence.

Revision ID: 0002_identity_auth
Revises: 0001_phase0
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_identity_auth"
down_revision: str | None = "0001_phase0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _install_evidence_triggers() -> None:
    for table_name in (
        "invite_redemptions",
        "age_assurance_records",
        "policy_acceptance_records",
    ):
        op.execute(
            f"CREATE TRIGGER trg_{table_name}_immutable "
            f"BEFORE UPDATE OR DELETE ON {table_name} "
            "FOR EACH ROW EXECUTE FUNCTION mirror_reject_mutation();"
        )


def _remove_evidence_triggers() -> None:
    for table_name in (
        "invite_redemptions",
        "age_assurance_records",
        "policy_acceptance_records",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_immutable ON {table_name}")


def upgrade() -> None:
    op.alter_column(
        "users",
        "phone_hash",
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
    )
    op.alter_column(
        "phone_verification_challenges",
        "phone_hash",
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
    )
    op.alter_column(
        "idempotency_records",
        "key_hash",
        existing_type=sa.String(length=64),
        type_=sa.String(length=128),
    )
    op.add_column(
        "phone_verification_challenges",
        sa.Column("invite_code_id", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "phone_verification_challenges",
        sa.Column("purpose", sa.String(length=48), nullable=True),
    )
    op.add_column(
        "phone_verification_challenges",
        sa.Column("request_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "phone_verification_challenges",
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE phone_verification_challenges "
        "SET purpose = COALESCE(purpose, 'legacy-phase0'), "
        "request_id = COALESCE(request_id, 'legacy-phase0') "
        "WHERE purpose IS NULL OR request_id IS NULL"
    )
    op.alter_column(
        "phone_verification_challenges",
        "purpose",
        existing_type=sa.String(length=48),
        nullable=False,
    )
    op.alter_column(
        "phone_verification_challenges",
        "request_id",
        existing_type=sa.String(length=128),
        nullable=False,
    )
    op.create_foreign_key(
        op.f("fk_phone_verification_challenges_invite_code_id_invite_codes"),
        "phone_verification_challenges",
        "invite_codes",
        ["invite_code_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_phone_verification_challenges_invite_code_id",
        "phone_verification_challenges",
        ["invite_code_id"],
    )
    op.create_check_constraint(
        op.f("ck_phone_verification_challenges_nonnegative_challenge_attempts"),
        "phone_verification_challenges",
        "attempts >= 0",
    )

    op.add_column("user_sessions", sa.Column("family_id", sa.String(length=32), nullable=True))
    op.add_column("user_sessions", sa.Column("token_id", sa.String(length=64), nullable=True))
    op.add_column("user_sessions", sa.Column("refresh_key_id", sa.String(length=64), nullable=True))
    op.add_column(
        "user_sessions", sa.Column("rotated_from_id", sa.String(length=32), nullable=True)
    )
    op.add_column("user_sessions", sa.Column("replaced_by_id", sa.String(length=32), nullable=True))
    op.add_column(
        "user_sessions", sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "user_sessions", sa.Column("revocation_reason", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "user_sessions", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(
        "UPDATE user_sessions SET family_id = COALESCE(family_id, id), "
        "token_id = COALESCE(token_id, id), "
        "refresh_key_id = COALESCE(refresh_key_id, 'legacy-phase0') "
        "WHERE family_id IS NULL OR token_id IS NULL OR refresh_key_id IS NULL"
    )
    op.alter_column(
        "user_sessions", "family_id", existing_type=sa.String(length=32), nullable=False
    )
    op.alter_column("user_sessions", "token_id", existing_type=sa.String(length=64), nullable=False)
    op.alter_column(
        "user_sessions", "refresh_key_id", existing_type=sa.String(length=64), nullable=False
    )
    op.create_unique_constraint(op.f("uq_user_sessions_token_id"), "user_sessions", ["token_id"])
    op.create_unique_constraint(
        op.f("uq_user_sessions_rotated_from_id"), "user_sessions", ["rotated_from_id"]
    )
    op.create_unique_constraint(
        op.f("uq_user_sessions_replaced_by_id"), "user_sessions", ["replaced_by_id"]
    )
    op.create_foreign_key(
        op.f("fk_user_sessions_rotated_from_id_user_sessions"),
        "user_sessions",
        "user_sessions",
        ["rotated_from_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_user_sessions_replaced_by_id_user_sessions"),
        "user_sessions",
        "user_sessions",
        ["replaced_by_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_user_sessions_user_family", "user_sessions", ["user_id", "family_id"])
    op.create_check_constraint(
        op.f("ck_user_sessions_valid_session_lineage"),
        "user_sessions",
        "(rotated_from_id IS NULL OR rotated_from_id <> id) AND "
        "(replaced_by_id IS NULL OR replaced_by_id <> id)",
    )

    op.add_column(
        "idempotency_records",
        sa.Column("state", sa.String(length=24), nullable=False, server_default="in_progress"),
    )
    op.add_column(
        "idempotency_records", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_idempotency_records_valid_idempotency_state"),
        "idempotency_records",
        "state IN ('in_progress','completed','failed') AND "
        "((state = 'completed' AND completed_at IS NOT NULL) OR "
        "(state <> 'completed' AND completed_at IS NULL))",
    )
    op.alter_column("idempotency_records", "state", server_default=None)

    op.create_table(
        "invite_redemptions",
        sa.Column("invite_code_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("challenge_id", sa.String(length=32), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["challenge_id"],
            ["phone_verification_challenges.id"],
            name="fk_invite_redemption_challenge",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invite_code_id"],
            ["invite_codes.id"],
            name=op.f("fk_invite_redemptions_invite_code_id_invite_codes"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_invite_redemptions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_invite_redemptions"),
        sa.UniqueConstraint("challenge_id", name=op.f("uq_invite_redemptions_challenge_id")),
        sa.UniqueConstraint("user_id", name=op.f("uq_invite_redemptions_user_id")),
    )
    op.create_index(
        "ix_invite_redemptions_invite_code_id", "invite_redemptions", ["invite_code_id"]
    )
    op.create_index("ix_invite_redemptions_user_id", "invite_redemptions", ["user_id"])

    op.create_table(
        "age_assurance_records",
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_reference_hash", sa.String(length=128), nullable=False),
        sa.Column("result", sa.String(length=24), nullable=False),
        sa.Column("provider_version", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at >= verified_at",
            name=op.f("ck_age_assurance_records_valid_age_assurance_expiry"),
        ),
        sa.CheckConstraint(
            "result IN ('verified','not_verified','indeterminate')",
            name=op.f("ck_age_assurance_records_valid_age_assurance_result"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_age_assurance_records_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_age_assurance_records"),
        sa.UniqueConstraint(
            "provider", "provider_reference_hash", name=op.f("uq_age_assurance_records_provider")
        ),
    )
    op.create_index("ix_age_assurance_records_user_id", "age_assurance_records", ["user_id"])

    op.create_table(
        "policy_acceptance_records",
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("document_code", sa.String(length=64), nullable=False),
        sa.Column("document_version", sa.String(length=64), nullable=False),
        sa.Column("document_digest", sa.String(length=64), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=48), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_policy_acceptance_records_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_policy_acceptance_records"),
        sa.UniqueConstraint(
            "user_id",
            "document_code",
            "document_version",
            "document_digest",
            name=op.f("uq_policy_acceptance_records_user_id"),
        ),
    )
    op.create_index(
        "ix_policy_acceptance_records_user_id", "policy_acceptance_records", ["user_id"]
    )
    _install_evidence_triggers()


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM users WHERE length(phone_hash) > 64) THEN "
        "RAISE EXCEPTION 'cannot downgrade 0002: users.phone_hash exceeds 64'; END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM phone_verification_challenges "
        "WHERE length(phone_hash) > 64) THEN "
        "RAISE EXCEPTION 'cannot downgrade 0002: phone verification challenge hash exceeds 64'; "
        "END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM idempotency_records WHERE length(key_hash) > 64) "
        "THEN RAISE EXCEPTION 'cannot downgrade 0002: idempotency key hash exceeds 64'; "
        "END IF; END $$;"
    )
    _remove_evidence_triggers()
    op.drop_index("ix_policy_acceptance_records_user_id", table_name="policy_acceptance_records")
    op.drop_table("policy_acceptance_records")
    op.drop_index("ix_age_assurance_records_user_id", table_name="age_assurance_records")
    op.drop_table("age_assurance_records")
    op.drop_index("ix_invite_redemptions_user_id", table_name="invite_redemptions")
    op.drop_index("ix_invite_redemptions_invite_code_id", table_name="invite_redemptions")
    op.drop_table("invite_redemptions")

    op.drop_constraint(
        op.f("ck_idempotency_records_valid_idempotency_state"),
        "idempotency_records",
        type_="check",
    )
    op.drop_column("idempotency_records", "completed_at")
    op.drop_column("idempotency_records", "state")

    op.drop_constraint(
        op.f("ck_user_sessions_valid_session_lineage"), "user_sessions", type_="check"
    )
    op.drop_index("ix_user_sessions_user_family", table_name="user_sessions")
    op.drop_constraint(
        op.f("fk_user_sessions_replaced_by_id_user_sessions"), "user_sessions", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_user_sessions_rotated_from_id_user_sessions"), "user_sessions", type_="foreignkey"
    )
    op.drop_constraint(op.f("uq_user_sessions_replaced_by_id"), "user_sessions", type_="unique")
    op.drop_constraint(op.f("uq_user_sessions_rotated_from_id"), "user_sessions", type_="unique")
    op.drop_constraint(op.f("uq_user_sessions_token_id"), "user_sessions", type_="unique")
    op.drop_column("user_sessions", "last_seen_at")
    op.drop_column("user_sessions", "revocation_reason")
    op.drop_column("user_sessions", "consumed_at")
    op.drop_column("user_sessions", "replaced_by_id")
    op.drop_column("user_sessions", "rotated_from_id")
    op.drop_column("user_sessions", "refresh_key_id")
    op.drop_column("user_sessions", "token_id")
    op.drop_column("user_sessions", "family_id")

    op.drop_constraint(
        op.f("ck_phone_verification_challenges_nonnegative_challenge_attempts"),
        "phone_verification_challenges",
        type_="check",
    )
    op.drop_index(
        "ix_phone_verification_challenges_invite_code_id",
        table_name="phone_verification_challenges",
    )
    op.drop_constraint(
        op.f("fk_phone_verification_challenges_invite_code_id_invite_codes"),
        "phone_verification_challenges",
        type_="foreignkey",
    )
    op.drop_column("phone_verification_challenges", "invalidated_at")
    op.drop_column("phone_verification_challenges", "request_id")
    op.drop_column("phone_verification_challenges", "purpose")
    op.drop_column("phone_verification_challenges", "invite_code_id")
    op.alter_column(
        "idempotency_records",
        "key_hash",
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
    )
    op.alter_column(
        "phone_verification_challenges",
        "phone_hash",
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
    )
    op.alter_column(
        "users",
        "phone_hash",
        existing_type=sa.String(length=128),
        type_=sa.String(length=64),
    )
