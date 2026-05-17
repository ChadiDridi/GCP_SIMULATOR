# GCP Simulator

Local GCP services simulator — like **Azurite** for Azure, but for GCP.

Install once, run any combination of services locally with a single command.

```bash
pip install gcp-simulator
gcp-sim start --all
```

---

## Services Simulated

| Service | API Path Prefix | Notes |
|---------|----------------|-------|
| Cloud Storage (GCS) | `/storage/v1/b/...` | Buckets, objects, resumable upload |
| Pub/Sub | `/v1/projects/{p}/topics/...` | Topics, subscriptions, publish, pull, push |
| BigQuery | `/bigquery/v2/projects/{p}/...` | Datasets, tables, SQL query passthrough to PG |
| Firestore | `/v1/projects/{p}/databases/.../documents/...` | CRUD + runQuery |
| Cloud SQL | `/sql/v1beta4/projects/{p}/instances/...` | Spins up real PG/MySQL Docker containers |
| Cloud Spanner | `/v1/projects/{p}/instances/...` | Sessions, transactions, SQL passthrough |
| Bigtable | `/v2/projects/{p}/instances/...` | Rows, mutations, readRows |
| Memorystore | `/v1/projects/{p}/locations/.../instances/...` | Real Redis container |
| **Cloud Run** | `/v1/projects/{p}/locations/.../services/...` | **Real Docker execution + proxy at `/run/<svc>/`** |
| GCE (Compute) | `/compute/v1/projects/{p}/zones/.../instances/...` | Metadata only |
| VPC / Networking | `/compute/v1/projects/{p}/global/networks/...` | Networks, subnets, firewall rules |
| Load Balancing | `/compute/v1/projects/{p}/global/forwardingRules/...` | Forwarding rules, backends, health checks |
| Secret Manager | `/v1/projects/{p}/secrets/...` | Secrets + versioned payloads |
| Dataflow | `/v1b3/projects/{p}/locations/.../jobs/...` | Job metadata (no execution) |
| Dataform | `/v1beta1/projects/{p}/locations/.../repositories/...` | Repos, workspaces, compilation results |
| IAM | `/v1/projects/{p}/roles/...` | Custom roles, policies, service accounts |
| Cloud DNS | `/dns/v1/projects/{p}/managedZones/...` | Zones, record sets |
| Cloud Scheduler | `/v1/projects/{p}/locations/.../jobs/...` | Jobs + `:run` fires real HTTP |
| Cloud Tasks | `/v2/projects/{p}/locations/.../queues/...` | Queues, tasks + real HTTP dispatch |
| OAuth2 | `/token`, `/o/oauth2/token` | JWT assertion + dev token |

---

## Installation

```bash
pip install gcp-simulator
```

**Requirements**: Python 3.11+, Docker (for PostgreSQL, Cloud Run, Cloud SQL, Memorystore)

---

## Usage

### Start all services
```bash
gcp-sim start --all
```

### Start specific services
```bash
gcp-sim start --services gcs,pubsub,bigquery,firestore
gcp-sim start --services secretmanager,cloudrun,cloudsql
gcp-sim start --services vpc,gce,lb,dns
```

### All CLI commands
```
gcp-sim start [--services X,Y,Z | --all] [--port 9099] [--project local-dev] [--dev-token dev-token]
gcp-sim stop [--keep-containers]
gcp-sim status
gcp-sim reset [--service NAME]
gcp-sim service-account create [--project P] [--email E] [--output key.json]
```

### Options
| Flag | Default | Description |
|------|---------|-------------|
| `--services` | `gcs,pubsub,bigquery,firestore` | Comma-separated service list |
| `--all` | — | Enable all 19 services |
| `--port` | `9099` | HTTP port |
| `--project` | `local-dev` | Default GCP project ID |
| `--dev-token` | `dev-token` | Always-valid Bearer token (no auth needed) |
| `--sqlite` | — | Use SQLite instead of PostgreSQL (limited) |
| `--no-docker` | — | Skip container management (use existing DB) |

---

## Auth

### Dev token (zero setup)
```bash
curl -H "Authorization: Bearer dev-token" http://localhost:9099/storage/v1/b?project=local-dev
```

### Service account JSON
```bash
gcp-sim service-account create --output ./sa.json
export GOOGLE_APPLICATION_CREDENTIALS=./sa.json
```
The key file's `token_uri` points to `http://localhost:9099/o/oauth2/token` — the Google SDK reads this automatically.

---

## SDK Connection Examples

### Cloud Storage
```python
from google.cloud import storage
from google.api_core.client_options import ClientOptions

client = storage.Client(
    project="local-dev",
    client_options=ClientOptions(api_endpoint="http://localhost:9099")
)
bucket = client.create_bucket("my-bucket")
blob = bucket.blob("hello.txt")
blob.upload_from_string("Hello!")
print(blob.download_as_text())
```

### BigQuery
```python
import os
os.environ["BIGQUERY_EMULATOR_HOST"] = "http://localhost:9099"
from google.cloud import bigquery

client = bigquery.Client(project="local-dev")
client.create_dataset("my_ds")
for row in client.query("SELECT 1 AS n"):
    print(row)
```

