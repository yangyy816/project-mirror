from __future__ import annotations

import hashlib
import shutil
import sqlite3
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from mirror_api import demo_d02_r2_private_registry as registry
from mirror_api.demo_measurement_quality import canonical_json_bytes, mirror_demo_digest

TIMESTAMP = "2026-08-25T00:00:00.000000Z"
AUTHORITY: registry.RootReceiptAuthority


def _git(repository: Path, *arguments: str) -> bytes:
    git_executable = shutil.which("git")
    assert git_executable is not None
    return subprocess.run(  # noqa: S603 - resolved local Git; isolated test repository only.
        [str(Path(git_executable).resolve(strict=True)), "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
    ).stdout


@pytest.fixture(scope="session", autouse=True)
def _accepted_registry_authority(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, str, str]:
    global AUTHORITY
    source_repository = Path(__file__).resolve().parents[3]
    authority_repository = tmp_path_factory.mktemp("registry-authority-repository")
    _git(authority_repository, "init", "--quiet")
    _git(authority_repository, "config", "user.name", "Project Mirror Test")
    _git(authority_repository, "config", "user.email", "test@project-mirror.invalid")
    _git(
        authority_repository,
        "fetch",
        "--quiet",
        "--no-tags",
        str(source_repository),
        registry.ACCEPTED_PLAN_SHA,
    )
    _git(authority_repository, "checkout", "--quiet", "--detach", "FETCH_HEAD")

    for relative_path in registry.REGISTRY_GOVERNED_PATHS:
        destination = authority_repository / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((source_repository / relative_path).read_bytes())
    _git(authority_repository, "add", "--", *registry.REGISTRY_GOVERNED_PATHS)
    _git(authority_repository, "commit", "--quiet", "-m", "test: candidate registry implementation")
    implementation_sha = _git(authority_repository, "rev-parse", "HEAD").decode().strip()
    implementation_tree = (
        _git(authority_repository, "rev-parse", f"{implementation_sha}^{{tree}}").decode().strip()
    )

    governed_paths: list[registry.JsonValue] = []
    for relative_path in registry.REGISTRY_GOVERNED_PATHS:
        governed_bytes = _git(
            authority_repository,
            "show",
            f"{implementation_sha}:{relative_path}",
        )
        governed_paths.append(
            {
                "path": relative_path,
                "git_blob_oid": _git(
                    authority_repository,
                    "rev-parse",
                    f"{implementation_sha}:{relative_path}",
                )
                .decode()
                .strip(),
                "sha256": hashlib.sha256(governed_bytes).hexdigest(),
            }
        )
    record: registry.JsonObject = {
        "schema_version": registry.REGISTRY_IMPLEMENTATION_ACCEPTANCE_SCHEMA,
        "authority_id": registry.REGISTRY_IMPLEMENTATION_AUTHORITY_ID,
        "change_control_id": registry.CHANGE_CONTROL_ID,
        "implementation_task_id": registry.REGISTRY_IMPLEMENTATION_TASK_ID,
        "evidence_root_id": registry.EVIDENCE_ROOT_ID,
        "accepted_plan_sha": registry.ACCEPTED_PLAN_SHA,
        "accepted_plan_tree": registry.ACCEPTED_PLAN_TREE,
        "registry_implementation_sha": implementation_sha,
        "registry_implementation_tree": implementation_tree,
        "registry_schema_contract_digest": registry.REGISTRY_SCHEMA_CONTRACT_DIGEST,
        "registry_normalized_ddl_sha256": registry.REGISTRY_NORMALIZED_DDL_SHA256,
        "governed_paths": governed_paths,
        "independent_review": {
            "review_task_id": "P3_P7_D02_R2_REGISTRY_EXACT_SHA_REVIEW_01",
            "reviewed_implementation_sha": implementation_sha,
            "result": "PASS",
            "findings_p0": 0,
            "findings_p1": 0,
            "findings_p2": 0,
            "findings_p3": 0,
            "evidence_digest": "1" * 64,
        },
        "same_sha_ci": {
            "provider": "GITHUB_ACTIONS",
            "repository": "yangyy816/project-mirror",
            "workflow_identity": ".github/workflows/ci.yml",
            "run_id": 1,
            "head_sha": implementation_sha,
            "result": "PASS",
            "required_jobs": list(registry.REGISTRY_REQUIRED_CI_JOBS),
            "artifact_manifest_digest": "2" * 64,
        },
        "principal_acceptance": {
            "status": "PRINCIPAL_ACCEPTED",
            "accepted_implementation_sha": implementation_sha,
            "acceptance_authority_digest": "3" * 64,
            "accepted_at_utc": TIMESTAMP,
        },
        "authorized_scope": registry.REGISTRY_AUTHORIZED_SCOPE,
        "prohibited_scope": list(registry.REGISTRY_PROHIBITED_SCOPE),
        "canonicalization_version": registry.CANONICALIZATION_VERSION,
        "record_created_at_utc": TIMESTAMP,
    }
    record["record_digest"] = mirror_demo_digest(
        registry.REGISTRY_IMPLEMENTATION_ACCEPTANCE_SCHEMA,
        record,
    )
    acceptance_path = authority_repository / registry.REGISTRY_IMPLEMENTATION_ACCEPTANCE_PATH
    acceptance_path.parent.mkdir(parents=True, exist_ok=True)
    acceptance_path.write_bytes(canonical_json_bytes(record))
    _git(authority_repository, "add", "--", registry.REGISTRY_IMPLEMENTATION_ACCEPTANCE_PATH)
    _git(authority_repository, "commit", "--quiet", "-m", "test: accept registry implementation")
    acceptance_sha = _git(authority_repository, "rev-parse", "HEAD").decode().strip()
    _git(
        authority_repository,
        "update-ref",
        registry.REGISTRY_IMPLEMENTATION_ACCEPTANCE_REF,
        acceptance_sha,
    )
    _git(authority_repository, "checkout", "--quiet", "--detach", implementation_sha)

    AUTHORITY = registry._load_accepted_root_receipt_authority(
        authority_repository,
        running_source=authority_repository / registry.REGISTRY_SOURCE_REPO_PATH,
        created_at_utc=TIMESTAMP,
    )
    return authority_repository, implementation_sha, acceptance_sha


def _root(tmp_path: Path) -> Path:
    parent = tmp_path / "private-parent"
    if not parent.exists():
        parent.mkdir(mode=0o700)
    return parent / registry.EVIDENCE_ROOT_BASENAME


def _create_root(tmp_path: Path) -> Path:
    root = _root(tmp_path)
    registry.create_evidence_root(root, AUTHORITY, excluded_roots=[])
    return root


def _name_and_seal(
    root: Path,
    *,
    output_id: str = "output-1",
    allocation_sequence: int = 1,
    logical_name: str = "candidate.bin",
) -> tuple[str, str]:
    name = registry.allocate_output_name_receipt(
        root,
        AUTHORITY,
        output_id=output_id,
        allocation_sequence=allocation_sequence,
        semantic_role="SOURCE_CANDIDATE",
        logical_name=logical_name,
        producer_task_id=registry.SOURCE_PRODUCER_TASK_ID,
        expected_parent_authority="d" * 64,
        expected_media_type="application/octet-stream",
        maximum_bytes=1024,
        allocated_at_utc=TIMESTAMP,
    )
    name_file = f"D02_R2_OUTPUT_NAME_RECEIPT__{allocation_sequence:08d}__" + output_id + ".json"
    destination = registry.output_path_for_principal(root, AUTHORITY, name_file)
    with destination.open("xb") as handle:
        handle.write(b"synthetic-only-test-bytes")
    seal = registry.seal_output(
        root,
        AUTHORITY,
        name_file,
        media_type="application/octet-stream",
        sealed_at_utc=TIMESTAMP,
    )
    seal_file = f"D02_R2_OUTPUT_SEAL_RECEIPT__{allocation_sequence:08d}__" + output_id + ".json"
    assert name["name_receipt_digest"] == seal["name_receipt_digest"]
    return name_file, seal_file


def _registry_paths(root: Path) -> tuple[Path, Path]:
    return registry._registry_paths(root)


def test_root_receipt_is_first_file_and_exactly_replays(tmp_path: Path) -> None:
    root = _root(tmp_path)

    created = registry.create_evidence_root(root, AUTHORITY, excluded_roots=[])

    assert [entry.name for entry in root.iterdir()] == [registry.ROOT_RECEIPT_LOGICAL_NAME]
    assert registry.load_root_name_receipt(root, AUTHORITY) == created
    assert registry.create_evidence_root(root, AUTHORITY, excluded_roots=[]) == created


def test_root_rejects_collision_corruption_and_escape(tmp_path: Path) -> None:
    root = _create_root(tmp_path)
    receipt_path = root / registry.ROOT_RECEIPT_LOGICAL_NAME
    receipt_path.write_bytes(receipt_path.read_bytes().replace(b'"D02_R2_', b'"X02_R2_', 1))

    with pytest.raises(registry.D02R2RegistryError, match="COLLISION_STOP"):
        registry.create_evidence_root(root, AUTHORITY, excluded_roots=[])

    escaped = tmp_path / "outside" / registry.EVIDENCE_ROOT_BASENAME
    escaped.parent.mkdir()
    with pytest.raises(registry.D02R2RegistryError, match="COLLISION_STOP"):
        registry.create_evidence_root(escaped, AUTHORITY, excluded_roots=[tmp_path])


def test_root_rejects_untrusted_authorities_and_preexisting_foreign_objects(
    tmp_path: Path,
) -> None:
    root = _root(tmp_path)
    bad_plan = object.__new__(registry.RootReceiptAuthority)
    object.__setattr__(bad_plan, "accepted_plan_sha", registry.ACCEPTED_PLAN_SHA)
    object.__setattr__(bad_plan, "accepted_plan_tree", registry.ACCEPTED_PLAN_TREE)
    object.__setattr__(bad_plan, "registry_implementation_sha", "c" * 40)
    object.__setattr__(bad_plan, "created_at_utc", TIMESTAMP)
    object.__setattr__(bad_plan, "_repository_root", tmp_path)
    object.__setattr__(bad_plan, "_acceptance_checkpoint_sha", "d" * 40)
    object.__setattr__(bad_plan, "_acceptance_record_digest", "e" * 64)
    object.__setattr__(bad_plan, "_trust_token", object())
    with pytest.raises(registry.D02R2RegistryError, match="COLLISION_STOP"):
        registry.create_evidence_root(root, bad_plan, excluded_roots=[])
    assert not root.exists()

    root.mkdir(mode=0o700)
    (root / "foreign-object").write_bytes(b"must-not-be-overwritten")
    with pytest.raises(registry.D02R2RegistryError, match="COLLISION_STOP"):
        registry.create_evidence_root(root, AUTHORITY, excluded_roots=[])
    assert (root / "foreign-object").read_bytes() == b"must-not-be-overwritten"


def test_acceptance_loader_rejects_missing_record_and_arbitrary_implementation_sha(
    _accepted_registry_authority: tuple[Path, str, str],
) -> None:
    authority_repository, implementation_sha, acceptance_sha = _accepted_registry_authority
    running_source = authority_repository / registry.REGISTRY_SOURCE_REPO_PATH

    _git(
        authority_repository,
        "update-ref",
        registry.REGISTRY_IMPLEMENTATION_ACCEPTANCE_REF,
        implementation_sha,
    )
    with pytest.raises(registry.D02R2RegistryError, match="COLLISION_STOP"):
        registry._load_accepted_root_receipt_authority(
            authority_repository,
            running_source=running_source,
            created_at_utc=TIMESTAMP,
        )

    _git(authority_repository, "checkout", "--quiet", "--detach", acceptance_sha)
    acceptance_path = authority_repository / registry.REGISTRY_IMPLEMENTATION_ACCEPTANCE_PATH
    record = registry._parse_canonical_json_bytes(acceptance_path.read_bytes())
    record["registry_implementation_sha"] = "c" * 40
    review = registry._require_json_object(record["independent_review"], "independent review")
    review["reviewed_implementation_sha"] = "c" * 40
    ci = registry._require_json_object(record["same_sha_ci"], "same-SHA CI")
    ci["head_sha"] = "c" * 40
    principal = registry._require_json_object(
        record["principal_acceptance"], "Principal acceptance"
    )
    principal["accepted_implementation_sha"] = "c" * 40
    record_without_digest = {key: value for key, value in record.items() if key != "record_digest"}
    record["record_digest"] = mirror_demo_digest(
        registry.REGISTRY_IMPLEMENTATION_ACCEPTANCE_SCHEMA,
        record_without_digest,
    )
    acceptance_path.write_bytes(canonical_json_bytes(record))
    _git(authority_repository, "add", "--", registry.REGISTRY_IMPLEMENTATION_ACCEPTANCE_PATH)
    _git(authority_repository, "commit", "--quiet", "-m", "test: forged implementation authority")
    forged_acceptance_sha = _git(authority_repository, "rev-parse", "HEAD").decode().strip()
    _git(
        authority_repository,
        "update-ref",
        registry.REGISTRY_IMPLEMENTATION_ACCEPTANCE_REF,
        forged_acceptance_sha,
    )
    _git(authority_repository, "checkout", "--quiet", "--detach", implementation_sha)
    try:
        with pytest.raises(registry.D02R2RegistryError, match="COLLISION_STOP"):
            registry._load_accepted_root_receipt_authority(
                authority_repository,
                running_source=running_source,
                created_at_utc=TIMESTAMP,
            )
    finally:
        _git(
            authority_repository,
            "update-ref",
            registry.REGISTRY_IMPLEMENTATION_ACCEPTANCE_REF,
            acceptance_sha,
        )


def test_root_rejects_reparse_points_and_insufficient_capacity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _root(tmp_path)
    no_space = shutil.disk_usage(tmp_path)._replace(free=0)
    with monkeypatch.context() as patch:
        patch.setattr(shutil, "disk_usage", lambda _: no_space)
        with pytest.raises(registry.D02R2RegistryError, match="COLLISION_STOP"):
            registry.create_evidence_root(root, AUTHORITY, excluded_roots=[])

    linked_root = tmp_path / "linked" / registry.EVIDENCE_ROOT_BASENAME
    linked_root.parent.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(registry.D02R2RegistryError, match="COLLISION_STOP"):
        registry.create_evidence_root(linked_root, AUTHORITY, excluded_roots=[])


def test_initialization_replays_exact_sqlite_contract_and_append_only(tmp_path: Path) -> None:
    root = _create_root(tmp_path)

    assert registry.initialize_registry_pair(root, AUTHORITY) == "REGISTRY_READY_EMPTY"
    root_receipt = registry.load_root_name_receipt(root, AUTHORITY)
    path_a, path_b = _registry_paths(root)
    assert (
        registry.validate_registry_copy(
            path_a, registry.REGISTRY_COPY_A_ID, root_receipt
        ).event_count
        == 0
    )
    assert (
        registry.validate_registry_copy(
            path_b, registry.REGISTRY_COPY_B_ID, root_receipt
        ).event_count
        == 0
    )

    connection = registry._open_registry(path_a)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="REGISTRY_APPEND_ONLY"):
            connection.execute("UPDATE registry_metadata SET schema_version = 'changed'")
        with pytest.raises(sqlite3.IntegrityError, match="REGISTRY_APPEND_ONLY"):
            connection.execute("DELETE FROM registry_metadata")
    finally:
        connection.close()


