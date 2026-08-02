# Storage - how ConfigMaps are stored and what is kept

## The three drawers

Everything lives in one MongoDB database named `ose_almanac`. Think of the three main
collections as drawers in a filing cabinet:

| Collection               | What it holds                                                    |
|--------------------------|------------------------------------------------------------------|
| `configmaps`             | The CURRENT photo of every ConfigMap in the estate.              |
| `configmaps_historical`  | Every OLDER photo that was replaced. Nothing is thrown away.     |
| `sweeps`                 | The logbook: one entry per collection run, with what succeeded.  |

Plus one operator-managed collection:

| Collection         | What it holds                                              |
|--------------------|------------------------------------------------------------|
| `cluster_registry` | The sweep targets: which clusters, which FID, which namespaces. |

Analytics collections (`cm_endpoints`, `cm_certificates`, `cm_changes`, and friends) are
reserved for the next phase.

## What happens to each ConfigMap during a sweep

Step by step, in order:

1. **Redact.** Every value is scanned for hardcoded credentials. A real password is
   replaced - permanently - with a marker like
   `[REDACTED:assigned_credential:10:a1b2c3d4e5f6]` that records which rule fired, where,
   and a hash of what was removed. References like `${zconnect.password}` or
   `{smg-secret}name` are left alone: they are pointers to a secret store, not secrets.
   Redaction happens BEFORE anything is written, so plaintext credentials never reach
   the database.

2. **Fingerprint.** Each key gets its own SHA-256 hash (so we can say WHICH key changed),
   and all the key hashes combine into one whole-ConfigMap hash (so we can say WHETHER
   anything changed at all).

3. **Deduplicate.** The identity of a ConfigMap is cluster + namespace + name. Three
   possible outcomes:

   - **Never seen before** - a new record is inserted.
   - **Seen before, same content** - no new record. We just update `last_seen` and add
     one to `seen_count`. This is why storage grows with CHANGE, not with time: an app
     that never changes costs one document forever.
   - **Seen before, different content** - the old record is copied into
     `configmaps_historical` FIRST, and only then is the current record replaced. The
     order is deliberate: if the process dies between the two writes, the worst case is a
     harmless duplicate in historical. The other order could silently lose a version.

4. **Record the run.** One `sweeps` document is written with per-namespace success or
   failure. A namespace that failed (for example, a permissions problem) is recorded as
   failed - and a ConfigMap missing from a FAILED namespace is never treated as deleted.
   One permissions hiccup must not look like a thousand deletions.

## What one stored ConfigMap record contains

| Field | What it is | Why we keep it |
|---|---|---|
| `cluster_name`, `namespace`, `name` | Where the ConfigMap lives. | Identity. |
| `content_hash` | One hash over everything. | "Did anything change?" in one comparison. |
| `environment`, `sector` | Which environment and business sector. | Kept as fields (not separate collections) so "compare prod against UAT" is a single query. |
| `data` | The full values of every key, already redacted. | Storing values (not just hashes) means new analytics ideas can run against data we already have - no re-sweep needed. |
| `key_hashes` | One hash per key. | Says exactly which key changed between two versions - what makes change reports readable. |
| `binary_data_keys` | Names of binary entries only. | The binary contents themselves are hashed but not stored. |
| `redactions` | Rule name, line, offset, and hash of each removed credential. | Proves a credential existed - and whether it changed - without keeping it. |
| `labels`, `annotations` | Kubernetes metadata. | Carries release stamps, ownership, tool markers. |
| `managed_fields` | Kubernetes's own record of who last wrote each field and when. | A daily sweep only sees the net result of a day. This recovers part of the story in between - for example an edit that was reverted the same day. |
| `resource_version`, `creation_timestamp` | Cluster-side version and creation time. | Correlation with cluster events. |
| `first_seen`, `last_seen`, `seen_count` | When this exact version appeared, when it was last confirmed, and across how many sweeps. | Stability history without storing duplicates. |
| `collector_version` | Which collector build wrote the record. | Says how good the DATA is. |
| `schema_version` | The shape version of the document. | Safe evolution of the format. |

## What is deliberately NOT stored

- **Plaintext credentials.** Removed before persistence. The removal is irreversible by
  design - this platform must never become the place where credentials can be found.
- **Binary data contents.** Only their names and hashes.

## The cluster registry document

One document per sector + environment pair tells the collector what to sweep:

```
{
  "active": true,
  "dimensions": { "sector": "<sector>", "environment": "<environment>" },
  "clusters": ["<cluster-name>", ...],
  "fid_details": { "name": "<fid>", "geheimer_schlussel": "eAMP::<encrypted>" },
  "namespace_prefixes": ["gcb-", "gcg-", "icg-", "cto-", "cops-"],
  "domain": "<dns-domain>",
  "api_port": 6443
}
```

- The API URL for each cluster is built as `https://api.<cluster>.<domain>:<api_port>`.
- Only namespaces starting with one of the `namespace_prefixes` are swept.
- `geheimer_schlussel` is the FID password, encrypted with the master key. It is
  decrypted in memory at the moment of login and never written anywhere.

## A note on who may read this data

The stored corpus is a map of the internal estate: Vault paths, role names, certificate
identifiers, service topology. Access to the `ose_almanac` database should be restricted
at least as tightly as access to the clusters themselves.

# end_STORAGE.md
