from __future__ import annotations

import os
from typing import Any

import pytest
from sqlalchemy import create_engine, delete, insert, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from mirror_api.models import (
    Asset,
    GeometryOntologyVersion,
    SyntheticGenerationPolicy,
    SyntheticIdentity,
    SyntheticPromptTemplate,
    SyntheticQAPolicy,
    User,
    new_id,
)

pytestmark = pytest.mark.integration

AUTHORITY_MODELS: tuple[tuple[type[Any], str], ...] = (
    (
        SyntheticGenerationPolicy,
        "mirror.synthetic-dataset/SyntheticGenerationPolicy/v1",
    ),
    (
        SyntheticPromptTemplate,
        "mirror.synthetic-dataset/SyntheticPromptTemplate/v1",
    ),
    (SyntheticQAPolicy, "mirror.synthetic-dataset/SyntheticQAPolicy/v1"),
    (GeometryOntologyVersion, "mirror.synthetic-dataset/GeometryOntologyVersion/v1"),
)


@pytest.fixture
def session() -> Session:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("NOT VERIFIED LOCALLY: TEST_DATABASE_URL PostgreSQL is unavailable")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE synthetic_generation_policies, synthetic_prompt_templates, "
                "synthetic_qa_policies, geometry_ontology_versions, synthetic_identities, assets, "
                "question_bank_versions, users CASCADE"
            )
        )
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


@pytest.mark.parametrize(("authority_model", "schema_version"), AUTHORITY_MODELS)
def test_synthetic_authority_content_is_unique_immutable_and_approval_is_terminal(
    session: Session, authority_model: type[Any], schema_version: str
) -> None:
    authority = authority_model(
        id=new_id(),
        schema_version=schema_version,
        version="fixture-v1",
        content={"kind": "synthetic-only"},
        content_digest="a" * 64,
    )
    session.add(authority)
    session.commit()

    orm_direct_approval = authority_model(
        id=new_id(),
        schema_version=schema_version,
        version="orm-direct-approval-v1",
        content={"kind": "orm-direct-approved"},
        content_digest="f" * 64,
        approval_status="APPROVED",
    )
    session.add(orm_direct_approval)
    with pytest.raises(ValueError, match="synthetic authority records must be inserted as DRAFT"):
        session.commit()
    session.rollback()

    with pytest.raises(IntegrityError):
        session.execute(
            insert(authority_model).values(
                id=new_id(),
                schema_version=schema_version,
                version="invalid-v1",
                content={"kind": "invalid-digest"},
                content_digest="A" * 64,
                approval_status="DRAFT",
            )
        )
    session.rollback()
    with pytest.raises(IntegrityError):
        session.execute(
            insert(authority_model).values(
                id=new_id(),
                schema_version="mirror.synthetic-dataset/Other/v1",
                version="invalid-schema-v1",
                content={"kind": "invalid-schema"},
                content_digest="b" * 64,
                approval_status="DRAFT",
            )
        )
    session.rollback()
    with pytest.raises(IntegrityError):
        session.execute(
            insert(authority_model).values(
                id=new_id(),
                schema_version=schema_version,
                version="invalid-content-v1",
                content=[],
                content_digest="c" * 64,
                approval_status="DRAFT",
            )
        )
    session.rollback()
    with pytest.raises(IntegrityError):
        session.execute(
            insert(authority_model).values(
                id=new_id(),
                schema_version=schema_version,
                version="Invalid-v1",
                content={"kind": "invalid-version"},
                content_digest="d" * 64,
                approval_status="DRAFT",
            )
        )
    session.rollback()
    with pytest.raises(DBAPIError, match="synthetic authority records must be inserted as DRAFT"):
        session.execute(
            insert(authority_model).values(
                id=new_id(),
                schema_version=schema_version,
                version="approved-v1",
                content={"kind": "direct-approved"},
                content_digest="e" * 64,
                approval_status="APPROVED",
                approved_at=text("now()"),
            )
        )
    session.rollback()

    duplicate_version = authority_model(
        id=new_id(),
        version="fixture-v1",
        content={"kind": "other"},
        content_digest="b" * 64,
    )
    session.add(duplicate_version)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    duplicate_digest = authority_model(
        id=new_id(),
        version="fixture-v2",
        content={"kind": "other"},
        content_digest="a" * 64,
    )
    session.add(duplicate_digest)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    with pytest.raises(DBAPIError, match="synthetic authority content is immutable"):
        session.execute(
            update(authority_model)
            .where(authority_model.id == authority.id)
            .values(content={"kind": "changed"})
        )
    session.rollback()
    with pytest.raises(DBAPIError, match="synthetic authority content is immutable"):
        session.execute(
            update(authority_model)
            .where(authority_model.id == authority.id)
            .values(schema_version="mirror.synthetic-dataset/Other/v1")
        )
    session.rollback()

    session.execute(
        update(authority_model)
        .where(authority_model.id == authority.id)
        .values(approval_status="APPROVED", approved_at=text("now()"))
    )
    session.commit()
    with pytest.raises(DBAPIError, match="synthetic authority approval is immutable once approved"):
        session.execute(
            update(authority_model)
            .where(authority_model.id == authority.id)
            .values(approval_status="DRAFT", approved_at=None)
        )
    session.rollback()
    with pytest.raises(DBAPIError, match="immutable record"):
        session.execute(delete(authority_model).where(authority_model.id == authority.id))
    session.rollback()


