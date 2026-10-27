# Zetaris: optional data-query integration research

Research date: 23 October 2026 (Australia/Sydney).

## Scope and independent design suggestions

Zetaris is an optional query-backend candidate, not a selected architecture or a required dependency. DuckDB, Vercel AI SDK and Meterless are also optional. This report preserves independently inspected product documentation and source behavior, followed by clearly labeled integration suggestions. No rule set, numeric detection threshold, worked investigation or evaluation split is prescribed.

If Zetaris is selected, a small application adapter could expose bounded queries to an agent. Keeping query execution, evidence persistence and verification independent of model orchestration would make other query backends and frameworks easier to compare. This is an engineering suggestion, not a requirement of any reviewed product.

The important discovery is a **current official, public getting-started repository** with concrete REST/JDBC clients and dated compatibility notes: [Zetaris getting-started](https://zetaris.github.io/getting-started/). The older knowledge-base REST article describes a different API generation; combining its request shape with the current client's endpoints would be a mistake.

Repository inspected at commit [`6a2fbaa47c32c9ac33f6584c64b43b146c621bed`](https://github.com/zetaris/getting-started/tree/6a2fbaa47c32c9ac33f6584c64b43b146c621bed), commit timestamp `2026-10-22T20:45:07Z`. References to upstream tests below mean tests reported by that repository, **not tests performed by this research**. No Zetaris instance was accessed, no accounts were created, no data was uploaded, and no software was installed.

## What Zetaris supplies

| Capability | Evidence and practical meaning |
|---|---|
| Data access | Virtualization-first registration of metadata for files, databases, streaming sources and REST sources. CSV and Parquet can be registered from supported storage. Registration is not automatically a copy into a new warehouse. [Data-source overview](https://kbase.zetaris.com/knowledge/connect) |
| Query interfaces | SQL Editor plus external JDBC, ODBC and REST access. A TypeScript backend can use HTTP; Java/JDBC is not mandatory. [Connection overview](https://kbase.zetaris.com/knowledge/overview-of-connecting-to-zetaris) |
| SQL | Joins, WHERE, GROUP BY, HAVING, window functions, ordinary CTEs, views and LIMIT are documented. These provide general primitives for structured transaction analysis. The documentation is not proof that every connector and SQL form performs correctly. [SQL manual](https://kbase.zetaris.com/knowledge/sql-manual) |
| Catalog | Table/column metadata, annotations, metadata-change history and statistics. Useful for describing authoritative columns to the agent, not a substitute for AML rules. [Catalog overview](https://kbase.zetaris.com/knowledge/data-catalog-overview) |
| Access control | Object-level SELECT/INSERT grants and row/column policies. Creation permissions and permission to read data are distinct. The runtime agent should receive read access to prepared views, not administrative credentials. [Permissions](https://zetaris.github.io/getting-started/docs/guides/permissions.html) |
| Performance mechanisms | Spark-based distributed processing, caching, optimizer statistics and source-dependent pushdown. Benefit depends on source and execution plan. [Deployment fundamentals](https://kbase.zetaris.com/knowledge/zetaris-fundamentals), [tuning](https://kbase.zetaris.com/knowledge/deployment-tuning-and-optimization) |

Zetaris also markets a Cloud query director and AgentFlow, and its GenZ documentation describes MCP tooling. These are additional product capabilities, not evidence that a prospective deployment exposes a usable external MCP server. The public onboarding route now provides ordinary client scripts independently of that functionality. [Cloud](https://www.zetaris.com/cloud), [GenZ tools](https://kbase.zetaris.com/knowledge/genz-tools)

Independent assessment: federation may be useful when several data systems must be queried together. A single static CSV provides a weaker reason to introduce a distributed integration platform.

## Concrete interfaces verified in source

### Current direct REST client

The official `RestChannel` sends this request relative to an API base ending in `/api/v1.0`:

```http
POST /api/v1.0/sql-editor/sqls/run
Authorization: Bearer <user-created API key>
X-Org-ID: <numeric organization id>
X-Request-ID: <fresh UUID>
Content-Type: application/json

{
  "queryId": "<fresh UUID>",
  "sql": "SELECT 1",
  "source": "SqlEditor",
  "limit": 100
}
```

Its parser reads a `data` property. The helper sets a 600-second HTTP timeout; that is a client timeout, not a documented query-cancellation guarantee. Source: [`zetaris_sql.py`](https://github.com/zetaris/getting-started/blob/6a2fbaa47c32c9ac33f6584c64b43b146c621bed/scripts/zetaris_sql.py#L182).

The current setup guide distinguishes API keys from the Basic authentication used to fetch `/redoc/docs.yaml`. API keys inherit the user's privileges. It also notes that REST values arrive as strings and decimals can use exponent notation. A production adapter must normalize results and confirm the deployed API schema. [Client setup](https://zetaris.github.io/getting-started/docs/connections/client-setup.html)

### Separate UI-proxy helper

The smaller Python/Deno helper instead posts to the **UI origin**:

```http
POST /api/proxy/sql-editor/sqls/run-query

{"sql":"SELECT 1","limit":1000}
```

It optionally adds `engineId`. It is not the direct REST endpoint above. Source: [`query_zetaris.py`](https://github.com/zetaris/getting-started/blob/6a2fbaa47c32c9ac33f6584c64b43b146c621bed/scripts/query_zetaris.py#L32).

The shared UI client sends bearer authentication, organization ID and a new request UUID, with a 30-second HTTP timeout. It supports API-key authentication or a login fallback. An integration should use a dedicated configured identity and keep its credentials out of model context. Source: [`zetaris_api.py`](https://github.com/zetaris/getting-started/blob/6a2fbaa47c32c9ac33f6584c64b43b146c621bed/scripts/zetaris_api.py#L31).

### JDBC and Python

The documented driver class is `com.zetaris.lightning.jdbc.LightningDriver`; the URL form is `jdbc:zetaris:lightning@<host>:<port>`, with port 10000 in the standard example. A matching driver JAR and Java runtime are required. [JDBC setup](https://kbase.zetaris.com/knowledge/setup-jdbc-driver), [sharing example with driver class](https://kbase.zetaris.com/knowledge/global-data-sharing-technical-design-and-implementation)

The repository includes a Python/JayDeBeApi channel. **Its current implementation calls `fetchall()` before slicing to its requested display limit.** That limit does not prevent fetching an enormous result. SQL must bound the query itself; production code should stream/fetch in bounded batches if the interface permits. [Pinned client source](https://github.com/zetaris/getting-started/blob/6a2fbaa47c32c9ac33f6584c64b43b146c621bed/scripts/zetaris_sql.py#L277)

The public scripts are executable examples, not evidence of a published official `pip install zetaris` query SDK. The separate `ndpmetadata` library documented in the knowledge base is for bulk catalog annotation, not this transaction-query application. [Metadata library scope](https://kbase.zetaris.com/knowledge/update-metadata-tags-description-using-python-and-excel)

### Legacy API: do not mix contracts

An older official article uses `OpenSqlQuery`, JSON fields `select` and `pageLimit`, a `queryToken` for paging, and a close operation. It documents page sizes 1–100. The linked Postman repository returned 404 during this research. Treat it as an alternative/legacy contract pending verification of a selected deployment, not as the specification for the newer `/sql-editor/sqls/run` route. [Legacy REST article](https://kbase.zetaris.com/knowledge/rest-api)

No ready-to-use Zetaris connector was available in this research environment. Context7 returned no matching Zetaris library; official web documentation and pinned public source were used instead.

## Conditional setup path if Zetaris is selected

1. **Confirm whether a deployment is available.** If Zetaris is selected, obtain its version, API base, UI origin, organization ID and a dedicated read identity. An existing deployment would avoid a separate local installation.
2. **If nothing is provisioned, choose deployment explicitly.** The official local path requires a platform archive, matching configuration, registry access and an appropriate entitlement. It uses Docker Compose, recommends 8 GB allocated to Docker/4 CPUs/15 GB free disk, and uses amd64 images (Apple Silicon requires emulation). The public recipe repository does not contain the platform images. [Local installation](https://zetaris.github.io/getting-started/docs/install/updated_zetaris_installation_guide.html)
3. **Do not equate a free software tier with free infrastructure.** The Cloud release describes deployment into the user's AWS account with AWS charges separate from the Zetaris subscription. [Cloud release](https://kbase.zetaris.com/knowledge/zetaris-cloud-release-note-v.1.0.0)
4. **Verify read access independently of AML data:** `SELECT 1`, `SHOW LIGHTNING DATABASES`, then a bounded sample of an assigned table. The upstream preflight is useful, but its JDBC socket probe currently hardcodes localhost:10000, so a remote deployment needs an adjusted readiness check. [Preflight source](https://github.com/zetaris/getting-started/blob/6a2fbaa47c32c9ac33f6584c64b43b146c621bed/scripts/preflight.py#L63)
5. **Prepare one typed transaction dataset and a separate evaluator-only labels dataset.** Preserve immutable source identifiers before any conversion or sorting.
6. **Make the transaction file reachable to Zetaris.** Either use supported object storage, or an approved platform upload/mount. A path on the developer's laptop is not automatically visible inside a remote engine. The older NDP workflow uploads a local file before registering it. [Local-file onboarding](https://kbase.zetaris.com/knowledge/how-to-ccnnect-to-json-from-local-machine)
7. **Register a Lightning database and filestore table using the deployment's supported recipe.** Verify a small sample, schema, count, date bounds and independently selected source rows before querying at scale. Public S3 registration uses `s3a://` paths and separate endpoint options; browser download URLs are not interchangeable with those paths. [File cookbook](https://zetaris.github.io/getting-started/open_data/parquet_csv/HOWTO.html)
8. **Create the agent's label-free view and permissions, then verify denied reads as that identity.** Setup is a separate administrative operation. Do not let a prompt's instruction to avoid labels be the only isolation mechanism.

This research prepared that path; it did not carry out these setup actions.

## Independent suggestion: normalized data contract

The independent [data investigation](ibm-data-and-evaluation.md) found account-number collisions across banks in the downloaded IBM files. This integration strand did not query those files through Zetaris. A possible normalized representation is:

| Field | Intended representation |
|---|---|
| `dataset_version`, `source_file_sha256` | Immutable dataset provenance |
| `source_row_number`, `transaction_id` | Stable original-row reference; document whether row numbering includes the header |
| `source_timestamp_text` | Exact original timestamp |
| `event_minute` | Integer minutes from a fixed simulation epoch, computed once without local-timezone conversion |
| `from_bank`, `from_account`, `to_bank`, `to_account` | Strings; retain leading zeros and original identifiers |
| `from_bank_canonical`, `to_bank_canonical` | Separate validated bank-ID join values; the audited IBM files require leading-zero normalization across transaction and account metadata |
| `amount_paid`, `amount_received` | Exact decimals with scale chosen from profiling, not floating point |
| `payment_currency`, `receiving_currency`, `payment_format` | Source values |

Account identity uses the composite pair `(canonical_bank, account)` for cross-file joins while retaining the raw source values for evidence. The full-file audit verified this normalization without metadata-key collisions and with complete active-account coverage. Repeat those checks for a different release. Avoid ambiguous concatenation and do not assume an account string is globally unique. A separate stable ID may encode the pair without losing either original value. [Data audit](ibm-data-and-evaluation.md)

The label and pattern-membership fields belong in an evaluator-only table, not the agent view. `source_row_number` should be preserved as provenance but not advertised as a predictive feature: row ordering could encode how synthetic examples were generated.

Preparing typed Parquet is my recommendation, not a requirement of Zetaris. It avoids repeated CSV type inference and creates an explicit cross-engine schema. Casting an already inferred integer bank ID back to a string cannot recover lost leading zeros. Read the original CSV with explicit string types before converting.

DuckDB documents both explicit CSV column types and disabling inference with `all_varchar`; its Parquet reader supports projection/filter pushdown and can skip row groups using statistics. [CSV options](https://duckdb.org/docs/stable/data/csv/overview), [Parquet reader](https://github.com/duckdb/duckdb-web/blob/main/docs/current/data/parquet/overview.md)

## SQL feasibility and performance

Aggregation, joins and temporal comparisons can support transaction-analysis experiments. Whether those primitives are sufficient depends on the chosen analysis; a native graph database is not intrinsically required for bounded relationship queries. The SQL manual documents `JOIN ... ON`, `OVER (PARTITION BY ... ORDER BY ...)`, `ROWS`/`RANGE`, and ordinary CTEs. **No selected deployment was available to verify recursive CTE support or temporal-interval behavior.** [SQL manual](https://kbase.zetaris.com/knowledge/sql-manual)

Spark's official documentation defines interval literals, but that alone does not prove acceptance by a particular Zetaris engine/version. [Spark literal reference](https://spark.apache.org/docs/latest/sql-ref-literals.html)

One optional cross-engine representation uses `event_minute` with integer bounds calculated in application code. It can avoid accidental timezone conversion and differences in timestamp arithmetic. This generic account-activity query is an independent, unexecuted illustration, not a detection rule:

```sql
SELECT transaction_id, source_timestamp_text,
       from_bank, from_account, to_bank, to_account,
       amount_paid, payment_currency
FROM analysis.transactions_agent
WHERE from_bank = <validated_bank>
  AND from_account = <validated_account>
  AND event_minute >= <start_minute>
  AND event_minute < <cutoff_minute>
ORDER BY event_minute, transaction_id
LIMIT <validated_row_limit>
```

This example retrieves outgoing transactions for a supplied bank/account pair within an explicitly bounded interval. It assigns no risk interpretation. Production compilation must render validated parameters using the backend's supported binding/escaping mechanism. The placeholders above are not runnable SQL parameter syntax.

Important workload decisions:

- A large account can produce `incoming_count × outgoing_count` candidate pairs before filtering. Avoid materializing every pair across a full dataset when only an account-level aggregate is needed.
- Apply the filters required by the selected analysis early; a bounded candidate-account set can reduce later evidence retrieval. Preserve complete population coverage when an evaluation requires it.
- Use a backend job to run full-period rules and persist results. The LLM should receive summaries and case references rather than thousands of API result pages.
- A tool response LIMIT bounds returned rows, not necessarily compute work. Distinguish complete results from a truncated sample; never count a silent sample as a complete investigation.
- For case expansion, query a bounded account frontier and use application code to verify directed paths, time order, cycles, parallel edges and visited state. This avoids depending on unverified recursive SQL.
- Repeated uncached CSV scans, skewed joins, Spark scheduling and network/object-storage access can dominate latency. A tiny `SELECT ... LIMIT 5` succeeding proves connectivity, not that a temporal self-join is affordable.

The upstream SQL companion reports specific connector failures and repeated-reference self-join failures for certain `UNION ALL`/`explode()` views. That does **not** establish a failure for a simple flat IBM table, but it justifies a fixture-based compatibility check before designing around such views. Its live-test scope is version 2.4.3.1, dated 12 October 2026. [Upstream compatibility notes](https://zetaris.github.io/getting-started/docs/guides/zetaris-lightning-sql-companion.html)

Caching may help repeated investigation queries, but it needs deployment-specific verification. Older documentation describes offsite memory/file cache and TTL; newer upstream notes distinguish session cache behavior and incomplete reporting of cache state. Do not assume all cache commands have the same semantics. [Cache documentation](https://kbase.zetaris.com/knowledge/caching)

## Independent suggestion: application integration contract

This optional contract illustrates one integration approach. It is not an existing Zetaris SDK API or a settled application design.

```text
QueryScope (server-owned):
  datasetVersion, allowedDateStart, cutoffExclusive, principalId

DataBackend:
  describeCoverage(scope)
  executeRule(ruleVersion, validatedParameters, scope) -> job/result reference
  listAccountTransactions(bank, account, direction, cursor, scope)
  getTransactions(transactionIds, scope)
  summarizeCounterparties(bank, account, direction, scope)

Every result:
  queryId, backend, datasetVersion, appliedScope,
  rows or resultRef, returnedCount, truncated, nextCursor,
  elapsedMs, warnings
```

The server binds the cutoff, dataset and principal; the agent cannot expand them by tool arguments. A bounded internal tool such as `listAccountTransactions` maps to a vetted SQL template. A separate trusted rule executor can accept a validated rule definition and compile it to SQL. A development agent may propose new definitions; it must not gain arbitrary database permissions merely because it is experimenting.

The AI SDK's documented tool structure has `inputSchema` and an `execute` function. If that SDK is selected, an ordinary server-side tool executor can call a backend adapter. No additional model call is necessary for query execution. [AI SDK tools/agents](https://github.com/vercel/ai/blob/main/content/docs/03-agents/01-overview.mdx)

```text
Agent tool call
  → validate business inputs
  → bind immutable evaluation scope
  → compile backend-specific SQL
  → call the selected query backend
  → normalize types and record query provenance
  → persist full evidence outside the prompt
  → return bounded evidence plus completeness metadata
```

If Zetaris and DuckDB adapters are compared, they should produce the same **behavior and records**, not necessarily identical SQL strings. Differences can include timestamp syntax, quoting, parameter support, response types, paging and execution-plan controls.

Independent suggestion: retain investigation state and evidence as explicit application records—accounts visited, outstanding questions, query IDs, source rows and graph edges. If Markovian is evaluated, its compact state can reference those records. This does not require selecting Markovian or any other framework; summaries should not become the only copy of evidence.

## Verification before trusting results

1. **Type integrity:** test leading-zero bank IDs, alphanumeric accounts, exact decimals, nulls and duplicated transaction content with different source rows.
2. **Boundary semantics:** test exactly-on-cutoff transactions, same-minute transfers, the chosen temporal boundaries and any permitted historical context.
3. **Fresh regression fixtures:** construct small, independently specified examples that cover directed links, parallel transactions and temporal ordering. Define expected records before executing the query; do not treat these fixtures as blind evaluation.
4. **Backend parity if comparing implementations:** run small synthetic fixtures and independently selected source-data slices through each adapter; compare IDs and normalized values, not display order.
5. **Coverage:** distinguish absent data, denied data, incomplete pages, failed queries and genuine zero matches.
6. **Isolation:** prove the runtime identity cannot read labels/pattern files, write source data, or bypass the cutoff through alternative tools.
7. **Performance:** measure cold/warm single-account queries, bounded frontier expansion and full-window rule jobs independently. Record row cardinalities, cache state, runtime and memory; benchmark the actual deployment rather than claiming generic distributed speed.

DuckDB's `EXPLAIN ANALYZE` exposes execution plans and timing for the local baseline. Use the corresponding deployment-supported Zetaris plan/metrics tooling rather than assuming that exact syntax is portable. [DuckDB profiling](https://github.com/duckdb/duckdb-web/blob/main/docs/current/guides/meta/explain_analyze.md)

## Questions to resolve if selecting Zetaris

1. Which platform release and query engine would be used? Does it match the inspected Lightning source or require another API contract?
2. Is an instance already provisioned? What are its direct REST base, UI origin, organization ID, and network requirements?
3. Which API contract is supported: current SQL-editor REST, UI proxy, legacy paginated API, JDBC, or external MCP? Please provide that instance's OpenAPI spec and a read-only sample.
4. Can we obtain a dedicated identity restricted to a label-free dataset/view? Are underlying tables/catalogs still discoverable through other routes?
5. Where should the IBM file live, and which upload/mount/S3 registration path is supported? Is typed Parquet preferred? What are file-size and source-access limits?
6. What are result limits, asynchronous-query facilities, paging, query cancellation, server timeouts and concurrency limits? Does client disconnect cancel computation?
7. Which SQL interval/decimal/window features are verified in this instance? Are prepared statement bindings supported for the chosen API? What query-plan inspection is available?
8. What cache/materialization operations are allowed, how are they refreshed, and what compute resources are allocated?
9. What entitlement would cover the intended deployment duration and evaluation use? Who would operate and pay for any cloud infrastructure?

These questions apply only if Zetaris is selected for a trial. Dataset preparation and independent analysis experiments can proceed with another backend; no product choice is implied by this report.
