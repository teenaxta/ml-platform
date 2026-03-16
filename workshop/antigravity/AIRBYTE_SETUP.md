# Airbyte Setup Guide

This guide walks you through installing Airbyte and configuring it to ingest data from the demo PostgreSQL database into the Iceberg lakehouse (MinIO).

> **Why not a docker-compose file?** Airbyte deprecated Docker Compose after version 1.0 (August 2024). The official self-hosted method is `abctl`, which uses a local Kubernetes cluster under the hood. It is the only supported local deployment method.

---

## 1. Prerequisites

Before starting:

1. The `mlplatform` Docker network must exist. If you have already run `docker compose up -d` for the main platform, the network exists. If not, create it:
   ```bash
   docker network create mlplatform
   ```

2. The demo PostgreSQL database must be running:
   ```bash
   docker compose -f docker-compose.demo-postgres.yml up -d
   ```

3. The main platform must be running (at minimum: MinIO, Iceberg REST, Trino):
   ```bash
   docker compose up -d
   ```

---

## 2. Install abctl

`abctl` is Airbyte's CLI tool. Install it:

**macOS (Homebrew):**

```bash
brew tap airbytehq/tap
brew install abctl
```

**Linux / manual:**

```bash
curl -LsfS https://get.airbyte.com | bash -
```

Verify the installation:

```bash
abctl version
```

You should see a version number like `v0.XX.X`.

---

## 3. Start Airbyte

Run Airbyte locally:

```bash
abctl local install
```

This will:
- Create a local Kubernetes cluster using `kind`
- Deploy all Airbyte services (server, worker, webapp, database, temporal)
- Take 3–10 minutes on first run

When the installation finishes, Airbyte will be available at:

- **Airbyte UI**: `http://localhost:8000`
- **Default credentials**: username `airbyte`, password `password`

### Low-resource mode

If your machine has fewer than 4 CPUs or less than 8 GB RAM:

```bash
abctl local install --low-resource-mode
```

### Verify Airbyte is running

1. Open `http://localhost:8000` in your browser.
2. Log in with username `airbyte` and password `password`.
3. You should see the Airbyte dashboard with a "Set up your first connection" prompt.

---

## 4. Configure the PostgreSQL Source

### Steps

1. In the Airbyte UI, click **"Sources"** in the left sidebar.

2. Click **"+ New source"**.

3. Search for **"Postgres"** and select it.

4. Fill in the connection details:

   | Field | Value |
   |---|---|
   | Source name | `demo-postgres` |
   | Host | `host.docker.internal` |
   | Port | `5433` |
   | Database name | `retail_db` |
   | Username | `analyst` |
   | Password | `analyst123` |
   | SSL mode | `prefer` (or `disable` for local) |

   > **Why `host.docker.internal`?** Airbyte runs inside a Kubernetes cluster (kind), which has its own network. `host.docker.internal` lets it reach services exposed on your host machine's ports. Demo-postgres exposes port `5433` on the host.

5. Scroll down to **"Replication method"**. Select **"Detect Changes with CDC"** if available, otherwise select **"Scan Changes with User Defined Cursor"**.

   > For this demo, **"Scan Changes with User Defined Cursor"** is sufficient. CDC requires additional PostgreSQL configuration (logical replication).

6. Click **"Set up source"**. Airbyte will test the connection — you should see a green checkmark.

### What to look for

- All 8 tables should be discovered: `customers`, `products`, `orders`, `order_items`, `events`, `payments`, `shipments`, `support_tickets`.
- The 3 views (`customer_summary`, `product_performance`, `order_ops_overview`) may also appear — you can skip these.

### Common mistakes

- **Connection refused**: If Airbyte cannot reach `host.docker.internal:5433`, verify that demo-postgres is running with `docker compose -f docker-compose.demo-postgres.yml ps`. Also verify the port mapping shows `0.0.0.0:5433->5432/tcp`.
- **Authentication failed**: Double-check the password is `analyst123`.

---

## 5. Configure the S3 Data Lake (Iceberg) Destination

### Steps

1. Click **"Destinations"** in the left sidebar.

2. Click **"+ New destination"**.

3. Search for **"S3 Data Lake"** and select it.

4. Fill in the configuration:

   | Field | Value |
   |---|---|
   | Destination name | `iceberg-minio` |
   | S3 Bucket Name | `warehouse` |
   | S3 Bucket Region | `us-east-1` |
   | S3 Endpoint | `http://host.docker.internal:9000` |
   | S3 Access Key ID | value of `MINIO_ROOT_USER` from your `.env` |
   | S3 Secret Access Key | value of `MINIO_ROOT_PASSWORD` from your `.env` |
   | S3 Path Style Access | `true` (toggle ON) |

5. Under **"Output Format"**, select **"Iceberg"** if available, otherwise select **"Parquet"**.

