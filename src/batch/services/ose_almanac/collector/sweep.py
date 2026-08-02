#!/usr/bin/env python


#
#
# ----------------------------------------------------------------------------------------------------#
#                                                                                                     #
# File Name     : sweep.py.                                                                           #
# Date of birth : 2026-08-02.                                                                         #
# Version       : 1.0.0.                                                                              #
# Author        : Shane Reddy.                                                                        #
#                                                                                                     #
# Explanation   : Collector orchestration - enumerate, redact, hash, dedup write, record outcome.     #
# Dependencies  : repositories, auth, cluster client, redaction, hashing, settings.                   #
# Modifications : 2026-08-02 Shane Reddy - initial.                                                   #
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

import asyncio
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

from src.batch.config.basesettings.ose_almanac import OSEAlmanacSettings
from src.batch.models.ose_almanac.cluster_registry import ClusterRegistryModel
from src.batch.models.ose_almanac.configmaps import (
    ConfigMapRecordModel,
    RedactionRecord,
)
from src.batch.models.ose_almanac.sweeps import (
    NamespaceSweepResult,
    SweepModel,
    SweepOutcome,
)
from src.batch.repositories.ose_almanac.cluster_registry import ClusterRegistryMotorRepository
from src.batch.repositories.ose_almanac.configmaps import ConfigMapsMotorRepository
from src.batch.repositories.ose_almanac.configmaps_historical import ConfigMapsHistoricalMotorRepository
from src.batch.repositories.ose_almanac.sweeps import SweepsMotorRepository
from src.batch.services.ose_almanac.collector.auth import OSEAuthService
from src.batch.services.ose_almanac.collector.cluster_client import OpenShiftClusterClient
from src.batch.services.ose_almanac.collector.hashing import fingerprint
from src.batch.services.ose_almanac.collector.redaction import Redactor
from src.common.httpx.client import HTTPXClient
from src.common.logger import logger

# Internal constants

module_version: str = "1.0.0v"


# ----------------------------------------------------------------------------------------------------#
# Classes or functions.                                                                               #
# ----------------------------------------------------------------------------------------------------#

class _SweepCounters:

    """Mutable per-run counters shared across namespace tasks."""

    def __init__(self) -> None:

        """
        Initializes all counters to zero.

        :return: None.
        :rtype: None
        """

        self.new = 0
        self.changed = 0
        self.unchanged = 0

    # endDef

# endClass


