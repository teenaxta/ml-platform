# Practice Lab Foundations

Use this document before either lab. It does not teach theory first. It tells you what must already be reachable, what "healthy" looks like, and what the two labs will expect you to do next.

## 1. What is already provided

You start with only these provided assets:

- a running platform based on this repository
- the demo PostgreSQL database loaded from `demo-postgres/init.sql`
- access to the platform UIs
- these workshop documents

You do not assume any prewritten learner code, prebuilt feature definitions, prebuilt dbt models, trained models, helper scripts, or generated outputs. If you see example assets elsewhere in the repository, ignore them while doing the workshop. The lab tells you exactly which files to create for your own implementation.

## 2. Shared assumptions for both labs

Both labs assume the following:

1. The platform is already up.
2. You can open the local URLs listed below from your browser.
3. Your Git remote is GitHub.
4. Your repository has a self-hosted GitHub Actions runner on the same machine as the platform so CI/CD can reach `localhost`, Docker, and the checked-out repository.
5. You will use the exact branch and commit flow written in the lab, not ad hoc edits in running containers.

If your Git platform is not GitHub, keep the file structure and commands the same and translate the workflow YAML into your CI system later.

## 3. Service URLs and the first health check

Open each of these before you start writing code. Do not skip this. You need to know what the healthy platform looks like before you add your own pipeline.

| Service | URL | What to do immediately | Healthy looks like | Broken looks like |
|---|---|---|---|---|
| CloudBeaver | `http://localhost:8978` | Complete the first-run admin wizard if this is your first visit. | You can reach the workspace screen. | The page never loads or loops back to setup after you finish. |
| JupyterHub | `http://localhost:8888` | Log in and click `Start My Server`. | You land in JupyterLab. | The server spinner never completes or shows a spawn error. |
| Spark master UI | `http://localhost:8080` | Open `Workers`. | One worker is listed with state `ALIVE`. In the current stack that worker reports `8` cores and `16384 MB` memory. | No workers are listed, or worker state is not `ALIVE`. |
| Spark worker UI | `http://localhost:8081` | Confirm the worker page opens. | The page shows the worker ID and resources. | The page is unreachable or blank. |
| Trino health endpoint | `http://localhost:8093/v1/info` | Open it directly in the browser. | The browser shows JSON. | Connection reset, timeout, or no JSON means Trino is not healthy. |
| MinIO Console | `http://localhost:9001` | Log in and open `Buckets`. | Buckets named `warehouse`, `mlflow-artifacts`, `mlserver-models`, `feast-offline`, `feast-registry`, and `monitoring` exist. | One or more buckets are missing. |
| Airflow | `http://localhost:8082` | Log in and open `DAGs`. | You can see at least `retail_ml_pipeline`. The current platform shows it as present and paused. | DAG list does not load, or the DAG is missing. |
| Superset | `http://localhost:8088` | Log in and confirm the home page loads. | You can reach the application shell. | Login fails or the UI shows bootstrap errors. |
| Grafana | `http://localhost:3000` | Open `Dashboards` and then `ML Platform Overview`. | The dashboard loads. `Prometheus Targets` should show `2` in the current stack. | The dashboard is missing or panels show `No data`. |
| Prometheus | `http://localhost:9090` | Open `Graph`, run `count(up)`, and click `Execute`. | The result is `2` in the current stack. | The query errors or returns `0`. |
| Great Expectations | `http://localhost:8091` | Open the home page. | You can see the validation index page. | Nginx returns 404 or the site is blank. |
| Evidently | `http://localhost:8092` | Open the report page. | The report renders a dashboard. | The page is blank or 404. |
| Feast UI | `http://localhost:6567` | Confirm the UI shell opens. | The Feast web UI loads. | The page errors or never loads. |
| MLflow | `http://localhost:5000` | Log in and open `Experiments`. | You can browse runs. The current stack contains `retail-churn-demo`. | The page returns auth errors or the experiment list never loads. |
| MLServer Swagger | `http://localhost:8085/v2/docs` | Open the Swagger page. | The docs render and list model endpoints. | The page is unreachable or empty. |
| dbt docs | `http://localhost:8090` | Open the generated docs site. | The docs shell loads and lineage can be explored. | Nginx returns 404 or the page is blank. |

## 4. Verify the source data before you build anything

You will use the demo PostgreSQL database as the only business-data starting point.

### 4.1 Create the CloudBeaver connection

1. Open `http://localhost:8978`.
2. If the first-run wizard appears, create the CloudBeaver admin account.
3. Click `New Connection`.
4. Choose `PostgreSQL`.
5. Enter these values:

```text
Host: demo-postgres
Port: 5432
Database: retail_db
Username: analyst
Password: analyst123
```

6. Click `Test Connection`.
7. Click `Create`.

### 4.2 Run the baseline SQL

In CloudBeaver, open `SQL Editor` for the new PostgreSQL connection and run this query:

