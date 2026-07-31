#!/usr/bin/env bash
# Bring up the local kind cluster used for the parallel-worker demo.
set -euo pipefail

CLUSTER="${CLUSTER:-thesisledger}"
IMAGE="thesisledger-api:latest"
NS="thesisledger"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  echo "==> Creating kind cluster '$CLUSTER'"
  kind create cluster --name "$CLUSTER"
fi

echo "==> Building and loading the API image"
docker build -t "$IMAGE" "$ROOT/backend"
kind load docker-image "$IMAGE" --name "$CLUSTER"

echo "==> Applying manifests"
kubectl apply -f "$ROOT/k8s/namespace.yaml"

# pgvector's CREATE EXTENSION runs from an initdb script mounted off this map.
kubectl create configmap postgres-init -n "$NS" \
  --from-file="$ROOT/infra/postgres/init/01_extensions.sql" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -n "$NS" -f "$ROOT/k8s/configmap.yaml"
kubectl apply -n "$NS" -f "$ROOT/k8s/secrets.yaml"
kubectl apply -n "$NS" -f "$ROOT/k8s/db.yaml"
kubectl apply -n "$NS" -f "$ROOT/k8s/redis.yaml"

echo "==> Waiting for datastores"
kubectl rollout status -n "$NS" statefulset/db --timeout=180s
kubectl rollout status -n "$NS" deployment/redis --timeout=120s

kubectl apply -n "$NS" -f "$ROOT/k8s/api.yaml"
kubectl apply -n "$NS" -f "$ROOT/k8s/worker.yaml"

echo "==> Waiting for app"
kubectl rollout status -n "$NS" deployment/api --timeout=180s
kubectl rollout status -n "$NS" deployment/worker --timeout=180s

echo "==> Running migrations"
kubectl exec -n "$NS" deployment/api -- python manage.py migrate --no-input

cat <<EOF

Ready.

  Scale workers for the demo:
    kubectl scale -n $NS deployment/worker --replicas=3

  Watch them pick up jobs:
    kubectl get pods -n $NS -w

  Reach the API:
    kubectl port-forward -n $NS svc/api 8000:8000

  Tear down:
    kind delete cluster --name $CLUSTER
EOF
