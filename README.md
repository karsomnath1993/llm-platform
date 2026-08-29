# llm-platform

A production-style LLM serving platform built from scratch to learn Docker, Docker Compose, and Kubernetes — covering containerization, orchestration, CI/CD, observability, and security hardening for a real FastAPI + Ollama application.

**Live stack:** FastAPI gateway → Ollama (qwen3:0.6b) → Redis cache, deployed on Kubernetes with Prometheus monitoring, structured logging, and a full GitHub Actions CI/CD pipeline.

---

## Architecture

```
                    Client
                      │
                      ▼
              FastAPI LLM Gateway  ──────► Prometheus /metrics
                      │                     Structured JSON logs
        ┌─────────────┼─────────────┐
        ▼             ▼             
     Redis          Ollama
     Cache          (qwen3:0.6b)

    Docker → Docker Compose → Kubernetes
                                  │
                     ┌────────────┼────────────┐
                     ▼            ▼            ▼
                Deployment    Service         HPA
                     │
              ┌──────┴──────┐
              ▼             ▼
             Pod           Pod

    CI/CD: git push → pytest → Trivy scan → docker build → GHCR push
```

**Namespace:** `llm-platform` on a local `kind` cluster
**Registry:** `ghcr.io/karsomnath1993/llm-platform-api`
**Current version:** `1.5.0`

---

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn (async) |
| LLM inference | Ollama, `qwen3:0.6b` |
| Cache | Redis (SHA256-keyed, 300s TTL) |
| Containerization | Docker (non-root, multi-layer cached, HEALTHCHECK) |
| Local orchestration | Docker Compose (with profiles) |
| Production orchestration | Kubernetes (`kind`) |
| CI/CD | GitHub Actions → GHCR |
| Monitoring | Prometheus (custom app metrics + Kubernetes service discovery) |
| Logging | Structured JSON via custom formatter |
| Security scanning | Trivy (image vulnerability scanning in CI) |

---

## What's implemented

### API (`app/`)
- `GET /health/live`, `GET /health/ready`, `GET /info`, `GET /metrics`
- `POST /v1/chat` — cache-first, falls back to Ollama generation
- Structured JSON logging with per-request `request_id`
- Prometheus metrics: request counts (by status), latency histogram, cache hit/miss counters
- Model + app version + git commit exposed via `/info` for full traceability

### Docker
- Non-root user, small base image (`python:3.12-slim`), `.dockerignore`, `HEALTHCHECK`
- Layer-cache-optimized `COPY` ordering
- Build-time `GIT_COMMIT` injection for version traceability

### Docker Compose
- `api`, `ollama`, `redis` — always-on default profile
- `prometheus`, `grafana` — opt-in via `--profile monitoring`
- Health-aware startup ordering (`depends_on: condition: service_healthy`)

### Kubernetes
- Namespace, ConfigMap, Secret, Deployments/Services for api/ollama/redis
- Rolling update strategy (`maxUnavailable: 0, maxSurge: 1`) — zero-downtime deploys
- Startup/readiness/liveness probes
- HPA (CPU-based, 2–5 replicas)
- RBAC (ServiceAccount/Role/RoleBinding) for Prometheus's Kubernetes service discovery
- `imagePullSecrets` for private GHCR images
- `readOnlyRootFilesystem: true` on the API container

### CI/CD (`.github/workflows/ci.yml`)
- `test` job: pytest on every push/PR
- `build-and-push` job (gated on tests passing, main branch only): Docker build → Trivy vulnerability scan → push to GHCR tagged with commit SHA

### Monitoring & Logging
- Prometheus deployed in-cluster, auto-discovers API pods via Kubernetes API (RBAC-scoped)
- Custom metrics: `llm_requests_total{status}`, `llm_request_latency_seconds`, `cache_hits_total`, `cache_misses_total`
- JSON structured logs to stdout, captured by `kubectl logs`

### Security
- Pinned dependency versions
- Trivy image scanning in CI
- Non-root containers throughout
- `readOnlyRootFilesystem` on API pods
- RBAC least-privilege for Prometheus

---

## Key findings (from real load testing and debugging)

**1. LLM inference is CPU-bound, not concurrency-bound.**
A k6 load test with unique prompts (forcing real Ollama generation) showed ~57s average latency with only 2 concurrent users, and HPA never triggered — because the bottleneck is Ollama's single CPU-bound inference, invisible to the API pods' CPU metrics. Increasing `OLLAMA_NUM_PARALLEL` from 1→3 didn't improve throughput; it just split the same CPU budget across more concurrent generations, each proportionally slower.