```sql
select 'customers' as table_name, count(*) as row_count from customers
union all
select 'products', count(*) from products
union all
select 'orders', count(*) from orders
union all
select 'order_items', count(*) from order_items
union all
select 'events', count(*) from events
union all
select 'payments', count(*) from payments
union all
select 'shipments', count(*) from shipments
union all
select 'support_tickets', count(*) from support_tickets
order by 1;
```

Expected output:

| table_name | row_count |
|---|---:|
| customers | 15 |
| events | 21 |
| order_items | 31 |
| orders | 20 |
| payments | 20 |
| products | 15 |
| shipments | 20 |
| support_tickets | 7 |

If any count is lower, stop. The lab depends on this exact dataset.

### 4.3 Inspect the raw tables you will use most

Run these next:

```sql
select * from customers order by customer_id limit 5;
select * from orders order by order_id limit 5;
select * from events order by event_id limit 5;
select * from support_tickets order by ticket_id limit 5;
```

You need to see:

- customer IDs that match across tables
- order statuses such as `completed`, `returned`, and `pending`
- event types such as `page_view`, `add_to_cart`, `checkout`, and `support_ticket`
- support ticket rows that can later affect churn labeling

If `support_tickets` is empty, your churn label logic later in the lab will not match the expected results.

## 5. Shared CI/CD contract

Both labs use the same CI/CD behavior. The only difference is where the code lives.

### 5.1 Workflow files

Each lab creates workflow YAML under:

```text
.github/workflows/
```

### 5.2 Trigger rules

Use these exact trigger rules:

- `pull_request` to `main` runs validation only
- `push` to `main` runs validation and deployment

### 5.3 Image and artifact naming

Use these exact conventions in both labs:

```text
Image registry: ghcr.io/<github-owner>/<repository-name>
MLServer image name: ghcr.io/<github-owner>/<repository-name>/churn-mlserver:<git-sha>
dbt docs artifact name: dbt-docs-<git-sha>.tar.gz
Great Expectations artifact name: ge-data-docs-<git-sha>.tar.gz
Evidently artifact name: evidently-report-<git-sha>.tar.gz
```

### 5.4 Where outputs go after CI succeeds

Use this destination contract:

| Output | Destination | Who consumes it next |
|---|---|---|
| MLServer container image | GHCR | The deploy job updates the platform `mlserver` service to use this tag. |
| dbt docs tarball | GitHub Actions artifact and unpacked into `dbt/retail/target/` on the platform host | `dbt-docs` Nginx serves it at `http://localhost:8090`. |
| Great Expectations Data Docs tarball | GitHub Actions artifact and unpacked into `great_expectations/uncommitted/data_docs/local_site/` on the platform host | `great-expectations-docs` Nginx serves it at `http://localhost:8091`. |
| Evidently report tarball | GitHub Actions artifact and unpacked into `evidently/reports/` on the platform host | `evidently-ui` Nginx serves it at `http://localhost:8092`. |
| Airflow DAG Python file | Copied into `airflow/dags/` on the platform host | `airflow-webserver` and `airflow-scheduler` load it. |
| Feast parquet files | `s3://warehouse/feast/...` in MinIO | Feast offline store and materialization read them. |
| MLflow experiment metadata | `s3://mlflow-artifacts/...` plus the MLflow metadata database | MLflow UI renders the run. |

### 5.5 What to check after every push to `main`

After a deployment push, verify in this order:

1. GitHub Actions workflow finished green.
2. GHCR shows the new `churn-mlserver` image tag.
3. Airflow shows the DAG file loaded.
4. dbt docs site opens and shows your models.
5. Feast UI shows your entities and feature views.
6. MLflow shows a new run with metrics.
7. MLServer responds on `/v2/models/churn-model/infer`.
8. Great Expectations and Evidently pages refresh.
9. Grafana and Prometheus still show a healthy platform.

## 6. Shared verification commands

Use these commands exactly from the repository root when the lab tells you to verify from a terminal instead of the browser:

```bash
docker compose ps
curl -s http://localhost:8080/json/ | jq '{status: .status, workers: [.workers[] | {state, cores, memory}]}'
curl -s 'http://localhost:9090/api/v1/query?query=count(up)' | jq .
curl -s -u admin:AirflowAdmin789 http://localhost:8082/api/v1/dags | jq .
curl -s -u admin:MLflowAdmin777 http://localhost:5000/api/2.0/mlflow/experiments/search \
  -H 'Content-Type: application/json' \
  -d '{"max_results":50,"filter":"name = \"retail-churn-demo\""}' | jq .
curl -s http://localhost:8085/v2/models/churn-model/infer \
  -H 'Content-Type: application/json' \
  -d '{"inputs":[{"name":"input-0","shape":[1,8],"datatype":"FP64","data":[[28,3,213.96,71.32,15,1,0,0.0]]}]}' | jq .
```

What to expect:

- `docker compose ps` should show the platform services as `Up`
- the Spark JSON should show one worker with state `ALIVE`
- `count(up)` should return `2` in the current stack
- Airflow should list at least one DAG
- MLflow should list the `retail-churn-demo` experiment when runs exist
- MLServer should return JSON with a `predict` output

## 7. Shared UI-specific checks you will use later

### 7.1 Spark

Open `http://localhost:8080`.

- Click `Workers`.
- Confirm there is at least one worker.
- Read the `Cores` and `Memory` columns.
- Healthy during idle time means `Memory Used` is close to `0` and at least one worker is `ALIVE`.
- Broken means no worker is listed or the worker state is not `ALIVE`.

If you run a notebook or pipeline and jobs get stuck:

- go back to the Spark UI
- open the application entry under `Running Applications` or `Completed Applications`
- inspect `Stages`
- if tasks are failing, return to the code that triggered Spark and fix the query or memory usage there

### 7.2 Trino

Trino does not give you a rich UI. Use two checks:

1. Open `http://localhost:8093/v1/info`.
2. Use CloudBeaver or JupyterHub to run SQL through Trino.

Healthy means:

- `/v1/info` returns JSON
- queries return rows

Broken means:

- `/v1/info` resets the connection
- the SQL client cannot connect

### 7.3 Prometheus and Grafana

Open Grafana at `http://localhost:3000`, then `Dashboards`, then `ML Platform Overview`.

Read these panels:

- `Prometheus Targets`
- `Demo Postgres Connections`
- `Process CPU Usage`
- `Prometheus Head Series`

Healthy in the current stack:

- `Prometheus Targets` shows `2`
- `Demo Postgres Connections` is a small number such as `2`
- timeseries panels draw lines instead of showing `No data`

If Grafana looks wrong:

1. Open `http://localhost:9090`.
2. Run `count(up)`.
3. If it is `0`, Prometheus is broken.
4. If it is `2` but Grafana still shows no data, the Grafana data source or dashboard is misconfigured.

### 7.4 Great Expectations

Open `http://localhost:8091`.

- Stay on the index page first.
- Look at the validations table.
- You should see rows for `customer_360_suite` and `churn_training_suite`.
- The `Status` column should show green success icons.

Broken looks like:

- a red failed validation
- the suite name is missing entirely
- the page still shows an older timestamp after you know your pipeline ran

### 7.5 Evidently

Open `http://localhost:8092`.

- Scroll until you see `Dataset Summary`.
- Confirm the report renders tables and charts, not raw HTML or a blank page.
- In the current stack the report includes a dataset summary table and drift widgets.

Broken looks like:

- the page is blank
- the browser downloads HTML instead of rendering it
- the report never changes after a successful deployment

### 7.6 MLflow

Open `http://localhost:5000`.

- Log in.
- Open `Experiments`.
- Click your experiment name.
- Open the newest run.

You should always verify these fields:

- run name
- start time
- metrics such as `accuracy` and `f1_score`
- parameters such as `model_type` and `n_estimators`

Broken looks like:

- the run is missing
- metrics are blank
- the run status is `FAILED`

### 7.7 MLServer

Open `http://localhost:8085/v2/docs`.

- Expand the inference endpoint for `churn-model`.
- Confirm the model exists.

Then send a test request:

```bash
curl -s http://localhost:8085/v2/models/churn-model/infer \
  -H 'Content-Type: application/json' \
  -d '{"inputs":[{"name":"input-0","shape":[1,8],"datatype":"FP64","data":[[28,3,213.96,71.32,15,1,0,0.0]]}]}' | jq .
```

Healthy looks like JSON with an `outputs` array.

Broken looks like:

- 404 means the model was not loaded
- 500 means the model bundle is malformed or the input shape is wrong

### 7.8 Feast

Open `http://localhost:6567`.

- Open the entities page.
- Confirm the `customer` entity exists.
- Open the feature views page.
- Confirm feature views such as `customer_stats` and `customer_behavior` exist after the lab creates them.

Broken looks like:

- the UI shell opens but there are no entities or feature views
- feature views exist but materialization never happened, so online lookups return nulls

### 7.9 dbt docs

Open `http://localhost:8090`.

- Click `View Lineage Graph`.
- Search for `customer_360`.
- Click the model node.
- Read the description and upstream dependencies.

Healthy looks like:

- the model node exists
- the graph shows upstream staging nodes
- tests are listed under the model metadata

Broken looks like:

- the model cannot be found
- the graph is empty
- the docs page is older than your latest pipeline run

## 8. Git discipline that applies to both labs

Use this exact flow every time:

```bash
git checkout -b workshop/<short-task-name>
git status
git add <files>
git commit -m "<scope>: <change>"
git push -u origin workshop/<short-task-name>
```

Do not push directly to `main`. Open a pull request, let validation run, merge, and then let the deployment job update the platform.

If you skip the branch and PR step, you remove the only clean way to compare "last known good" against "what I just changed."

