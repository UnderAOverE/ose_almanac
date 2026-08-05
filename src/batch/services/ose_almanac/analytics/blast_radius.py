#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : blast_radius.py.                                                                    #
# Date of birth : 2026-08-05.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Blast-radius extractor - joins stored workloads to stored ConfigMaps.               #
# Dependencies  : repositories (configmaps, workloads, sweeps, blast_radius), blast_radius models.    #
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

from src.batch.models.ose_almanac.blast_radius import (
    BlastRadiusModel,
    OrphanStatus,
    ReferenceKind,
    WorkloadReference,
)
from src.batch.models.ose_almanac.workloads import WorkloadRecordModel
from src.batch.repositories.ose_almanac.blast_radius import BlastRadiusMotorRepository
from src.batch.repositories.ose_almanac.configmaps import ConfigMapsMotorRepository
from src.batch.repositories.ose_almanac.sweeps import SweepsMotorRepository
from src.batch.repositories.ose_almanac.workloads import WorkloadsMotorRepository
from src.common.logger import logger

# Internal constants

module_version: str = "1.0.0v"

BATCH_SIZE: int = 1000


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

def _volume_references(
        pod_template: dict[str, Any],
) -> dict[str, list[tuple[str, list[str], bool, ReferenceKind]]]:

    """
    Collects the ConfigMap references declared by each pod volume.

    :param pod_template: the stored pod-template subtree.
    :type pod_template: dict[str, Any]
    :return: volume name -> list of (configmap name, keys, optional, reference kind).
    :rtype: dict[str, list[tuple[str, list[str], bool, ReferenceKind]]]
    """

    by_volume: dict[str, list[tuple[str, list[str], bool, ReferenceKind]]] = {}

    for volume in pod_template.get("volumes") or []:
        volume_name = volume.get("name", "")
        entries: list[tuple[str, list[str], bool, ReferenceKind]] = []

        configmap_source = volume.get("configMap") or {}

        if configmap_source.get("name"):
            keys = [item.get("key", "") for item in configmap_source.get("items") or []]
            entries.append(
                (configmap_source["name"], keys, bool(configmap_source.get("optional")), ReferenceKind.VOLUME)
            )

        # endIf

        for source in (volume.get("projected") or {}).get("sources") or []:
            projected_configmap = source.get("configMap") or {}

            if projected_configmap.get("name"):
                keys = [item.get("key", "") for item in projected_configmap.get("items") or []]
                entries.append(
                    (
                        projected_configmap["name"],
                        keys,
                        bool(projected_configmap.get("optional")),
                        ReferenceKind.PROJECTED,
                    )
                )

            # endIf

        # endFor

        if entries:
            by_volume[volume_name] = entries

        # endIf

    # endFor

    return by_volume

# endDef