class OSEAlmanacCollectorService:

    """
    OSEAlmanacCollectorService class: the daily sweep for the OpenShift ConfigMap Intelligence
    Platform. Reads targets from the cluster registry, enumerates in-scope namespaces, redacts
    and fingerprints every ConfigMap, deduplicates by content hash (historical is always
    written before current, so a crash can only ever produce a harmless duplicate, never data
    loss), and records the run outcome per namespace.
    """

    def __init__(
            self,
            cluster_registry_repository: ClusterRegistryMotorRepository,
            configmaps_repository: ConfigMapsMotorRepository,
            configmaps_historical_repository: ConfigMapsHistoricalMotorRepository,
            sweeps_repository: SweepsMotorRepository,
            http_client: HTTPXClient,
            auth_service: OSEAuthService,
            cluster_client: OpenShiftClusterClient,
            redactor: Redactor,
            settings: OSEAlmanacSettings,
    ) -> None:

        """
        OSEAlmanacCollectorService constructor - all collaborators injected.

        :param cluster_registry_repository: read access to sweep targets.
        :type cluster_registry_repository: ClusterRegistryMotorRepository
        :param configmaps_repository: current-version store.
        :type configmaps_repository: ConfigMapsMotorRepository
        :param configmaps_historical_repository: superseded-version store.
        :type configmaps_historical_repository: ConfigMapsHistoricalMotorRepository
        :param sweeps_repository: run-outcome store.
        :type sweeps_repository: SweepsMotorRepository
        :param http_client: shared HTTP client wrapper (lifecycle owned by run_sweep).
        :type http_client: HTTPXClient
        :param auth_service: cluster authentication service.
        :type auth_service: OSEAuthService
        :param cluster_client: read-only cluster API adapter.
        :type cluster_client: OpenShiftClusterClient
        :param redactor: write-time secret redaction.
        :type redactor: Redactor
        :param settings: collector settings.
        :type settings: OSEAlmanacSettings
        :return: None.
        :rtype: None
        """

        self._cluster_registry_repository = cluster_registry_repository
        self._configmaps_repository = configmaps_repository
        self._configmaps_historical_repository = configmaps_historical_repository
        self._sweeps_repository = sweeps_repository
        self._http_client = http_client
        self._auth_service = auth_service
        self._cluster_client = cluster_client
        self._redactor = redactor
        self._settings = settings

    # endDef

    @classmethod
    async def get_service(
            cls,
            mongo_client: AsyncIOMotorClient,
    ) -> Self:

        """
        Wires the collector service and every collaborator from one Mongo client and the
        environment-driven settings.

        :param mongo_client: shared MongoDB client.
        :type mongo_client: AsyncIOMotorClient
        :return: a ready collector service.
        :rtype: Self
        """

        settings = OSEAlmanacSettings()

        http_client = HTTPXClient(
            ca_certificate_path=settings.ca_certificate_path,
            verify_ssl=settings.verify_ssl,
            concurrency_limit=settings.request_concurrency_limit,
            timeout_seconds=settings.request_timeout_seconds,
        )
        auth_service = OSEAuthService(http_client=http_client, settings=settings)
        cluster_client = OpenShiftClusterClient(
            http_client=http_client,
            auth_service=auth_service,
            settings=settings,
        )

        return cls(
            cluster_registry_repository=ClusterRegistryMotorRepository(mongo_client),
            configmaps_repository=ConfigMapsMotorRepository(mongo_client),
            configmaps_historical_repository=ConfigMapsHistoricalMotorRepository(mongo_client),
            sweeps_repository=SweepsMotorRepository(mongo_client),
            http_client=http_client,
            auth_service=auth_service,
            cluster_client=cluster_client,
            redactor=Redactor(settings.redaction_rules_path),
            settings=settings,
        )

    # endAsyncDef

    async def run_sweep(
            self,
            batch_environment: str,
            batch_sector: str,
    ) -> SweepModel:

        """
        Runs one full sweep for an environment + sector and records its outcome.

        :param batch_environment: environment to sweep, e.g. development.
        :type batch_environment: str
        :param batch_sector: sector to sweep, e.g. pbwm_cgw.
        :type batch_sector: str
        :return: the recorded sweep document.
        :rtype: SweepModel
        """

        started_at = datetime.now(timezone.utc)
        counters = _SweepCounters()
        namespace_results: list[NamespaceSweepResult] = []
        errors: list[str] = []
        clusters_attempted: list[str] = []

        registry = await self._cluster_registry_repository.find_active_by_environment_sector(
            environment=batch_environment,
            sector=batch_sector,
        )

        if registry is None:
            errors.append(f"No active cluster_registry document for {batch_environment}/{batch_sector}")
            logger.error(errors[-1])

        else:
            clusters_attempted = list(registry.clusters)
            username, password = self._auth_service.resolve_credentials(registry.fid_details)

            async with self._http_client:
                # The cluster cap is an operational promise to the platform team, not a knob.
                cluster_semaphore = asyncio.Semaphore(self._settings.cluster_concurrency_limit)

                cluster_results = await asyncio.gather(
                    *(
                        self._sweep_cluster(
                            registry, cluster_name, username, password, cluster_semaphore, counters
                        )
                        for cluster_name in registry.clusters
                    ),
                    return_exceptions=True,
                )

            # endAsyncWith

            for cluster_name, result in zip(registry.clusters, cluster_results):
                if isinstance(result, BaseException):
                    errors.append(f"cluster {cluster_name}: {result}")
                    logger.error("cluster_sweep_failed cluster=%s error=%s", cluster_name, result)

                else:
                    namespace_results.extend(result)

                # endIfElse

            # endFor

        # endIfElse

        outcome = self._classify_outcome(namespace_results, errors)

        sweep = SweepModel(
            environment=batch_environment,
            sector=batch_sector,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            outcome=outcome,
            clusters_attempted=clusters_attempted,
            namespace_results=namespace_results,
            configmaps_new=counters.new,
            configmaps_changed=counters.changed,
            configmaps_unchanged=counters.unchanged,
            errors=errors,
        )

        await self._sweeps_repository.create(sweep)

        logger.info(
            "sweep_recorded environment=%s sector=%s outcome=%s new=%d changed=%d unchanged=%d",
            batch_environment,
            batch_sector,
            outcome.value,
            counters.new,
            counters.changed,
            counters.unchanged,
        )
        return sweep

    # endAsyncDef

    @staticmethod
    def _classify_outcome(
            namespace_results: list[NamespaceSweepResult],
            errors: list[str],
    ) -> SweepOutcome:

        """
        Classifies the run: success only when every namespace succeeded and nothing errored.

        :param namespace_results: per-namespace outcomes.
        :type namespace_results: list[NamespaceSweepResult]
        :param errors: run-level errors.
        :type errors: list[str]
        :return: the overall outcome.
        :rtype: SweepOutcome
        """

        if not namespace_results:
            return SweepOutcome.FAILED

        # endIf

        failed = [result for result in namespace_results if not result.success]

        if not failed and not errors:
            return SweepOutcome.SUCCESS

        # endIf

        return SweepOutcome.PARTIAL if len(failed) < len(namespace_results) else SweepOutcome.FAILED

    # endDef

    async def _sweep_cluster(
            self,
            registry: ClusterRegistryModel,
            cluster_name: str,
            username: str,
            password: str,
            cluster_semaphore: asyncio.Semaphore,
            counters: _SweepCounters,
    ) -> list[NamespaceSweepResult]:

        """
        Sweeps every in-scope namespace on one cluster. A namespace failure is recorded, never
        raised - one bad namespace must not cost the rest of the cluster, and deletion logic
        may only ever trust namespaces recorded as successful.

        :param registry: registry document for this group.
        :type registry: ClusterRegistryModel
        :param cluster_name: cluster to sweep.
        :type cluster_name: str
        :param username: FID username.
        :type username: str
        :param password: FID password.
        :type password: str
        :param cluster_semaphore: bounds concurrent cluster sweeps.
        :type cluster_semaphore: asyncio.Semaphore
        :param counters: shared run counters.
        :type counters: _SweepCounters
        :return: per-namespace outcomes for this cluster.
        :rtype: list[NamespaceSweepResult]
        """

        async with cluster_semaphore:
            namespaces = await self._cluster_client.list_namespaces(
                registry, cluster_name, username, password
            )
            results: list[NamespaceSweepResult] = []

            for namespace in namespaces:
                try:
                    seen = await self._sweep_namespace(
                        registry, cluster_name, namespace, username, password, counters
                    )
                    results.append(
                        NamespaceSweepResult(
                            cluster_name=cluster_name,
                            namespace=namespace,
                            success=True,
                            configmaps_seen=seen,
                        )
                    )

                except Exception as generic_exception:
                    logger.error(
                        "namespace_sweep_failed cluster=%s namespace=%s error=%s",
                        cluster_name,
                        namespace,
                        generic_exception,
                    )
                    results.append(
                        NamespaceSweepResult(
                            cluster_name=cluster_name,
                            namespace=namespace,
                            success=False,
                            error=str(generic_exception)[:500],
                        )
                    )

                # endTryExcept

            # endFor

            return results

        # endAsyncWith

    # endAsyncDef

    async def _sweep_namespace(
            self,
            registry: ClusterRegistryModel,
            cluster_name: str,
            namespace: str,
            username: str,
            password: str,
            counters: _SweepCounters,
    ) -> int:

        """
        Sweeps one namespace: list, redact, fingerprint, dedup write.

        :param registry: registry document for this group.
        :type registry: ClusterRegistryModel
        :param cluster_name: cluster being swept.
        :type cluster_name: str
        :param namespace: namespace to sweep.
        :type namespace: str
        :param username: FID username.
        :type username: str
        :param password: FID password.
        :type password: str
        :param counters: shared run counters.
        :type counters: _SweepCounters
        :return: the number of ConfigMaps observed.
        :rtype: int
        """

        raw_configmaps = await self._cluster_client.list_configmaps(
            registry, cluster_name, namespace, username, password
        )

        for raw in raw_configmaps:
            await self._store_configmap(registry, cluster_name, namespace, raw, counters)

        # endFor

        return len(raw_configmaps)

    # endAsyncDef

    async def _store_configmap(
            self,
            registry: ClusterRegistryModel,
            cluster_name: str,
            namespace: str,
            raw: dict[str, Any],
            counters: _SweepCounters,
    ) -> None:

        """
        Stores one ConfigMap with hash-based deduplication. Matching hash bumps last_seen;
        differing hash appends the old current record to historical FIRST, then replaces
        current - so storage grows with change, not with time, and a crash between the two
        writes loses nothing.

        :param registry: registry document for placement dimensions.
        :type registry: ClusterRegistryModel
        :param cluster_name: cluster the ConfigMap came from.
        :type cluster_name: str
        :param namespace: namespace the ConfigMap lives in.
        :type namespace: str
        :param raw: the raw ConfigMap object from the API.
        :type raw: dict[str, Any]
        :param counters: shared run counters.
        :type counters: _SweepCounters
        :return: None.
        :rtype: None
        """

        record = self._build_record(registry, cluster_name, namespace, raw)
        current = await self._configmaps_repository.find_by_identity(cluster_name, namespace, record.name)

        if current is None:
            await self._configmaps_repository.create(record)
            counters.new += 1

        elif current.content_hash == record.content_hash:
            await self._configmaps_repository.mark_seen(
                cluster_name, namespace, record.name, record.last_seen
            )
            counters.unchanged += 1

        else:
            # Historical first - the one write order that cannot lose data.
            await self._configmaps_historical_repository.create(current)
            await self._configmaps_repository.replace_current(record)
            counters.changed += 1

        # endIfElifElse

    # endAsyncDef

    def _build_record(
            self,
            registry: ClusterRegistryModel,
            cluster_name: str,
            namespace: str,
            raw: dict[str, Any],
    ) -> ConfigMapRecordModel:

        """
        Builds the stored record for one raw ConfigMap: redact every value, then fingerprint
        the redacted contents. Redaction happens before hashing so stored hashes always match
        stored values.

        :param registry: registry document for placement dimensions.
        :type registry: ClusterRegistryModel
        :param cluster_name: cluster the ConfigMap came from.
        :type cluster_name: str
        :param namespace: namespace the ConfigMap lives in.
        :type namespace: str
        :param raw: the raw ConfigMap object from the API.
        :type raw: dict[str, Any]
        :return: the record ready to persist.
        :rtype: ConfigMapRecordModel
        """

        metadata = raw.get("metadata") or {}
        data: dict[str, str] = raw.get("data") or {}
        binary_data: dict[str, str] = raw.get("binaryData") or {}

        redacted_data: dict[str, str] = {}
        redactions: list[RedactionRecord] = []

        for key, value in data.items():
            redacted_value, records = self._redactor.redact_value(key, value)
            redacted_data[key] = redacted_value
            redactions.extend(records)

        # endFor

        content_hash, key_hashes = fingerprint(redacted_data, binary_data)
        now = datetime.now(timezone.utc)

        creation_timestamp = metadata.get("creationTimestamp")

        return ConfigMapRecordModel(
            cluster_name=cluster_name,
            namespace=namespace,
            name=metadata.get("name", ""),
            content_hash=content_hash,
            environment=registry.dimensions.environment,
            sector=registry.dimensions.sector,
            data=redacted_data,
            binary_data_keys=sorted(binary_data.keys()),
            key_hashes=key_hashes,
            redactions=redactions,
            labels=metadata.get("labels") or {},
            annotations=metadata.get("annotations") or {},
            managed_fields=metadata.get("managedFields") or [],
            resource_version=metadata.get("resourceVersion"),
            creation_timestamp=creation_timestamp,
            first_seen=now,
            last_seen=now,
        )

    # endDef

# endClass


# end_sweep.py