def test_name_allocation_replays_exactly_and_rejects_all_collision_domains(
    tmp_path: Path,
) -> None:
    root = _create_root(tmp_path)
    arguments: dict[str, Any] = {
        "output_id": "allocation-one",
        "allocation_sequence": 1,
        "semantic_role": "SOURCE_CANDIDATE",
        "logical_name": "candidate.bin",
        "producer_task_id": registry.SOURCE_PRODUCER_TASK_ID,
        "expected_parent_authority": "d" * 64,
        "expected_media_type": "application/octet-stream",
        "maximum_bytes": 1024,
        "allocated_at_utc": TIMESTAMP,
    }
    first = registry.allocate_output_name_receipt(root, AUTHORITY, **arguments)
    assert registry.allocate_output_name_receipt(root, AUTHORITY, **arguments) == first

    for changes in (
        {"allocation_sequence": 2},
        {"output_id": "allocation-two"},
        {
            "output_id": "allocation-three",
            "allocation_sequence": 3,
        },
    ):
        conflicting = {**arguments, **changes}
        with pytest.raises(registry.D02R2RegistryError, match="COLLISION_STOP"):
            registry.allocate_output_name_receipt(root, AUTHORITY, **conflicting)


@pytest.mark.parametrize(
    "drift_sql",
    [
        "DROP TRIGGER trg_registry_events_no_update",
        "CREATE TABLE unknown_application_object (value TEXT)",
        "PRAGMA user_version=2",
    ],
)
def test_registry_rejects_ddl_object_and_pragma_drift(tmp_path: Path, drift_sql: str) -> None:
    root = _create_root(tmp_path)
    registry.initialize_registry_pair(root, AUTHORITY)
    root_receipt = registry.load_root_name_receipt(root, AUTHORITY)
    path_a, _ = _registry_paths(root)
    connection = sqlite3.connect(path_a)
    try:
        connection.execute(drift_sql)
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(registry.D02R2RegistryError, match="CORRUPTION_STOP"):
        registry.validate_registry_copy(path_a, registry.REGISTRY_COPY_A_ID, root_receipt)