def extract_configmap_references(
        workload: WorkloadRecordModel,
) -> dict[str, list[WorkloadReference]]:

    """
    Extracts every ConfigMap reference from one stored workload's pod-template subtree,
    covering all four hookup shapes: volume mounts, projected volumes, envFrom, and single
    env keys - across containers and init containers. A change only reaches the container
    without a restart through a non-subPath volume mount, so each reference carries a
    restart_required verdict.

    :param workload: the stored workload record.
    :type workload: WorkloadRecordModel
    :return: configmap name -> references from this workload.
    :rtype: dict[str, list[WorkloadReference]]
    """

    references: dict[str, list[WorkloadReference]] = {}
    by_volume = _volume_references(workload.pod_template)
    mounted_volumes: set[str] = set()

    def add(configmap_name: str, reference: WorkloadReference) -> None:

        """
        Appends one reference under its ConfigMap name.

        :param configmap_name: the referenced ConfigMap.
        :type configmap_name: str
        :param reference: the reference to record.
        :type reference: WorkloadReference
        :return: None.
        :rtype: None
        """

        references.setdefault(configmap_name, []).append(reference)

    # endDef

    containers = list(workload.pod_template.get("containers") or [])
    containers.extend(workload.pod_template.get("initContainers") or [])

    for container in containers:
        container_name = container.get("name", "")

        for mount in container.get("volumeMounts") or []:
            volume_name = mount.get("name", "")

            if volume_name not in by_volume:
                continue

            # endIf

            mounted_volumes.add(volume_name)
            sub_path_used = bool(mount.get("subPath"))

            for configmap_name, keys, optional, kind in by_volume[volume_name]:
                add(
                    configmap_name,
                    WorkloadReference(
                        workload_kind=workload.kind.value,
                        workload_name=workload.name,
                        container_name=container_name,
                        reference_kind=kind,
                        keys=keys,
                        sub_path_used=sub_path_used,
                        optional_reference=optional,
                        restart_required=sub_path_used,
                    ),
                )

            # endFor

        # endFor

        for env_source in container.get("envFrom") or []:
            configmap_ref = env_source.get("configMapRef") or {}

            if configmap_ref.get("name"):
                add(
                    configmap_ref["name"],
                    WorkloadReference(
                        workload_kind=workload.kind.value,
                        workload_name=workload.name,
                        container_name=container_name,
                        reference_kind=ReferenceKind.ENV_FROM,
                        optional_reference=bool(configmap_ref.get("optional")),
                        restart_required=True,
                    ),
                )

            # endIf

        # endFor

        for env_entry in container.get("env") or []:
            key_ref = (env_entry.get("valueFrom") or {}).get("configMapKeyRef") or {}

            if key_ref.get("name"):
                add(
                    key_ref["name"],
                    WorkloadReference(
                        workload_kind=workload.kind.value,
                        workload_name=workload.name,
                        container_name=container_name,
                        reference_kind=ReferenceKind.ENV_KEY,
                        keys=[key_ref.get("key", "")],
                        optional_reference=bool(key_ref.get("optional")),
                        restart_required=True,
                    ),
                )

            # endIf

        # endFor

    # endFor

    # A declared volume no container mounts is still a reference - the ConfigMap is part of
    # the pod contract even though nothing reads it yet.
    for volume_name, entries in by_volume.items():
        if volume_name in mounted_volumes:
            continue

        # endIf

        for configmap_name, keys, optional, kind in entries:
            add(
                configmap_name,
                WorkloadReference(
                    workload_kind=workload.kind.value,
                    workload_name=workload.name,
                    container_name=None,
                    reference_kind=kind,
                    keys=keys,
                    optional_reference=optional,
                    restart_required=False,
                ),
            )

        # endFor

    # endFor

    return references

# endDef


