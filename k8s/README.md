# Kubernetes Manifests for ThesisLedger

Local Kubernetes deployment using [kind](https://kind.sigs.k8s.io/).

## Prerequisites

- Docker
- kind: `brew install kind` or `go install sigs.k8s.io/kind@latest`
- kubectl: `brew install kubectl`

## Quick Start

```bash
# 1. Create cluster
kind create cluster --name thesisledger

# 2. Build and load images
docker build -t thesisledger-api:latest ./backend
kind load docker-image thesisledger-api:latest --name thesisledger

# 3. Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml  # Edit secrets first!
kubectl apply -f k8s/api.yaml
kubectl apply -f k8s/worker.yaml

# 4. Check status
kubectl get pods -n thesisledger

# 5. Port forward to access API
kubectl port-forward svc/api 8000:8000 -n thesisledger
```

## Scaling Workers

Demonstrate parallel processing:

```bash
# Scale to 3 workers
kubectl scale deployment worker --replicas=3 -n thesisledger

# Watch scaling
kubectl get pods -n thesisledger -w

# Trigger multiple analyses and watch workers process in parallel
```

## Cleanup

```bash
kind delete cluster --name thesisledger
```

## Notes

- DB and Redis run externally (Compose) or need separate manifests
- For production, use managed services (Cloud SQL, ElastiCache, etc.)
- Ollama needs GPU node or runs externally