def test_registry_rejects_sqlite_sidecars_and_copy_id_swap(tmp_path: Path) -> None:
    root = _create_root(tmp_path)
    registry.initialize_registry_pair(root, AUTHORITY)
    path_a, path_b = _registry_paths(root)
    sidecar = Path(f"{path_a}-wal")
    sidecar.write_bytes(b"unexpected")
    with pytest.raises(registry.D02R2RegistryError, match="CORRUPTION_STOP"):
        registry.initialize_registry_pair(root, AUTHORITY)
    sidecar.unlink()

    temporary = path_a.with_name("registry-swap-temporary.sqlite3")
    path_a.rename(temporary)
    path_b.rename(path_a)
    temporary.rename(path_b)
    with pytest.raises(registry.D02R2RegistryError, match="CORRUPTION_STOP"):
        registry.initialize_registry_pair(root, AUTHORITY)


def test_deferred_circular_foreign_keys_and_singleton_role_constraint(tmp_path: Path) -> None:
    root = _create_root(tmp_path)
    registry.initialize_registry_pair(root, AUTHORITY)
    path_a, _ = _registry_paths(root)
    connection = registry._open_registry(path_a)
    try:
        genesis = connection.execute(
            "SELECT common_genesis_digest FROM registry_metadata WHERE singleton = 1"
        ).fetchone()[0]
        connection.execute("BEGIN IMMEDIATE")
        transaction_id = "1" * 64
        event_digest = "2" * 64
        connection.execute(
            """
            INSERT INTO registry_transactions VALUES (?, 'one', 'SOURCE_GENERATION_PREREGISTRATION',
              ?, ?, 1, ?, 'COPY_PREPARED', ?)
            """,
            (transaction_id, "3" * 64, "4" * 64, event_digest, TIMESTAMP),
        )
        connection.execute(
            """
            INSERT INTO registry_events VALUES (
              1, ?, 'one', 'SOURCE_GENERATION_PREREGISTRATION', ?, ?, ?, ?, ?, ?
            )
            """,
            (transaction_id, "3" * 64, "5" * 64, "6" * 64, genesis, event_digest, b"{}"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO registry_transactions VALUES (
                  ?, 'two', 'SOURCE_GENERATION_PREREGISTRATION', ?, ?, 2, ?,
                  'COPY_PREPARED', ?
                )
                """,
                ("8" * 64, "9" * 64, "a" * 64, "c" * 64, TIMESTAMP),
            )
            connection.execute(
                """
                INSERT INTO registry_events VALUES (
                  2, ?, 'two', 'SOURCE_GENERATION_PREREGISTRATION', ?, ?, ?, ?, ?, ?
                )
                """,
                ("8" * 64, "9" * 64, "d" * 64, "e" * 64, event_digest, "c" * 64, b"{}"),
            )
        connection.rollback()
    finally:
        connection.close()


def test_register_replays_intent_event_commit_and_hides_absolute_locator(tmp_path: Path) -> None:
    root = _create_root(tmp_path)
    name_file, seal_file = _name_and_seal(root)

    commit = registry.register_sealed_output(
        root, AUTHORITY, name_file, seal_file, intent_created_at_utc=TIMESTAMP
    )
    assert (
        registry.register_sealed_output(
            root, AUTHORITY, name_file, seal_file, intent_created_at_utc=TIMESTAMP
        )
        == commit
    )

    path_a, path_b = _registry_paths(root)
    root_receipt = registry.load_root_name_receipt(root, AUTHORITY)
    snapshot_a = registry.validate_registry_copy(path_a, registry.REGISTRY_COPY_A_ID, root_receipt)
    snapshot_b = registry.validate_registry_copy(path_b, registry.REGISTRY_COPY_B_ID, root_receipt)
    assert snapshot_a == snapshot_b
    connection = registry._open_registry(path_a)
    try:
        event = connection.execute("SELECT canonical_event_json FROM registry_events").fetchone()[0]
    finally:
        connection.close()
    assert str(root).encode() not in event
    assert b"OPAQUE_LOCATOR" in event and b"r2rel1:" in event


def test_initialization_recovers_only_empty_peer_and_rejects_missing_historical_peer(
    tmp_path: Path,
) -> None:
    root = _create_root(tmp_path)
    assert registry.initialize_registry_pair(root, AUTHORITY) == "REGISTRY_READY_EMPTY"
    path_a, path_b = _registry_paths(root)
    path_b.unlink()
    assert registry.initialize_registry_pair(root, AUTHORITY) == "REGISTRY_READY_EMPTY"

    name_file, seal_file = _name_and_seal(root)
    registry.register_sealed_output(
        root, AUTHORITY, name_file, seal_file, intent_created_at_utc=TIMESTAMP
    )
    path_a.unlink()
    with pytest.raises(registry.D02R2RegistryError, match="REGISTRY_INCONSISTENT_STOP"):
        registry.initialize_registry_pair(root, AUTHORITY)


def test_divergence_and_interrupted_first_copy_require_fail_closed_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _create_root(tmp_path)
    name_file, seal_file = _name_and_seal(root)
    original_append: Callable[..., None] = registry._append_registry_copy
    calls = 0

    def interrupt_after_a(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated interruption before copy B")
        original_append(*args, **kwargs)

    monkeypatch.setattr(registry, "_append_registry_copy", interrupt_after_a)
    with pytest.raises(OSError, match="simulated interruption"):
        registry.register_sealed_output(
            root, AUTHORITY, name_file, seal_file, intent_created_at_utc=TIMESTAMP
        )
    with pytest.raises(registry.D02R2RegistryError, match="REGISTRY_INCONSISTENT_STOP"):
        registry.initialize_registry_pair(root, AUTHORITY)
    monkeypatch.setattr(registry, "_append_registry_copy", original_append)
    recovery = registry.recover_registry_transaction(
        root,
        AUTHORITY,
        name_file,
        seal_file,
        recovery_attempt=1,
        principal_authority_digest="f" * 64,
        created_at_utc=TIMESTAMP,
    )
    assert recovery["observed_prior_state"] == "REGISTRY_ONE_COPY_PREPARED_STOP"
    assert recovery["recovery_outcome"] == "COMMITTED_BOTH_COPIES"
    assert registry.initialize_registry_pair(root, AUTHORITY) == "REGISTRY_READY_REPLAYED"


def test_recovery_replays_intent_when_both_copies_are_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _create_root(tmp_path)
    name_file, seal_file = _name_and_seal(root)
    original_append: Callable[..., None] = registry._append_registry_copy

    def interrupt_before_a(*args: object, **kwargs: object) -> None:
        raise OSError("simulated interruption before copy A")

    monkeypatch.setattr(registry, "_append_registry_copy", interrupt_before_a)
    with pytest.raises(OSError, match="simulated interruption"):
        registry.register_sealed_output(
            root, AUTHORITY, name_file, seal_file, intent_created_at_utc=TIMESTAMP
        )
    monkeypatch.setattr(registry, "_append_registry_copy", original_append)
    with pytest.raises(registry.D02R2RegistryError, match="REGISTRY_RECOVERY_REQUIRED"):
        registry.initialize_registry_pair(root, AUTHORITY)

    recovery = registry.recover_registry_transaction(
        root,
        AUTHORITY,
        name_file,
        seal_file,
        recovery_attempt=1,
        principal_authority_digest="f" * 64,
        created_at_utc=TIMESTAMP,
    )
    assert recovery["observed_prior_state"] == "INTENT_DURABLE_BOTH_COPIES_ABSENT"
    assert registry.initialize_registry_pair(root, AUTHORITY) == "REGISTRY_READY_REPLAYED"


def test_recovery_creates_missing_intent_from_seal_only(tmp_path: Path) -> None:
    root = _create_root(tmp_path)
    name_file, seal_file = _name_and_seal(root)

    recovery = registry.recover_registry_transaction(
        root,
        AUTHORITY,
        name_file,
        seal_file,
        recovery_attempt=1,
        principal_authority_digest="f" * 64,
        created_at_utc=TIMESTAMP,
        intent_created_at_utc=TIMESTAMP,
    )
    assert recovery["observed_prior_state"] == "SEAL_DURABLE_INTENT_ABSENT"
    assert recovery["observed_intent_digest"] is None
    assert recovery["resulting_intent_digest"] is not None
    assert registry.initialize_registry_pair(root, AUTHORITY) == "REGISTRY_READY_REPLAYED"


def test_recovery_seals_durable_output_at_the_preallocated_path(tmp_path: Path) -> None:
    root = _create_root(tmp_path)
    output_id = "output-seal-recovery"
    name_file = f"D02_R2_OUTPUT_NAME_RECEIPT__00000001__{output_id}.json"
    seal_file = f"D02_R2_OUTPUT_SEAL_RECEIPT__00000001__{output_id}.json"
    registry.allocate_output_name_receipt(
        root,
        AUTHORITY,
        output_id=output_id,
        allocation_sequence=1,
        semantic_role="SOURCE_CANDIDATE",
        logical_name="candidate.bin",
        producer_task_id=registry.SOURCE_PRODUCER_TASK_ID,
        expected_parent_authority="d" * 64,
        expected_media_type="application/octet-stream",
        maximum_bytes=1024,
        allocated_at_utc=TIMESTAMP,
    )
    destination = registry.output_path_for_principal(root, AUTHORITY, name_file)
    with destination.open("xb") as handle:
        handle.write(b"synthetic-only-test-bytes")

    recovery = registry.recover_output_seal(
        root,
        AUTHORITY,
        name_file,
        media_type="application/octet-stream",
        sealed_at_utc=TIMESTAMP,
        recovery_attempt=1,
        principal_authority_digest="f" * 64,
        created_at_utc=TIMESTAMP,
    )
    assert recovery["observed_prior_state"] == "OUTPUT_DURABLE_SEAL_ABSENT"
    assert (root / "control" / "seal-receipts" / seal_file).is_file()

    transaction_recovery = registry.recover_registry_transaction(
        root,
        AUTHORITY,
        name_file,
        seal_file,
        recovery_attempt=2,
        principal_authority_digest="f" * 64,
        created_at_utc=TIMESTAMP,
        intent_created_at_utc=TIMESTAMP,
    )
    assert transaction_recovery["recovery_outcome"] == "COMMITTED_BOTH_COPIES"


def test_recovery_publishes_commit_after_both_copies_are_prepared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _create_root(tmp_path)
    name_file, seal_file = _name_and_seal(root)
    original_write: Callable[..., None] = registry._write_exclusive_json

    def interrupt_before_commit(
        write_root: Path,
        path: Path,
        payload: Mapping[str, object],
        *,
        maximum_bytes: int,
    ) -> None:
        if path.name.startswith("D02_R2_REGISTRY_COMMIT_RECEIPT__"):
            raise OSError("simulated interruption before commit receipt")
        original_write(write_root, path, payload, maximum_bytes=maximum_bytes)

    monkeypatch.setattr(registry, "_write_exclusive_json", interrupt_before_commit)
    with pytest.raises(OSError, match="simulated interruption"):
        registry.register_sealed_output(
            root, AUTHORITY, name_file, seal_file, intent_created_at_utc=TIMESTAMP
        )
    monkeypatch.setattr(registry, "_write_exclusive_json", original_write)
    with pytest.raises(registry.D02R2RegistryError, match="REGISTRY_RECOVERY_REQUIRED"):
        registry.initialize_registry_pair(root, AUTHORITY)

    recovery = registry.recover_registry_transaction(
        root,
        AUTHORITY,
        name_file,
        seal_file,
        recovery_attempt=1,
        principal_authority_digest="f" * 64,
        created_at_utc=TIMESTAMP,
    )
    assert recovery["observed_prior_state"] == "BOTH_COPIES_PREPARED_NOT_COMMITTED"
    assert registry.initialize_registry_pair(root, AUTHORITY) == "REGISTRY_READY_REPLAYED"


def test_corrupt_intent_is_preserved_and_consumes_recovery_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _create_root(tmp_path)
    name_file, seal_file = _name_and_seal(root)
    original_append: Callable[..., None] = registry._append_registry_copy

    def interrupt_before_a(*args: object, **kwargs: object) -> None:
        raise OSError("simulated interruption before copy A")

    monkeypatch.setattr(registry, "_append_registry_copy", interrupt_before_a)
    with pytest.raises(OSError):
        registry.register_sealed_output(
            root, AUTHORITY, name_file, seal_file, intent_created_at_utc=TIMESTAMP
        )
    monkeypatch.setattr(registry, "_append_registry_copy", original_append)
    intent_path = next((root / "control" / "registry-intents").iterdir())
    original_bytes = intent_path.read_bytes()
    intent_path.write_bytes(original_bytes[:-1])

    with pytest.raises(
        registry.D02R2RegistryError,
        match="REGISTRY_INTENT_PARTIAL_OR_CORRUPT_STOP",
    ):
        registry.recover_registry_transaction(
            root,
            AUTHORITY,
            name_file,
            seal_file,
            recovery_attempt=1,
            principal_authority_digest="f" * 64,
            created_at_utc=TIMESTAMP,
        )
    assert intent_path.read_bytes() == original_bytes[:-1]
    recovery_files = list((root / "control" / "registry-recovery").iterdir())
    assert len(recovery_files) == 1


def test_corrupt_commit_receipt_is_preserved_and_recovery_stops(tmp_path: Path) -> None:
    root = _create_root(tmp_path)
    name_file, seal_file = _name_and_seal(root)
    registry.register_sealed_output(
        root, AUTHORITY, name_file, seal_file, intent_created_at_utc=TIMESTAMP
    )
    commit_path = next((root / "control" / "registry-commits").iterdir())
    original_bytes = commit_path.read_bytes()
    commit_path.write_bytes(original_bytes[:-1])

    with pytest.raises(
        registry.D02R2RegistryError,
        match="REGISTRY_COMMIT_RECEIPT_PARTIAL_OR_CORRUPT_STOP",
    ):
        registry.recover_registry_transaction(
            root,
            AUTHORITY,
            name_file,
            seal_file,
            recovery_attempt=1,
            principal_authority_digest="f" * 64,
            created_at_utc=TIMESTAMP,
        )
    assert commit_path.read_bytes() == original_bytes[:-1]
    assert len(list((root / "control" / "registry-recovery").iterdir())) == 1


def test_corrupt_recovery_receipt_stops_fresh_registry_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _create_root(tmp_path)
    name_file, seal_file = _name_and_seal(root)
    original_append: Callable[..., None] = registry._append_registry_copy

    def interrupt_before_a(*args: object, **kwargs: object) -> None:
        raise OSError("simulated interruption before copy A")

    monkeypatch.setattr(registry, "_append_registry_copy", interrupt_before_a)
    with pytest.raises(OSError, match="simulated interruption"):
        registry.register_sealed_output(
            root, AUTHORITY, name_file, seal_file, intent_created_at_utc=TIMESTAMP
        )
    monkeypatch.setattr(registry, "_append_registry_copy", original_append)

    registry.recover_registry_transaction(
        root,
        AUTHORITY,
        name_file,
        seal_file,
        recovery_attempt=1,
        principal_authority_digest="f" * 64,
        created_at_utc=TIMESTAMP,
    )
    recovery_path = next((root / "control" / "registry-recovery").iterdir())
    original_bytes = recovery_path.read_bytes()
    recovery_path.write_bytes(original_bytes[:-1])

    with pytest.raises(registry.D02R2RegistryError, match="CORRUPTION_STOP"):
        registry.initialize_registry_pair(root, AUTHORITY)
    assert recovery_path.read_bytes() == original_bytes[:-1]


@pytest.mark.parametrize(
    "corrupt_authority",
    ("name", "seal", "intent", "commit", "output", "recovery"),
)
def test_recovery_validates_complete_committed_prefix_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corrupt_authority: str,
) -> None:
    root = _create_root(tmp_path)
    name_file_1, seal_file_1 = _name_and_seal(root)
    original_append: Callable[..., None] = registry._append_registry_copy

    def interrupt_before_a(*args: object, **kwargs: object) -> None:
        raise OSError("simulated interruption before copy A")

    monkeypatch.setattr(registry, "_append_registry_copy", interrupt_before_a)
    with pytest.raises(OSError, match="simulated interruption"):
        registry.register_sealed_output(
            root,
            AUTHORITY,
            name_file_1,
            seal_file_1,
            intent_created_at_utc=TIMESTAMP,
        )
    monkeypatch.setattr(registry, "_append_registry_copy", original_append)
    registry.recover_registry_transaction(
        root,
        AUTHORITY,
        name_file_1,
        seal_file_1,
        recovery_attempt=1,
        principal_authority_digest="f" * 64,
        created_at_utc=TIMESTAMP,
    )

    name_file_2, seal_file_2 = _name_and_seal(
        root,
        output_id="output-2",
        allocation_sequence=2,
        logical_name="candidate-2.bin",
    )
    monkeypatch.setattr(registry, "_append_registry_copy", interrupt_before_a)
    with pytest.raises(OSError, match="simulated interruption"):
        registry.register_sealed_output(
            root,
            AUTHORITY,
            name_file_2,
            seal_file_2,
            intent_created_at_utc=TIMESTAMP,
        )
    monkeypatch.setattr(registry, "_append_registry_copy", original_append)

    commit_path = next((root / "control" / "registry-commits").iterdir())
    transaction_id = commit_path.stem.removeprefix("D02_R2_REGISTRY_COMMIT_RECEIPT__")
    prior_paths = {
        "name": root / "control" / "name-receipts" / name_file_1,
        "seal": root / "control" / "seal-receipts" / seal_file_1,
        "intent": (
            root
            / "control"
            / "registry-intents"
            / f"D02_R2_REGISTRY_TRANSACTION_INTENT__{transaction_id}.json"
        ),
        "commit": commit_path,
        "output": registry.output_path_for_principal(root, AUTHORITY, name_file_1),
        "recovery": next((root / "control" / "registry-recovery").iterdir()),
    }
    corrupted_path = prior_paths[corrupt_authority]
    original_bytes = corrupted_path.read_bytes()
    corrupted_path.write_bytes(original_bytes[:-1])

    path_a, path_b = _registry_paths(root)
    root_receipt = registry.load_root_name_receipt(root, AUTHORITY)

    def durable_state() -> tuple[int, int, int, int, int]:
        return (
            registry.validate_registry_copy(
                path_a, registry.REGISTRY_COPY_A_ID, root_receipt
            ).event_count,
            registry.validate_registry_copy(
                path_b, registry.REGISTRY_COPY_B_ID, root_receipt
            ).event_count,
            len(list((root / "control" / "registry-intents").iterdir())),
            len(list((root / "control" / "registry-commits").iterdir())),
            len(list((root / "control" / "registry-recovery").iterdir())),
        )

    before = durable_state()
    with pytest.raises(registry.D02R2RegistryError):
        registry.recover_registry_transaction(
            root,
            AUTHORITY,
            name_file_2,
            seal_file_2,
            recovery_attempt=1,
            principal_authority_digest="f" * 64,
            created_at_utc=TIMESTAMP,
        )
    assert durable_state() == before
    assert corrupted_path.read_bytes() == original_bytes[:-1]
