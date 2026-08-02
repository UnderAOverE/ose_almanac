# Architecture - how the platform is put together

## What this is, in plain English

ConfigMaps on our OpenShift clusters do not just hold harmless application settings. They
hold security policy: who is allowed to call which API, how card numbers are masked in
logs, whether TLS verification is on, where secrets live in Vault. These files get edited
by hand, outside the release pipeline, and today nobody records what changed or when.

The OpenShift ConfigMap Intelligence Platform fixes that. Every day it takes a complete,
credential-free copy of every ConfigMap in scope and stores it in MongoDB. Once the data
is in one place, questions that used to be unanswerable become simple queries: what
changed in this app's config last week? Why is production different from UAT? Which
services depend on which backends?

## The one big design rule: two parts, one seam

The system is split into two halves that only meet at the database:

1. **The collector** (built) - deliberately unintelligent. It downloads, redacts
   credentials, hashes, and stores. It does not parse or interpret anything.
2. **Analytics** (next phase) - all the intelligence. It reads the stored data, never the
   live clusters, and writes its conclusions to separate collections.

Why the split matters: when a parser improves or a new use case appears, we re-run
analytics against data we already have. We never have to re-sweep the estate, and a bug in
analytics can never disturb collection.

Two promises the platform makes and never breaks:

- **Read-only, always.** It never writes to a cluster. It is not a remediation tool.
- **Not a secrets manager.** Credentials are removed before anything is stored, and the
  removal cannot be undone.

## Folder map

```
ose_almanac/
├── ose_almanac_collector_main.py   entry point - the command the scheduler runs
├── conf/
│   └── redaction.yaml              secret-scanner rules (tunable without a code change)
├── docs/                           you are here
├── src/
│   ├── common/                     shared infrastructure layer
│   │   ├── db/                     MongoDB client + base repository classes
│   │   ├── httpx/                  HTTP client wrapper (TLS, timeouts, concurrency cap)
│   │   ├── security/               CryptoTransformer (encrypt/decrypt with a master key)
│   │   ├── logger.py               shared logger, UTC timestamps
│   │   └── constants.py
│   └── batch/
│       ├── constants.py            database + collection names, version stamps
│       ├── config/basesettings/    settings models, read from environment variables
│       ├── models/ose_almanac/     the shape of every stored document
│       ├── repositories/ose_almanac/  one class per collection - all Mongo access
│       └── services/ose_almanac/
│           ├── collector/          auth, cluster client, redaction, hashing, sweep
│           └── analytics/          parser and extractors (next phase)
└── tests/
```

## How the layers talk to each other

Requests flow one way, top to bottom:

```
entry point  ->  sweep service  ->  cluster client / redactor / hashing
                     |                     |
                repositories          auth service
                     |                     |
              common db layer       common httpx layer
```

Rules that keep the design clean:

- Only `src/common/db` touches the MongoDB driver. Everyone else goes through a
  repository class.
- Only `src/common/httpx` touches the HTTP library. Everyone else goes through the
  cluster client.
- Business logic never reads environment variables; the settings layer does that. The
  one exception is the master key, read at the single place it is used.
- Every collaborator is passed in through the constructor, so each piece can be tested
  on its own without a live cluster or database.

## The common layer is a placeholder

`src/common/` mirrors the interface of the enterprise common layer (base repositories,
HTTP client wrapper, crypto transformer, logger). At deployment the enterprise modules
replace these files verbatim, and nothing else in the project has to change, because
every caller depends only on the interface. Do not add project-specific logic there.

## Analytics - what comes next

The analytics half will read the stored ConfigMaps and derive intelligence, one
independent extractor per topic (endpoints, certificates, keystores, resilience settings,
authorization rules, masking rules). All of them consume a shared parser that flattens
raw YAML / properties / JSON values into individual keys, so a change report can say
"this timeout went from 1s to 5s" instead of "line 214 changed". Extractors know nothing
about each other; adding one touches nothing that already exists.

# end_ARCHITECTURE.md
