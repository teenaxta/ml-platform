# Notebook 03: Train a churn model, log it to MLflow, and save it for MLServer

import json
import os
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import pandas as pd
import trino
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

conn = trino.dbapi.connect(
    host=os.environ.get("TRINO_HOST", "trino"),
    port=int(os.environ.get("TRINO_PORT", "8080")),
    user=os.environ.get("TRINO_USER", "trino"),
    catalog=os.environ.get("TRINO_CATALOG", "iceberg"),
    schema=os.environ.get("TRINO_SCHEMA", "analytics"),
)
cursor = conn.cursor()
cursor.execute("SELECT * FROM iceberg.analytics.churn_training_dataset ORDER BY customer_id")
dataset = pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])

features = [
    "age",
    "total_orders",
    "lifetime_value",
    "avg_order_value",
    "days_since_last_order",
    "page_views_30d",
    "support_tickets",
    "return_rate",
]
X = dataset[features]
y = dataset["churn_label"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
model = RandomForestClassifier(n_estimators=50, random_state=42)
model.fit(X_train, y_train)
predictions = model.predict(X_test)
accuracy = accuracy_score(y_test, predictions)

mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000"))
mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT_NAME", "retail-churn-demo"))
with mlflow.start_run(run_name="notebook-random-forest"):
    mlflow.log_metric("accuracy", accuracy)
    mlflow.sklearn.log_model(model, artifact_path="model")

model_dir = Path("/srv/jupyterhub/notebooks/churn-model")
model_dir.mkdir(parents=True, exist_ok=True)
joblib.dump(model, model_dir / "model.joblib")
(model_dir / "model-settings.json").write_text(
    json.dumps(
        {
            "name": "churn-model",
            "implementation": "mlserver_sklearn.SKLearnModel",
            "parameters": {"uri": "./model.joblib", "version": "v1"},
        },
        indent=2,
    ),
    encoding="utf-8",
)

print(f"Logged accuracy={accuracy:.3f} and saved an MLServer model bundle to {model_dir}")