class BlastRadiusExtractorService:

    """
    BlastRadiusExtractorService class: computes, for every stored ConfigMap in one
    environment + sector, which collected workloads consume it and how. Reads stored data
    only - never the live cluster - and rebuilds its output scope wholesale, so it is safe
    to re-run at any time. Orphan verdicts are suppressed to indeterminate for any namespace
    whose latest sweep could not list every collected workload kind: an empty blast radius
    must never be manufactured by a missing RBAC verb.
    """

    def __init__(
            self,
            configmaps_repository: ConfigMapsMotorRepository,
            workloads_repository: WorkloadsMotorRepository,
            sweeps_repository: SweepsMotorRepository,
            blast_radius_repository: BlastRadiusMotorRepository,
    ) -> None:

        """
        BlastRadiusExtractorService constructor - all collaborators injected.

        :param configmaps_repository: read access to current ConfigMaps.
        :type configmaps_repository: ConfigMapsMotorRepository
        :param workloads_repository: read access to current workloads.
        :type workloads_repository: WorkloadsMotorRepository
        :param sweeps_repository: read access to sweep outcomes for coverage decisions.
        :type sweeps_repository: SweepsMotorRepository
        :param blast_radius_repository: output store.
        :type blast_radius_repository: BlastRadiusMotorRepository
        :return: None.
        :rtype: None
        """

        self._configmaps_repository = configmaps_repository
        self._workloads_repository = workloads_repository
        self._sweeps_repository = sweeps_repository
        self._blast_radius_repository = blast_radius_repository

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
            workloads_repository=WorkloadsMotorRepository(mongo_client),
            sweeps_repository=SweepsMotorRepository(mongo_client),
            blast_radius_repository=BlastRadiusMotorRepository(mongo_client),
        )

    # endAsyncDef

    async def _covered_namespaces(
            self,
            batch_environment: str,
            batch_sector: str,
    ) -> set[tuple[str, str]]:

        """
        Determines which (cluster, namespace) pairs had complete workload coverage in the
        latest sweep. A sweep that predates workload collection covers nothing.

        :param batch_environment: environment to check.
        :type batch_environment: str
        :param batch_sector: sector to check.
        :type batch_sector: str
        :return: pairs where every collected workload kind listed successfully.
        :rtype: set[tuple[str, str]]
        """

        sweep = await self._sweeps_repository.find_latest(batch_environment, batch_sector)

        if sweep is None or not sweep.workloads_collected:
            return set()

        # endIf

        return {
            (result.cluster_name, result.namespace)
            for result in sweep.namespace_results
            if result.success and not result.workload_kinds_failed
        }

    # endAsyncDef

    async def _build_reference_index(
            self,
            batch_environment: str,
            batch_sector: str,
    ) -> dict[tuple[str, str, str], list[WorkloadReference]]:

        """
        Walks every stored workload in scope, page by page, and indexes its ConfigMap
        references by (cluster, namespace, configmap name).

        :param batch_environment: environment to read.
        :type batch_environment: str
        :param batch_sector: sector to read.
        :type batch_sector: str
        :return: the reference index.
        :rtype: dict[tuple[str, str, str], list[WorkloadReference]]
        """

        index: dict[tuple[str, str, str], list[WorkloadReference]] = {}
        after_id: str | None = None
        workloads_read = 0

        while True:
            batch = await self._workloads_repository.find_batch(
                batch_environment, batch_sector, after_id, BATCH_SIZE
            )

            if not batch:
                break

            # endIf

            workloads_read += len(batch)

            for workload in batch:
                for configmap_name, refs in extract_configmap_references(workload).items():
                    key = (workload.cluster_name, workload.namespace, configmap_name)
                    index.setdefault(key, []).extend(refs)

                # endFor

            # endFor

            after_id = batch[-1].id_

        # endWhile

        logger.info("blast_radius_index_built workloads=%d referenced_configmaps=%d", workloads_read, len(index))
        return index

    # endAsyncDef

    async def run(
            self,
            batch_environment: str,
            batch_sector: str,
    ) -> None:

        """
        Recomputes blast radius for one environment + sector: clears the output scope, then
        streams every stored ConfigMap through the reference index and writes one document
        per ConfigMap in bounded batches.

        :param batch_environment: environment to compute.
        :type batch_environment: str
        :param batch_sector: sector to compute.
        :type batch_sector: str
        :return: None.
        :rtype: None
        """

        covered = await self._covered_namespaces(batch_environment, batch_sector)
        index = await self._build_reference_index(batch_environment, batch_sector)

        deleted = await self._blast_radius_repository.delete_scope(batch_environment, batch_sector)
        computed_at = datetime.now(timezone.utc)

        matched_keys: set[tuple[str, str, str]] = set()
        counts = {"referenced": 0, "no_reference": 0, "indeterminate": 0}
        pending: list[BlastRadiusModel] = []
        after_id: str | None = None

        while True:
            identities = await self._configmaps_repository.find_identities_batch(
                batch_environment, batch_sector, after_id, BATCH_SIZE
            )

            if not identities:
                break

            # endIf

            for identity in identities:
                key = (identity.cluster_name, identity.namespace, identity.name)
                references = index.get(key, [])

                if references:
                    matched_keys.add(key)
                    status = OrphanStatus.REFERENCED
                    counts["referenced"] += 1

                elif (identity.cluster_name, identity.namespace) in covered:
                    status = OrphanStatus.NO_REFERENCE_FOUND
                    counts["no_reference"] += 1

                else:
                    status = OrphanStatus.INDETERMINATE
                    counts["indeterminate"] += 1

                # endIfElifElse

                pending.append(
                    BlastRadiusModel(
                        cluster_name=identity.cluster_name,
                        namespace=identity.namespace,
                        configmap_name=identity.name,
                        environment=batch_environment,
                        sector=batch_sector,
                        references=references,
                        orphan_status=status,
                        coverage_complete=(identity.cluster_name, identity.namespace) in covered,
                        computed_at=computed_at,
                    )
                )

                if len(pending) >= BATCH_SIZE:
                    await self._blast_radius_repository.create_many(pending)
                    pending = []

                # endIf

            # endFor

            after_id = identities[-1].id_

        # endWhile

        if pending:
            await self._blast_radius_repository.create_many(pending)

        # endIf

        # References to ConfigMaps that are not in the store are real operational signal (a
        # workload counting on a map that does not exist), surfaced in the log for now.
        dangling = len(set(index) - matched_keys)

        logger.info(
            "blast_radius_computed environment=%s sector=%s referenced=%d no_reference=%d "
            "indeterminate=%d dangling_references=%d replaced=%d",
            batch_environment,
            batch_sector,
            counts["referenced"],
            counts["no_reference"],
            counts["indeterminate"],
            dangling,
            deleted,
        )

    # endAsyncDef

# endClass


# end_blast_radius.py
