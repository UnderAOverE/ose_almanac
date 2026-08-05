#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : changes.py.                                                                         #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Drift extractor - key-level change events from stored version pairs.                #
# Dependencies  : repositories (configmaps, configmaps_historical, changes), changes models.          #
# Modifications : 2026-08-05 Shane Reddy - initial.                                                   #
#                                                                                                     #
# Contact       : shanevreddy@gmail.com.                                                              #
#                                                                                                     #
# ----------------------------------------------------------------------------------------------------#
#
#


# ----------------------------------------------------------------------------------------------------#
# Imports.                                                                                            #
# ----------------------------------------------------------------------------------------------------#

import sys

sys.dont_write_bytecode = True

# External imports

from datetime import (
    datetime,
    timezone,
)
from typing import (
    Any,
    Self,
)

from motor.motor_asyncio import AsyncIOMotorClient

# Internal imports

from src.batch.models.ose_almanac.changes import (
    ChangeEventModel,
    ChangeType,
)
from src.batch.models.ose_almanac.configmaps import ConfigMapRecordModel
from src.batch.repositories.ose_almanac.changes import ChangesMotorRepository
from src.batch.repositories.ose_almanac.configmaps import ConfigMapsMotorRepository
from src.batch.repositories.ose_almanac.configmaps_historical import ConfigMapsHistoricalMotorRepository
from src.common.logger import logger

# Internal constants

module_version: str = "1.0.0v"

BATCH_SIZE: int = 1000


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

def _latest_manager(
        managed_fields: list[dict[str, Any]],
) -> tuple[str | None, datetime | None]:

    """
    Recovers who last touched the object from its managedFields entries - the cluster's own
    note of which tool wrote which part, and when. "kubectl" here means a human edited the
    object by hand.

    :param managed_fields: metadata.managedFields as stored, verbatim.
    :type managed_fields: list[dict[str, Any]]
    :return: (manager name, operation time), either None when unavailable.
    :rtype: tuple[str | None, datetime | None]
    """

    latest_manager: str | None = None
    latest_time: datetime | None = None

    for entry in managed_fields:
        raw_time = entry.get("time")

        if not isinstance(raw_time, str):
            continue

        # endIf

        try:
            parsed = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))

        except ValueError:
            continue

        # endTryExcept

        if latest_time is None or parsed > latest_time:
            latest_time = parsed
            latest_manager = entry.get("manager")

        # endIf

    # endFor

    return latest_manager, latest_time

# endDef


def build_change_event(
        current: ConfigMapRecordModel,
        predecessor: ConfigMapRecordModel | None,
        computed_at: datetime,
) -> ChangeEventModel | None:

    """
    Builds one change event from a current version and its most recent predecessor, purely
    from stored per-key hashes - no value parsing. Returns None when the pair carries no
    change worth reporting (a duplicate predecessor from a crash between the two collector
    writes, which is harmless by design).

    :param current: the current stored version.
    :type current: ConfigMapRecordModel
    :param predecessor: the latest superseded version, or None when this is the first.
    :type predecessor: ConfigMapRecordModel | None
    :param computed_at: run timestamp stamped on the event (UTC).
    :type computed_at: datetime
    :return: the event, or None when there is nothing to report.
    :rtype: ChangeEventModel | None
    """

    manager, manager_time = _latest_manager(current.managed_fields)
    redacted_keys = {record.key for record in current.redactions}

    if predecessor is None:
        return ChangeEventModel(
            cluster_name=current.cluster_name,
            namespace=current.namespace,
            configmap_name=current.name,
            new_content_hash=current.content_hash,
            environment=current.environment,
            sector=current.sector,
            change_type=ChangeType.CREATED,
            observed_at=current.first_seen,
            added_keys=sorted(current.key_hashes),
            credential_change=bool(redacted_keys),
            manager=manager,
            manager_operation_time=manager_time,
            computed_at=computed_at,
        )

    # endIf

    if predecessor.content_hash == current.content_hash:
        return None

    # endIf

    changed_keys = sorted(
        key
        for key, digest in current.key_hashes.items()
        if key in predecessor.key_hashes and predecessor.key_hashes[key] != digest
    )
    added_keys = sorted(set(current.key_hashes) - set(predecessor.key_hashes))
    removed_keys = sorted(set(predecessor.key_hashes) - set(current.key_hashes))

    return ChangeEventModel(
        cluster_name=current.cluster_name,
        namespace=current.namespace,
        configmap_name=current.name,
        new_content_hash=current.content_hash,
        previous_content_hash=predecessor.content_hash,
        environment=current.environment,
        sector=current.sector,
        change_type=ChangeType.MODIFIED,
        observed_at=current.first_seen,
        changed_keys=changed_keys,
        added_keys=added_keys,
        removed_keys=removed_keys,
        credential_change=bool(redacted_keys.intersection(changed_keys + added_keys)),
        manager=manager,
        manager_operation_time=manager_time,
        computed_at=computed_at,
    )

