# 🚀 DevOps Engineer Assessment — Scale Under Constraint

> **Objective:** Make a deliberately under-optimised application survive **10,000 concurrent users** against a single, constrained MongoDB node.

---

## Table of Contents

1. [Overview & Rules](#1-overview--rules)
2. [System Architecture](#2-system-architecture)
3. [Prerequisites — Installing the Tools](#3-prerequisites--installing-the-tools)
   - [Docker](#31-docker)
   - [k3d](#32-k3d)
   - [kubectl](#33-kubectl)
   - [k6 (Stress Test)](#34-k6-stress-test-tool)
4. [Environment Setup](#4-environment-setup)
5. [Verifying the Environment](#5-verifying-the-environment)
6. [Running the Stress Test (Baseline)](#6-running-the-stress-test-baseline)
7. [Your Task — Optimisation Targets](#7-your-task--optimisation-targets)
8. [Pass Criteria](#8-pass-criteria)
9. [Submission Checklist](#9-submission-checklist)
10. [Hints (Read Only When Stuck)](#10-hints-read-only-when-stuck)

---

## 1. Overview & Rules

You are given a small web service connected to a MongoDB database. Both are deployed inside a local Kubernetes cluster (k3d). The system, as provided, **will collapse under load**. Your job is to fix it.

### Hard Rules (cannot be changed)

| Constraint                     | Value                          |
| ------------------------------ | ------------------------------ |
| MongoDB nodes                  | **1** (no horizontal scaling)  |
| MongoDB memory limit           | **500 MiB**                    |
| MongoDB IOPS cap (simulated)   | **100 concurrent I/O tickets** |
| Reads per `/api/data` request  | **5** (fixed in source code)   |
| Writes per `/api/data` request | **5** (fixed in source code)   |

### What you CAN change

- Application code (within the language you choose: Python or Node.js)
- Dockerfile and container configuration
- Number of application pod replicas
- Kubernetes resource requests/limits for **application pods only**
- Kubernetes manifests for the application (not the MongoDB deployment)
- Introduce a caching layer (Redis, Memcached, etc.) — but you must deploy it inside the cluster
- Ingress/proxy configuration
- Anything else not listed in the "Hard Rules" above

### What you CANNOT change

- `k8s/mongodb/deployment.yaml` — MongoDB replicas, memory limits, IOPS constraints
- The count of reads/writes inside the `/api/data` handler (the `for` loop bounds)
- The Kubernetes Namespace name (`assessment`)

---

## 2. System Architecture

```
                          ┌──────────────────────────────────────────────┐
                          │              k3d Cluster (local)             │
                          │                                              │
   Browser / k6           │   ┌──────────────┐     ┌─────────────────┐  │
   ──────────────►  80    │   │   Traefik    │────►│   App (Python   │  │
   (assessment.local)     │   │   Ingress    │     │   or Node.js)   │  │
                          │   └──────────────┘     │   replicas: 1   │  │
                          │                        └────────┬────────┘  │
                          │                                 │           │
                          │                        ┌────────▼────────┐  │
                          │                        │    MongoDB      │  │
                          │                        │  1 node         │  │
                          │                        │  500 MiB RAM    │  │
                          │                        │  ~100 IOPS      │  │
                          │                        └─────────────────┘  │
                          └──────────────────────────────────────────────┘
```

### Key Endpoints

| Endpoint         | Description                                           |
| ---------------- | ----------------------------------------------------- |
| `GET /healthz`   | Liveness probe — always returns 200                   |
| `GET /readyz`    | Readiness probe — checks MongoDB connectivity         |
| `GET /api/data`  | **Assessment endpoint** — 5 reads + 5 writes per call |
| `GET /api/stats` | Collection document count                             |

---

## 3. Prerequisites — Installing the Tools

### 3.1 Docker

Docker must be installed and the daemon must be running before you proceed.

- **Linux:** https://docs.docker.com/engine/install/
- **macOS / Windows:** Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)

Verify:

```bash
docker version
```

---

### 3.2 k3d

k3d runs a full k3s Kubernetes cluster inside Docker containers — no VMs needed.

#### 🐧 Linux (all distributions)

```bash
# Via the official install script
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# Or via Homebrew on Linux
brew install k3d
```

Verify:

```bash
k3d version
```

#### 🍎 macOS

```bash
# Homebrew (recommended)
brew install k3d

# Or via the install script
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
```

Verify:

```bash
k3d version
```

#### 🪟 Windows

**Option A — winget (Windows Package Manager)**

```powershell
winget install k3d
```

**Option B — Chocolatey**

```powershell
choco install k3d
```

**Option C — Manual**

1. Go to https://github.com/k3d-io/k3d/releases/latest
2. Download `k3d-windows-amd64.exe`
3. Rename it to `k3d.exe` and place it in a directory on your `PATH` (e.g. `C:\tools\`)

Verify (PowerShell):

```powershell
k3d version
```

#### 🏄 Arch Linux

```bash
# Via pacman (community repo)
sudo pacman -S k3d

# Or AUR
yay -S k3d-bin
```

Verify:

```bash
k3d version
```

---

### 3.3 kubectl

kubectl is the Kubernetes command-line tool.

#### 🐧 Linux

```bash
# Download the latest stable release
curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Arch Linux
sudo pacman -S kubectl

# Via Homebrew on Linux
brew install kubectl
```

#### 🍎 macOS

```bash
brew install kubectl
```

#### 🪟 Windows

```powershell
# winget
winget install Kubernetes.kubectl

# Chocolatey
choco install kubernetes-cli

# Or download manually from:
# https://dl.k8s.io/release/v1.30.0/bin/windows/amd64/kubectl.exe
```

Verify (all platforms):

```bash
kubectl version --client
```

---

### 3.4 k6 (Stress Test Tool)

k6 is used to run the included stress test.

#### 🐧 Linux

```bash
# Debian/Ubuntu
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6

# Fedora/RHEL/CentOS
sudo dnf install https://dl.k6.io/rpm/repo.rpm
sudo dnf install k6

# Arch Linux
yay -S k6-bin

# Via Homebrew on Linux
brew install k6
```

#### 🍎 macOS

```bash
brew install k6
```

#### 🪟 Windows

```powershell
# winget
winget install k6

# Chocolatey
choco install k6
```

Verify (all platforms):

```bash
k6 version
```

---

## 4. Environment Setup

### Step 1 — Clone the repository

```bash
git clone <repo-url>
cd devops-assessment
```

### Step 2 — Add the local hostname

The Ingress uses the hostname `assessment.local`. Add it to your hosts file:

**Linux / macOS:**

```bash
echo "127.0.0.1  assessment.local" | sudo tee -a /etc/hosts
```

**Windows (PowerShell as Administrator):**

```powershell
Add-Content -Path "C:\Windows\System32\drivers\etc\hosts" -Value "127.0.0.1  assessment.local"
```

### Step 3 — Bootstrap the cluster

Run the provided setup script. It will:

- Create a k3d cluster with 2 agent nodes
- Build both Docker images
- Import them into the cluster (no external registry needed)
- Apply all Kubernetes manifests
- Wait for everything to be healthy

```bash
chmod +x setup.sh
./setup.sh
```

> **Windows users:** Run the commands inside `setup.sh` manually in sequence, or use Git Bash / WSL2.

Expected output (tail):

```
[OK]    All deployments are ready!

════════════════════════════════════════════════════════
  Assessment Environment Ready!
════════════════════════════════════════════════════════

  Endpoints:
    Health   : http://assessment.local/healthz
    Readiness: http://assessment.local/readyz
    API      : http://assessment.local/api/data
    Stats    : http://assessment.local/api/stats
```

---

## 5. Verifying the Environment

```bash
# All pods should be Running
kubectl get pods -n assessment

# Quick smoke test
curl http://assessment.local/healthz
# → {"status":"ok","timestamp":"..."}

curl http://assessment.local/readyz
# → {"status":"ready","timestamp":"..."}

curl http://assessment.local/api/data
# → {"status":"success","reads":[...],"writes":[...],"timestamp":"..."}
```

**Arch Linux only** — if `curl` still fails after adding the hosts entry, fix the resolver order:

```bash
sudo sed -i 's/hosts: mymachines mdns_minimal \[NOTFOUND=return\] resolve files myhostname dns/hosts: mymachines files mdns_minimal resolve myhostname dns/' /etc/nsswitch.conf
```

This moves `files` before `mdns_minimal` so `/etc/hosts` is checked first.

Expected pod list:

```
NAME                          READY   STATUS    RESTARTS   AGE
mongo-xxxxxxxxx-xxxxx         1/1     Running   0          2m
app-python-xxxxxxxxx-xxxxx    1/1     Running   0          90s
app-nodejs-xxxxxxxxx-xxxxx    1/1     Running   0          90s
```

---

## 6. Running the Stress Test (Baseline)

Before making any changes, run the stress test to establish a baseline. **It is expected to fail at this point.**
You should see the system breaking at 10,000 virtual users

```bash
k6 run stress-test/stress-test.js
```

But it works fine at 100 concurrent users

```bash
k6 run --vus 100 --duration 30s stress-test/stress-test.js
```

To run against a different URL:

```bash
BASE_URL=http://assessment.local k6 run stress-test/stress-test.js
```

To enable verbose failure logging:

```bash
VERBOSE=true k6 run stress-test/stress-test.js
```

### Reading the Results

k6 outputs a summary table after each run. Key metrics to watch:

| Metric                    | What it means               | Target           |
| ------------------------- | --------------------------- | ---------------- |
| `http_req_duration` p(95) | 95th-percentile latency     | **< 2,000 ms**   |
| `http_req_duration` p(99) | 99th-percentile latency     | **< 5,000 ms**   |
| `http_req_failed`         | Fraction of failed requests | **< 1%**         |
| `error_rate`              | Custom error counter        | **< 1%**         |
| `http_reqs`               | Total requests completed    | Higher is better |

A ✓ next to a threshold means it passed. A ✗ means it failed.

---

## 7. Your Task - Optimisation Targets

With 100 IOPS capped on MongoDB, you cannot sustain 10,000 raw read-write cycles per second. The system collapses under load. Find out why, fix it, and make it pass the stress test at 10,000 VUs.
You must deploy any new infrastructure **inside the cluster** as a Kubernetes Deployment + Service.

You have four layers to investigate:

**Application** — the app code and how it talks to MongoDB

**Infrastructure** — how the app is deployed inside the cluster

**Database** — how MongoDB is being used (within the hard constraints)

**Container** — how the images are built and run

Where you start and what you change is up to you. Diagnose first, then optimise.

### 7.1 Choose Your Application

Pick **one** application to optimise (Python or Node.js). Both are deployed; only the active one (default: Python) receives ingress traffic.

To switch to Node.js, edit `k8s/app/services.yaml`:

```yaml
# Change:
name: app-python
# To:
name: app-nodejs
```

Then apply: `kubectl apply -f k8s/app/services.yaml`

## 8. Pass Criteria

Your submission passes if a full `k6 run stress-test/stress-test.js` run **at 10,000 VUs** produces:

| Threshold                 | Required Value |
| ------------------------- | -------------- |
| `http_req_duration` p(95) | ≤ 2,000 ms     |
| `http_req_duration` p(99) | ≤ 5,000 ms     |
| `http_req_failed` rate    | < 1%           |
| `error_rate`              | < 1%           |

All four thresholds must pass simultaneously (k6 will print ✓ or ✗ for each).

---

## 9. Submission Checklist

- [ ] All modified files committed to git
- [ ] A `SOLUTION.md` file at the root of the repo explaining:
  - What changes you made and **why**
  - What bottlenecks you identified and how you diagnosed them
  - Trade-offs you considered but did not implement
  - k6 summary output pasted (showing all ✓ thresholds)
- [ ] All changes deployable via `kubectl apply` (no manual steps not documented)
- [ ] `setup.sh` still works on a fresh cluster

---

## 10. Hints (Read Only When Stuck)

### Decoupling with Pub/Sub

One approach worth considering is decoupling the write path using a message queue. Rather than every request writing directly and synchronously to MongoDB, writes can be published to a queue and consumed asynchronously — smoothing out the burst pressure on the database.

Google Cloud Pub/Sub is one such system. For local development inside the cluster, Google provides an official Pub/Sub emulator image that behaves identically to the real service and can be deployed in Kubernetes:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pubsub-emulator
  namespace: assessment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: pubsub-emulator
  template:
    metadata:
      labels:
        app: pubsub-emulator
    spec:
      containers:
        - name: pubsub-emulator
          image: gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators
          command:
            - gcloud
            - beta
            - emulators
            - pubsub
            - start
            - --host-port=0.0.0.0:8085
            - --project=assessment-project
          ports:
            - containerPort: 8085
          resources:
            limits:
              memory: "256Mi"
              cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: pubsub-emulator
  namespace: assessment
spec:
  selector:
    app: pubsub-emulator
  ports:
    - port: 8085
      targetPort: 8085
```

To point your application at the emulator, set the environment variable:

```
PUBSUB_EMULATOR_HOST=pubsub-emulator:8085
```

The Google Cloud Pub/Sub client libraries for both [Python](https://cloud.google.com/python/docs/reference/pubsub/latest) and [Node.js](https://cloud.google.com/nodejs/docs/reference/pubsub/latest) will automatically detect this variable and route all calls to the emulator instead of the real service — no code changes needed to switch between local and production.

How you integrate it, what you queue, and how you consume it is your decision to make.

## Appendix — Useful Commands

```bash
# Watch pods in real time
kubectl get pods -n assessment -w

# View application logs
kubectl logs -n assessment deploy/app-python -f
kubectl logs -n assessment deploy/app-nodejs -f
kubectl logs -n assessment deploy/mongo -f

# Resource usage (requires metrics-server)
kubectl top pods -n assessment
kubectl top nodes

# Scale the app manually (without HPA)
kubectl scale deployment app-python -n assessment --replicas=5

# Exec into a running pod
kubectl exec -it -n assessment deploy/app-python -- bash
kubectl exec -it -n assessment deploy/mongo -- mongosh

# Re-import image after rebuilding
docker build -t assessment/app-python:latest ./app-python/
k3d image import assessment/app-python:latest --cluster assessment
kubectl rollout restart deployment/app-python -n assessment

# Delete and recreate the cluster (full reset)
k3d cluster delete assessment
./setup.sh

# Run a quick load sanity check (100 VUs, 30 s) before the full test
k6 run --vus 100 --duration 30s stress-test/stress-test.js
```

---

_Good luck. The system is broken by design — your job is to make it unbreakable._
