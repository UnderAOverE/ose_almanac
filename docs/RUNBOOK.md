# Runbook - launching the collector

This is the step-by-step guide to run the OpenShift ConfigMap Intelligence Platform collector.
The collector connects to the OpenShift clusters listed in the cluster registry, downloads
every ConfigMap in scope, removes any hardcoded credentials, and stores the results in
MongoDB. It is designed to run once every 24 hours per environment and sector.

---

## 1. Prerequisites

- Python 3.12 or newer.
- Network access to the target cluster API servers.
- A MongoDB instance you can reach (the collector creates the `ose_almanac` database on
  first write).
- The master key used to encrypt the FID password (see step 4).

Install the project and its dependencies from the repo root:

```bash
pip install -e ".[dev]"
```

Quick sanity check that everything imports:

```bash
python -c "import src.batch.services.ose_almanac.collector.sweep; print('ok')"
```

---

## 2. Set the environment variables

The collector reads all of its settings from environment variables. Only the first two are
required; the rest have sensible defaults (full list in CONFIGURATION.md).

| Variable                 | Required | What it is                                             |
|--------------------------|----------|--------------------------------------------------------|
| `MONGO_URI`              | yes      | MongoDB connection string.                             |
| `OSE_ALMANAC_MASTER_KEY` | yes      | Master key that decrypts the FID password.             |
| `OSE_ALMANAC_CA_CERTIFICATE_PATH` | recommended | CA bundle used to trust the cluster API servers. |
| `OSE_ALMANAC_VERIFY_SSL` | no       | Set to `false` ONLY for a dev shakedown.               |
| `LOG_LEVEL`              | no       | `INFO` by default; `DEBUG` for troubleshooting.        |

PowerShell:

```powershell
$env:MONGO_URI = "mongodb://localhost:27017"
$env:OSE_ALMANAC_MASTER_KEY = "<master key>"
$env:OSE_ALMANAC_CA_CERTIFICATE_PATH = "C:\certs\ca-bundle.pem"
```

bash:

```bash
export MONGO_URI="mongodb://localhost:27017"
export OSE_ALMANAC_MASTER_KEY="<master key>"
export OSE_ALMANAC_CA_CERTIFICATE_PATH="/etc/pki/ca-bundle.pem"
```

---

## 3. Seed the cluster registry

The collector only sweeps what the `cluster_registry` collection tells it to. Insert one
document per sector + environment pair into `ose_almanac.cluster_registry`:

```javascript
// mongosh example - replace the placeholder values with real ones.
use ose_almanac

db.cluster_registry.insertOne({
    "_comment": "PBWM_CGW development clusters",
    "active": true,
    "dimensions": { "sector": "pbwm_cgw", "environment": "development" },
    "clusters": ["<cluster-name-1>", "<cluster-name-2>"],
    "fid_details": {
        "name": "<fid-username>",
        "geheimer_schlussel": "eAMP::<encrypted password - see step 4>"
    },
    "namespace_prefixes": ["gcb-", "gcg-", "icg-", "cto-", "cops-"],
    "domain": "<dns-domain>",
    "api_port": 6443
})
```

Field meanings:

- `active` - set to `false` to take a group out of the sweep without deleting it.
- `dimensions` - must match the two arguments you pass on the command line.
- `clusters` - the API URL for each cluster is built as
  `https://api.<cluster>.<domain>:<api_port>`.
- `namespace_prefixes` - only namespaces starting with one of these are swept.
- `geheimer_schlussel` - the FID password, encrypted. Never store it in plain text.

---

## 4. Encrypt the FID password

The password in the registry document must be encrypted with the same master key the
collector will use at runtime. To produce the encrypted value:

```bash
python -c "from src.common.security.secure_data_transformer import CryptoTransformer; print(CryptoTransformer('<master key>').encrypt('<fid password>'))"
```

Copy the printed `eAMP::...` value into the registry document.

Note: an encrypted value can only be decrypted by the same implementation of the
transformer that produced it, using the same master key. If the enterprise transformer
module replaces the local one, re-encrypt the password with the enterprise version.

---

## 5. Launch

From the repo root:

```bash
python ose_almanac_collector_main.py <environment> <sector>
```

Example:

```bash
python ose_almanac_collector_main.py development pbwm_cgw
```

Passing the wrong number of arguments prints a usage message and exits.

What a healthy run looks like in the log:

```
... | INFO | batch | mongo_client_ready
... | INFO | batch | redactor_ready rules=5 placeholder_patterns=4
... | INFO | batch | openshift_login_ok cluster=<name> user=<fid>
... | INFO | batch | namespaces_in_scope cluster=<name> count=42
... | INFO | batch | sweep_recorded environment=development sector=pbwm_cgw outcome=success new=310 changed=0 unchanged=0
```

---

## 6. Verify the results

Check the run record first - it says how complete the sweep was:

```javascript
use ose_almanac
db.sweeps.find().sort({ started_at: -1 }).limit(1)
```

- `outcome: "success"` - every namespace listed cleanly.
- `outcome: "partial"` - some namespaces failed; see `namespace_results` for which and why.
- `outcome: "failed"` - nothing was swept; see `errors`.

Then look at the data itself:

```javascript
db.configmaps.countDocuments({})
db.configmaps.findOne({ namespace: "<some-namespace>" })
```

---

## 7. Scheduling

The collector is a batch job, not a service. Schedule this command to run once every
24 hours per environment + sector, with the environment variables from step 2 present in
the job's environment:

```bash
python ose_almanac_collector_main.py <environment> <sector>
```

Running it more often is safe (unchanged ConfigMaps only bump a counter), but the
platform team should agree to the sweep frequency first - an estate-wide sweep is a
noticeable amount of API traffic.

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `OSE_ALMANAC_MASTER_KEY is not set` | Env var missing in the job environment. | Set it (step 2). |
| `No active cluster_registry document for <env>/<sector>` | No registry document matches the arguments, or `active` is false. | Check step 3; check spelling of environment and sector. |
| `Decryption failed - wrong master pre_data or corrupted value` | Password encrypted with a different key or a different transformer implementation. | Re-encrypt with the current key (step 4). |
| `OAuth server rejected credentials (401)` | Wrong FID password, or the FID is locked or expired. | Verify the FID; re-encrypt the correct password. |
| TLS certificate errors | The cluster API uses an internal CA the collector does not trust. | Set `OSE_ALMANAC_CA_CERTIFICATE_PATH` to the right CA bundle. |
| Mongo server selection timeout | `MONGO_URI` wrong or Mongo unreachable. | Check the URI and network. |
| `outcome: partial` with 403 errors on some namespaces | The FID lacks list permission there. | Request read (list) access; failed namespaces are recorded honestly and never treated as deletions. |

# end_RUNBOOK.md