**2. Caching provides a ~10,000x speedup for repeated prompts.**
Identical-prompt load testing hit **20,932 requests in 60 seconds at 5.5ms average latency** (Redis cache hits) vs. **3 requests in 60 seconds at 57.8s average latency** (uncached Ollama generation) — a dramatic, measured demonstration of why the Lab 4 caching layer matters.

**3. More API replicas ≠ more LLM throughput.**
Scaling `llm-api` from 2→5 replicas has no effect on chat throughput, since all replicas funnel through the same single Ollama backend. This is a real-world illustration of why LLM serving scales differently from typical stateless web APIs.

**4. "Works locally, fails in CI" — twice.**
Two files (`app/logging_config.py`, `app/metrics.py`) existed and worked locally but were never actually committed to git, causing CI failures that didn't reproduce locally. Diagnosed via `git ls-files` and `git show HEAD:<path>` — a real, common class of bug worth recognizing on sight.

**5. Kubernetes node-level image caching can mask a "successful" deploy.**
Multiple times, a `docker build` + `docker push` + `kubectl set image` sequence appeared to succeed, but the running pods still served old code — because `kind`'s node had cached the same image tag from an earlier (broken) build. Root-caused via `crictl images` on the node, fixed with `imagePullPolicy: Always` and verified by `kubectl exec ... cat` directly against the running container's filesystem — never trusting the API response alone as proof of a successful deploy.

---

## Failure drills performed

| Failure | Trigger | Recovery |
|---|---|---|
| Pod deleted | `kubectl delete pod` | ReplicaSet auto-recreated it |
| Ollama container lost (real incident) | Docker/node restart | `describe pod` → diagnosed `SandboxChanged` → force-delete → auto-recreate → re-pulled model |
| Bad image tag | Deliberate (`does-not-exist` tag) | `kubectl rollout undo` |
| OOMKilled | Deliberate 20Mi memory limit | Exit code 137 confirmed, reverted limits, rolling update |
| Bad ConfigMap (DNS failure) | Deliberate `OLLAMA_URL` typo | `[Errno -3] Temporary failure in name resolution`, reverted + rollout restart |

---

## Local development

```bash
# Docker Compose (default: api, ollama, redis)
docker compose up --build

# With monitoring stack (adds Prometheus + Grafana)
docker compose --profile monitoring up --build
```

## Kubernetes deployment

```bash
kind create cluster --name llm-platform
kubectl apply -f k8s/
kubectl exec -it deployment/ollama -n llm-platform -- ollama pull qwen3:0.6b
kubectl port-forward service/llm-api 8000:8000 -n llm-platform
```

## CI/CD

Every push to `main`:
1. Runs `pytest`
2. If tests pass, builds a Docker image tagged with the commit SHA
3. Scans the image with Trivy for CRITICAL/HIGH vulnerabilities
4. Pushes to `ghcr.io/karsomnath1993/llm-platform-api`

---

## Known gaps / next steps

- **NetworkPolicies** — currently any pod in the namespace can reach Redis directly; no network-level isolation between services.
- **Persistent storage for Ollama** — the Ollama pod has no PersistentVolumeClaim, so the pulled model is lost on every pod restart.
- **Secrets not fully wired** — `k8s/secret.yaml` exists as a pattern demonstration but isn't consumed by any running service (Redis has no auth).
- **Single Ollama replica** — no redundancy; a more resilient design would need either multiple Ollama replicas behind a load-balancing service, or a move to a GPU-backed inference server (vLLM) sized for expected concurrency.
- **Pod Security Standards** — not yet enforced at the namespace level.

---

## Interview-ready talking points

- Diagnosed and fixed a genuine node-level image-caching bug in Kubernetes using `crictl`, distinct from Docker's build cache.
- Measured and explained *why* LLM inference throughput doesn't scale the same way as typical web API throughput (CPU-bound single-model-instance bottleneck vs. horizontal replica scaling).
- Quantified caching's real-world impact with actual load-test data (10,000x latency difference, hit vs. miss).
- Built and debugged a real CI/CD pipeline, including catching "local works, CI fails" bugs via `git ls-files` / `git show`.
- Implemented RBAC least-privilege for a monitoring system that needs Kubernetes API access.
- Performed failure injection (OOMKilled, bad config, bad image, pod deletion) and one real unplanned incident (Ollama sandbox loss on node restart), diagnosing each via `kubectl describe`/`logs`/`events` rather than guessing.