# endDef


class DriftExtractorService:

    """
    DriftExtractorService class: derives key-level change events by pairing every current
    ConfigMap version with its most recent superseded version. Runs entirely on stored data
    and upserts events on a stable identity, so recomputes are idempotent. Deletion events
    are deliberately out of scope for now - absence is only trustworthy once several sweeps
    have proven the per-namespace success bookkeeping.
    """

    def __init__(
            self,
            configmaps_repository: ConfigMapsMotorRepository,
            configmaps_historical_repository: ConfigMapsHistoricalMotorRepository,
            changes_repository: ChangesMotorRepository,
    ) -> None:

        """
        DriftExtractorService constructor - all collaborators injected.

        :param configmaps_repository: read access to current ConfigMaps.
        :type configmaps_repository: ConfigMapsMotorRepository
        :param configmaps_historical_repository: read access to superseded versions.
        :type configmaps_historical_repository: ConfigMapsHistoricalMotorRepository
        :param changes_repository: output store.
        :type changes_repository: ChangesMotorRepository
        :return: None.
        :rtype: None
        """

        self._configmaps_repository = configmaps_repository
        self._configmaps_historical_repository = configmaps_historical_repository
        self._changes_repository = changes_repository

    # endDef

    @classmethod
    async def get_service(
            cls,
            mongo_client: AsyncIOMotorClient,
    ) -> Self:

        """
        Wires the extractor from one Mongo client.

        :param mongo_client: shared MongoDB client.
        :type mongo_client: AsyncIOMotorClient
        :return: a ready extractor.
        :rtype: Self
        """

        return cls(
            configmaps_repository=ConfigMapsMotorRepository(mongo_client),
            configmaps_historical_repository=ConfigMapsHistoricalMotorRepository(mongo_client),
            changes_repository=ChangesMotorRepository(mongo_client),
        )

    # endAsyncDef

    async def run(
            self,
            batch_environment: str,
            batch_sector: str,
    ) -> None:

        """
        Recomputes change events for one environment + sector: loads every ConfigMap's most
        recent predecessor in one aggregation, then streams current versions through the
        pairing and upserts events in bounded batches.

        :param batch_environment: environment to compute.
        :type batch_environment: str
        :param batch_sector: sector to compute.
        :type batch_sector: str
        :return: None.
        :rtype: None
        """

        predecessors = {
            (record.cluster_name, record.namespace, record.name): record
            for record in await self._configmaps_historical_repository.find_latest_versions(
                batch_environment, batch_sector
            )
        }

        computed_at = datetime.now(timezone.utc)
        counts = {"created": 0, "modified": 0, "inserted": 0}
        pending: list[ChangeEventModel] = []
        after_id: str | None = None

        while True:
            batch = await self._configmaps_repository.find_batch(
                batch_environment, batch_sector, after_id, BATCH_SIZE
            )

            if not batch:
                break

            # endIf

            for current in batch:
                predecessor = predecessors.get((current.cluster_name, current.namespace, current.name))
                event = build_change_event(current, predecessor, computed_at)

                if event is None:
                    continue

                # endIf

                counts[event.change_type.value] += 1
                pending.append(event)

                if len(pending) >= BATCH_SIZE:
                    counts["inserted"] += await self._changes_repository.upsert_events(pending)
                    pending = []

                # endIf

            # endFor

            after_id = batch[-1].id_

        # endWhile

        if pending:
            counts["inserted"] += await self._changes_repository.upsert_events(pending)

        # endIf

        logger.info(
            "changes_computed environment=%s sector=%s created=%d modified=%d newly_inserted=%d",
            batch_environment,
            batch_sector,
            counts["created"],
            counts["modified"],
            counts["inserted"],
        )

    # endAsyncDef

# endClass


# end_changes.py
