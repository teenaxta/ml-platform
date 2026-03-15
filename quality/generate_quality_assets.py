from __future__ import annotations

from pathlib import Path

import pandas as pd
import trino
from evidently.metric_preset import DataDriftPreset, DataQualityPreset
from evidently.report import Report
from great_expectations.data_context import FileDataContext


ROOT_DIR = Path("/workspace")
GE_ROOT = ROOT_DIR / "great_expectations"
GE_DATA = GE_ROOT / "data"
EVIDENTLY_REPORTS = ROOT_DIR / "evidently" / "reports"


def trino_query(sql: str) -> pd.DataFrame:
    conn = trino.dbapi.connect(host="trino", port=8080, user="trino", catalog="iceberg", schema="analytics")
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    columns = [col[0] for col in cur.description]
    return pd.DataFrame(rows, columns=columns)


def build_ge_docs() -> None:
    GE_DATA.mkdir(parents=True, exist_ok=True)
    customer_360 = trino_query("SELECT * FROM iceberg.analytics.customer_360")
    churn_training = trino_query("SELECT * FROM iceberg.analytics.churn_training_dataset")
    customer_path = GE_DATA / "customer_360.csv"
    churn_path = GE_DATA / "churn_training_dataset.csv"
    customer_360.to_csv(customer_path, index=False)
    churn_training.to_csv(churn_path, index=False)

    context = FileDataContext.create(project_root_dir=str(GE_ROOT))
    datasource = context.sources.add_or_update_pandas_filesystem(
        name="retail_files",
        base_directory=str(GE_DATA),
    )
    customer_asset = datasource.add_csv_asset(name="customer_360", batching_regex=r"customer_360\.csv")
    churn_asset = datasource.add_csv_asset(
        name="churn_training_dataset",
        batching_regex=r"churn_training_dataset\.csv",
    )

    suites = {
        "customer_360_suite": customer_asset.build_batch_request(),
        "churn_training_suite": churn_asset.build_batch_request(),
    }

    for suite_name, batch_request in suites.items():
        suite = context.add_or_update_expectation_suite(expectation_suite_name=suite_name)
        validator = context.get_validator(
            batch_request=batch_request,
            expectation_suite_name=suite.expectation_suite_name,
        )
        validator.expect_column_values_to_not_be_null("customer_id")
        if "total_orders" in validator.columns():
            validator.expect_column_values_to_be_between("total_orders", min_value=0)
        if "lifetime_value" in validator.columns():
            validator.expect_column_values_to_be_between("lifetime_value", min_value=0)
        if "churn_label" in validator.columns():
            validator.expect_column_distinct_values_to_be_in_set("churn_label", [0, 1])
        validator.save_expectation_suite(discard_failed_expectations=False)
        context.add_or_update_checkpoint(
            name=f"{suite_name}_checkpoint",
            validations=[
                {
                    "batch_request": batch_request,
                    "expectation_suite_name": suite.expectation_suite_name,
                }
            ],
        )
        context.run_checkpoint(checkpoint_name=f"{suite_name}_checkpoint")

    context.build_data_docs()


def build_evidently_report() -> None:
    EVIDENTLY_REPORTS.mkdir(parents=True, exist_ok=True)
    scored = pd.read_csv(ROOT_DIR / "evidently" / "scored_dataset.csv")
    reference = scored.iloc[: max(4, len(scored) // 2)].copy()
    current = scored.iloc[max(4, len(scored) // 2) :].copy()
    current["avg_order_value"] = current["avg_order_value"] * 1.15
    current["prediction_probability"] = current["prediction_probability"].clip(upper=1.0)

    report = Report(metrics=[DataQualityPreset(), DataDriftPreset()])
    report.run(reference_data=reference, current_data=current)
    report.save_html(str(EVIDENTLY_REPORTS / "index.html"))


if __name__ == "__main__":
    build_ge_docs()
    build_evidently_report()