def test_synthetic_identity_is_bank_independent_and_synthetic_asset_shape_is_immutable(
    session: Session,
) -> None:
    identity = SyntheticIdentity(
        id=new_id(),
        generator_provider="deterministic_fixture",
        generator_model="fixture-v1",
        prompt_version="fixture-prompt-v1",
        provenance={"source": "synthetic"},
        adult_synthetic_attested=True,
    )
    session.add(identity)
    session.commit()
    assert identity.bank_version_id is None

    owner = User(id=new_id(), phone_hash="f" * 64)
    session.add(owner)
    session.commit()
    invalid_owner_bound_asset = Asset(
        id=new_id(),
        owner_user_id=owner.id,
        asset_role="synthetic",
        internal_purpose="synthetic_dataset",
        storage_key="synthetic/fixture/invalid-owner.jpg",
        mime_type="image/jpeg",
        byte_size=100,
        width=10,
        height=10,
        sha256="b" * 64,
        synthetic=True,
        is_ai_generated=True,
    )
    session.add(invalid_owner_bound_asset)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    invalid_purpose_asset = Asset(
        id=new_id(),
        owner_user_id=None,
        asset_role="synthetic",
        internal_purpose="other_internal_use",
        storage_key="synthetic/fixture/invalid-purpose.jpg",
        mime_type="image/jpeg",
        byte_size=100,
        width=10,
        height=10,
        sha256="d" * 64,
        synthetic=True,
        is_ai_generated=True,
    )
    session.add(invalid_purpose_asset)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    asset = Asset(
        id=new_id(),
        owner_user_id=None,
        asset_role="synthetic",
        internal_purpose="synthetic_dataset",
        storage_key="synthetic/fixture/canonical.jpg",
        mime_type="image/jpeg",
        byte_size=100,
        width=10,
        height=10,
        sha256="c" * 64,
        synthetic=True,
        is_ai_generated=True,
    )
    session.add(asset)
    session.commit()
    derived_asset = Asset(
        id=new_id(),
        owner_user_id=owner.id,
        asset_role="derived",
        storage_key="users/fixture/derived.jpg",
        mime_type="image/jpeg",
        byte_size=100,
        width=10,
        height=10,
        sha256="e" * 64,
        synthetic=False,
    )
    session.add(derived_asset)
    session.commit()
    with pytest.raises(DBAPIError, match="synthetic asset role is immutable"):
        session.execute(
            update(Asset)
            .where(Asset.id == derived_asset.id)
            .values(
                asset_role="synthetic",
                owner_user_id=None,
                internal_purpose="synthetic_dataset",
                synthetic=True,
            )
        )
    session.rollback()
    session.refresh(derived_asset)
    derived_asset.asset_role = "synthetic"
    with pytest.raises(ValueError, match="synthetic asset role is immutable"):
        session.commit()
    session.rollback()
    with pytest.raises(DBAPIError, match="synthetic asset blob metadata is immutable"):
        session.execute(
            text("UPDATE assets SET storage_key = 'synthetic/fixture/changed.jpg' WHERE id = :id"),
            {"id": asset.id},
        )
    session.rollback()
    with pytest.raises(DBAPIError, match="synthetic asset role is immutable"):
        session.execute(update(Asset).where(Asset.id == asset.id).values(asset_role="derived"))
    session.rollback()
    with pytest.raises(DBAPIError, match="synthetic asset blob metadata is immutable"):
        session.execute(update(Asset).where(Asset.id == asset.id).values(owner_user_id=owner.id))
    session.rollback()
    with pytest.raises(DBAPIError, match="synthetic asset blob metadata is immutable"):
        session.execute(
            update(Asset).where(Asset.id == asset.id).values(internal_purpose="other_internal_use")
        )
    session.rollback()
    with pytest.raises(DBAPIError, match="synthetic asset blob metadata is immutable"):
        session.execute(update(Asset).where(Asset.id == asset.id).values(synthetic=False))
    session.rollback()
    with pytest.raises(DBAPIError, match="synthetic asset blob metadata is immutable"):
        session.execute(update(Asset).where(Asset.id == asset.id).values(is_ai_generated=False))
    session.rollback()
    asset.internal_purpose = "other_internal_use"
    with pytest.raises(ValueError, match="synthetic asset blob metadata is immutable"):
        session.commit()
    session.rollback()
