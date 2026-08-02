# ose_almanac

The OpenShift ConfigMap Intelligence Platform: a two-part system that collects every
ConfigMap across the OpenShift estate into MongoDB, then derives operational and
configuration-assurance intelligence from the stored data.

ConfigMaps in this estate are control-plane configuration - authorization policy, data
masking rules, resilience parameters, TLS flags, Vault paths - edited outside CI/CD with
no record of what changed or when. This platform keeps the record.

- **Part 1 - Collector** (this repo, built): a daily sweep that stores every ConfigMap,
  deduplicated by content hash, with credentials irreversibly redacted before storage.
- **Part 2 - Analytics** (next phase): independent extractors that read the stored data
  and answer "what changed", "why is prod different from UAT", and "who depends on what".

The platform is read-only towards the clusters, always, and is not a secrets manager.

## Quick start

```bash
pip install -e ".[dev]"
python ose_almanac_collector_main.py <environment> <sector>
```

See [docs/RUNBOOK.md](docs/RUNBOOK.md) for prerequisites, environment variables, and the
cluster registry setup - the collector needs both before its first run.

## Documentation

| Document | What it covers |
|---|---|
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | How to launch: install, configure, seed, run, verify, troubleshoot. |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the platform is put together and why. |
| [docs/STORAGE.md](docs/STORAGE.md) | How ConfigMaps are stored and what every field means. |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Every setting, its default, and the redaction rules file. |

# end_README.md
