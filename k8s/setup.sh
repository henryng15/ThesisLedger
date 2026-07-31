#!/usr/bin/env bash
# Bring up the local kind cluster used for the parallel-worker demo.
#
# NOTE: configmap.yaml points POSTGRES_HOST at "db" and REDIS_URL at "redis",
# but there are no manifests for either yet. api/worker will not become ready
# until those are added (or pointed at services outside the cluster).
set -euo pipefail

CLUSTER="${CLUSTER:-thesisledger}"
IMAGE="thesisledger-api:latest"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! kind get clusters 2>/dev/null | grep -qx "$CLUSTER"; then
  kind create cluster --name "$CLUSTER"
fi

docker build -t "$IMAGE" "$ROOT/backend"
kind load docker-image "$IMAGE" --name "$CLUSTER"

kubectl apply -f "$ROOT/k8s/namespace.yaml"
kubectl apply -n thesisledger -f "$ROOT/k8s/configmap.yaml"
kubectl apply -n thesisledger -f "$ROOT/k8s/secrets.yaml"
kubectl apply -n thesisledger -f "$ROOT/k8s/api.yaml"
kubectl apply -n thesisledger -f "$ROOT/k8s/worker.yaml"

kubectl rollout status -n thesisledger deployment/api --timeout=180s
kubectl rollout status -n thesisledger deployment/worker --timeout=180s

echo
echo "Ready. Scale workers for the demo:"
echo "  kubectl scale -n thesisledger deployment/worker --replicas=3"
