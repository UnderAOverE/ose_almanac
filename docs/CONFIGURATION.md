# Configuration - every setting and what it does

All settings are environment variables. Defaults are sensible; you only have to set the
first two. Precedence, lowest to highest: built-in defaults, then environment variables,
then command-line arguments.

## Required

| Variable | What it is |
|---|---|
| `MONGO_URI` | MongoDB connection string, e.g. `mongodb://host:27017`. |
| `OSE_ALMANAC_MASTER_KEY` | Master key that decrypts the FID password from the cluster registry. Read only at the moment of decryption; never logged, never stored. |

## TLS towards the clusters

| Variable | Default | What it does |
|---|---|---|
| `OSE_ALMANAC_CA_CERTIFICATE_PATH` | not set | Path to the CA bundle used to verify cluster API server certificates. Set this in every real environment. |
| `OSE_ALMANAC_VERIFY_SSL` | `true` | Set to `false` to skip certificate verification. Development shakedowns only - a warning is logged when it is off. |

## Sweep shape

| Variable | Default | What it does |
|---|---|---|
| `OSE_ALMANAC_CLUSTER_CONCURRENCY_LIMIT` | `3` | How many clusters are swept at the same time. |
| `OSE_ALMANAC_REQUEST_CONCURRENCY_LIMIT` | `20` | Maximum HTTP requests in flight at once, across everything. |
| `OSE_ALMANAC_PAGE_SIZE` | `500` | How many items each list call asks the cluster for. Every list call is paginated. |
| `OSE_ALMANAC_REQUEST_TIMEOUT_SECONDS` | `30.0` | Per-request timeout. |

The two concurrency limits are a promise to the platform team, not a performance knob.
An estate-wide sweep is a noticeable amount of API traffic; raise these only after
agreeing it with the people who run the clusters.

## Retries - cluster API calls

Every call to a cluster API server (namespace listing, ConfigMap pages) automatically
retries with exponential backoff and a hard stop. What triggers a retry: network errors,
server errors (5xx), and throttling (429). What never retries: permission errors (401 and
403) - instead the cached token is dropped so the next attempt logs in fresh.

| Variable | Default | What it does |
|---|---|---|
| `OSE_ALMANAC_RETRY_ATTEMPTS` | `3` | Maximum attempts per call. |
| `OSE_ALMANAC_RETRY_WAIT_MIN_SECONDS` | `2.0` | First backoff wait. |
| `OSE_ALMANAC_RETRY_WAIT_MAX_SECONDS` | `10.0` | Backoff ceiling. |

## Retries - login tokens

Getting a login token is the gate to everything on a cluster, so transient OAuth server
failures (throttling, server errors, network blips) are retried with exponential backoff.
Wrong credentials (401) are never retried - repeating a bad password only risks locking
the FID.

| Variable | Default | What it does |
|---|---|---|
| `OSE_ALMANAC_AUTH_RETRY_ATTEMPTS` | `3` | Maximum attempts to obtain a token per cluster. |
| `OSE_ALMANAC_AUTH_RETRY_WAIT_MIN_SECONDS` | `2.0` | First backoff wait between token attempts. |
| `OSE_ALMANAC_AUTH_RETRY_WAIT_MAX_SECONDS` | `30.0` | Backoff ceiling between token attempts. |
| `OSE_ALMANAC_TOKEN_SKEW_SECONDS` | `300` | Tokens are refreshed this many seconds before they would expire, so a long sweep never runs into an expiring token. |

## Redaction rules

| Variable | Default | What it does |
|---|---|---|
| `OSE_ALMANAC_REDACTION_RULES_PATH` | `conf/redaction.yaml` | Where the secret-scanner rules live. |

## Logging

| Variable | Default | What it does |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Standard levels; `DEBUG` for troubleshooting. Timestamps are always UTC. |

---

## The redaction rules file (conf/redaction.yaml)

The scanner that removes credentials before storage is driven entirely by this file, so a
rule can be tuned without touching code.

Three sections:

1. **`placeholder_patterns`** - patterns that identify indirection references. A value
   that FULLY matches one of these (for example `${zconnect.password}` or
   `{smg-secret}configserver_prod`) is a pointer to a secret store, not a stored secret.
   It is never redacted, because destroying it would destroy the analytics signal.

2. **`rules`** - high-confidence credential patterns, each with a name and a Python
   regular expression. Two behaviors:
   - A rule containing a `(?P<value>...)` group redacts only the captured secret and
     leaves the rest of the line intact.
   - A rule without one redacts the whole match (used for private key blocks).

   The replacement marker is `[REDACTED:<rule name>:<offset>:<hash prefix>]` - enough for
   analytics to know a credential existed and whether it changed, without keeping it.

3. **`minimum_secret_length`** - captured values shorter than this are treated as noise
   (default 4). Prevents `password: abc` style test values from flooding the results.

### Adding a rule

Add an entry under `rules`:

```yaml
  - name: my_new_rule
    pattern: '(?i)my[_-]?token\s*[:=]\s*(?P<value>\S+)'
```

Then re-run the collector. No code change, no redeploy of anything else. Keep rules
high-confidence: a false positive here permanently destroys a legitimate value in the
stored copy (the cluster itself is never touched).

# end_CONFIGURATION.md