### Pub/Sub (REST transport — gRPC not supported)
```python
from google.cloud import pubsub_v1
from google.api_core.client_options import ClientOptions

opts = ClientOptions(api_endpoint="http://localhost:9099")
pub = pubsub_v1.PublisherClient(transport="rest", client_options=opts)
sub = pubsub_v1.SubscriberClient(transport="rest", client_options=opts)

topic = pub.topic_path("local-dev", "my-topic")
sub_path = sub.subscription_path("local-dev", "my-sub")
pub.create_topic(request={"name": topic})
sub.create_subscription(request={"name": sub_path, "topic": topic})
pub.publish(topic, data=b"hello")
```

### Firestore
```python
from google.cloud import firestore
from google.api_core.client_options import ClientOptions

client = firestore.Client(
    project="local-dev",
    client_options=ClientOptions(api_endpoint="http://localhost:9099")
)
client.collection("users").document("alice").set({"name": {"stringValue": "Alice"}})
```

### Secret Manager
```python
from google.cloud import secretmanager
from google.api_core.client_options import ClientOptions

client = secretmanager.SecretManagerServiceClient(
    client_options=ClientOptions(api_endpoint="http://localhost:9099")
)
parent = "projects/local-dev"
secret = client.create_secret(request={"parent": parent, "secret_id": "my-secret", "secret": {"replication": {"automatic": {}}}})
client.add_secret_version(request={"parent": secret.name, "payload": {"data": b"my-secret-value"}})
response = client.access_secret_version(request={"name": f"{secret.name}/versions/latest"})
print(response.payload.data)
```

### Cloud Run (real Docker execution)
```python
import httpx

# Create a Cloud Run service (starts a real Docker container)
resp = httpx.post(
    "http://localhost:9099/v1/projects/local-dev/locations/us-central1/services",
    headers={"Authorization": "Bearer dev-token"},
    json={
        "metadata": {"name": "my-app"},
        "spec": {"template": {"spec": {"containers": [{"image": "nginx:alpine"}]}}}
    }
)
service_url = resp.json()["status"]["url"]
# service_url = "http://localhost:9099/run/my-app"
# All requests to /run/my-app/... are proxied to the running nginx container

# Call the service
print(httpx.get(service_url).status_code)
```

### Memorystore
```python
import redis
# After creating a Memorystore instance, get host/port from the API response
r = redis.Redis(host="127.0.0.1", port=6379)
r.set("key", "value")
print(r.get("key"))
```

### Cloud SQL
```python
import psycopg2
# After creating a Cloud SQL instance, connect directly:
conn = psycopg2.connect(host="127.0.0.1", port=<mapped_port>, user="postgres", password="postgres", dbname="postgres")
```

---

## Kubernetes / Helm

```bash
docker build -t gcp-simulator:latest .
minikube image load gcp-simulator:latest

helm repo add bitnami https://charts.bitnami.com/bitnami
helm dep update helm/gcp-simulator/
helm install gcp-sim helm/gcp-simulator/ \
  --set simulator.enabledServices="gcs\,pubsub\,bigquery\,firestore\,secretmanager"

export SIMULATOR_URL=http://$(minikube ip):30099
curl $SIMULATOR_URL/health
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GCP_SIM_DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL URL |
| `GCP_SIM_PROJECT_ID` | `local-dev` | Default project |
| `GCP_SIM_DEV_TOKEN` | `dev-token` | Always-valid token |
| `GCP_SIM_ENABLED_SERVICES` | `gcs,pubsub,bigquery,firestore` | Active services (or `all`) |
| `GCP_SIM_LOG_LEVEL` | `INFO` | Log level |
| `GCP_SIM_DATA_DIR` | `~/.gcp-sim` | Data directory |

---

## API Docs

OpenAPI docs available at `http://localhost:9099/docs` when running.

---

## Architecture

```
gcp-sim start
  │
  ├─ Docker: gcp-sim-postgres (PostgreSQL 15)
  ├─ Docker: gcp-sim-redis    (Redis 7, if memorystore enabled)
  │
  └─ FastAPI server :9099
       ├─ OAuth2        → /token, /o/oauth2/token
       ├─ GCS           → /storage/v1/...
       ├─ Pub/Sub       → /v1/projects/.../topics|subscriptions
       ├─ BigQuery      → /bigquery/v2/...
       ├─ Firestore     → /v1/projects/.../databases/.../documents
       ├─ Cloud SQL     → /sql/v1beta4/... (spins Docker containers)
       ├─ Spanner       → /v1/projects/.../instances (SQL passthrough)
       ├─ Bigtable      → /v2/projects/.../instances
       ├─ Memorystore   → /v1/.../instances (connects to Redis)
       ├─ Cloud Run     → /v1/.../services (real Docker) + /run/<svc>/...
       ├─ GCE           → /compute/v1/.../instances
       ├─ VPC           → /compute/v1/.../networks|subnetworks|firewalls
       ├─ Load Balancer → /compute/v1/.../forwardingRules|backendServices
       ├─ Secret Mgr    → /v1/projects/.../secrets
       ├─ Dataflow      → /v1b3/projects/.../jobs
       ├─ Dataform      → /v1beta1/projects/.../repositories
       ├─ IAM           → /v1/projects/.../roles|serviceAccounts
       ├─ DNS           → /dns/v1/projects/.../managedZones
       ├─ Scheduler     → /v1/projects/.../jobs (HTTP dispatch on :run)
       └─ Tasks         → /v2/projects/.../queues|tasks (real HTTP dispatch)
```