6. If Iceberg format is selected, configure the catalog:

   | Field | Value |
   |---|---|
   | Catalog Type | `JDBC` |
   | JDBC Catalog URL | `jdbc:postgresql://host.docker.internal:5432/iceberg_catalog` |
   | JDBC Catalog Username | `iceberg` |
   | JDBC Catalog Password | `iceberg123` |
   | Default Schema / Namespace | `retail_raw` |

   > **Note**: The Iceberg catalog Postgres (`postgres-iceberg`) is exposed on port `5432` inside Docker but you need to check if it's mapped to a host port. If not, you may need to add a port mapping or use a different connectivity approach. Check `docker compose ps postgres-iceberg` for port info.

   > **Alternative approach**: If the Iceberg catalog connection is difficult from Airbyte's isolated network, use the **Parquet** output format instead. Airbyte will write raw Parquet files to MinIO at `s3://warehouse/retail_raw/`. You can then register them as Iceberg tables via a Spark or Trino `CREATE TABLE` command.

7. Click **"Set up destination"**. Airbyte will verify the connection.

### Common mistakes

- **S3 connection failed**: Ensure MinIO is running (`docker compose ps minio`). The endpoint must include `http://` prefix.
- **Path style access**: Must be enabled for MinIO. Without it, Airbyte tries virtual-hosted style URLs which MinIO does not support.

---

## 6. Create the Connection (Source → Destination)

### Steps

1. Click **"Connections"** in the left sidebar.

2. Click **"+ New connection"**.

3. Select:
   - **Source**: `demo-postgres`
   - **Destination**: `iceberg-minio`

4. On the **"Configure connection"** screen:

   - **Replication frequency**: Set to **"Manual"** for the lab (you will trigger syncs yourself). In production, you would set this to a schedule like "Every 24 hours".
   - **Sync mode**: For each table, select **"Full Refresh | Overwrite"** (simplest for the demo).
   - **Namespace**: Set the destination namespace to `retail_raw`.

5. Select all 8 tables for syncing. Deselect the views (`customer_summary`, `product_performance`, `order_ops_overview`) — you will build better versions with dbt.

6. Click **"Set up connection"**.

---

## 7. Run the Initial Sync

### Steps

1. On the connection page, click the **"Sync now"** button.

2. Airbyte will start syncing all 8 tables. You can watch progress on the connection page:
   - Each table shows a progress bar and row count.
   - The sync typically takes 1–3 minutes for this small demo dataset.

3. Wait for all 8 tables to show **"Succeeded"** status.

### Expected results

After the sync completes, you should see:

| Table | Rows |
|---|---|
| `customers` | 15 |
| `products` | 15 |
| `orders` | 20 |
| `order_items` | 31 |
| `events` | 21 |
| `payments` | 20 |
| `shipments` | 20 |
| `support_tickets` | 7 |

---

## 8. Verify Data in the Platform

### Verify in MinIO

1. Open `http://localhost:9001` and log in.
2. Navigate to the **warehouse** bucket.
3. Look for a `retail_raw/` folder (or the namespace Airbyte created).
4. Inside, you should see subfolders for each table containing Parquet or Iceberg data files.

### Verify in Trino

If Airbyte wrote Iceberg format with the JDBC catalog, Trino should see the tables immediately:

```sql
-- Run from JupyterHub or any Trino client
SHOW TABLES FROM iceberg.retail_raw;
SELECT COUNT(*) FROM iceberg.retail_raw.customers;
```

If Airbyte wrote raw Parquet (not Iceberg format), you need to register the tables in Iceberg. See the next section.

### Register Parquet files as Iceberg tables (if using Parquet output)

If Airbyte wrote raw Parquet files instead of Iceberg tables, create Iceberg tables from the Parquet files using Trino:

```sql
CREATE SCHEMA IF NOT EXISTS iceberg.retail_raw;

CREATE TABLE iceberg.retail_raw.customers AS
SELECT * FROM parquet_table('s3://warehouse/retail_raw/customers/');
```

Repeat for each table. Alternatively, use the Spark ingestion notebook from Lab 1 to read the Parquet files and write them as Iceberg tables.

---

## 9. Useful abctl Commands

| Command | What it does |
|---|---|
| `abctl local install` | Install/start Airbyte |
| `abctl local status` | Check if Airbyte is running |
| `abctl local credentials` | Show the admin username and password |
| `abctl local uninstall` | Remove Airbyte completely |

---

## Troubleshooting

### Airbyte UI not loading

```bash
abctl local status
```

If it shows "not installed", re-run `abctl local install`.

### Sync fails with connection errors

1. Check that the source database is running: `docker compose -f docker-compose.demo-postgres.yml ps`
2. Check that MinIO is running: `docker compose ps minio`
3. Verify `host.docker.internal` resolves on your OS. On Linux, you may need to add `--add-host=host.docker.internal:host-gateway` or use the actual IP address instead.

### Airbyte uses too much memory

Use low-resource mode:

```bash
abctl local uninstall
abctl local install --low-resource-mode
```
