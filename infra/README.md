# UAP Explorer — Azure Container Apps deployment

This folder contains the **reusable Bicep template** and a **PowerShell wrapper**
that deploy the full UAP Explorer stack to Azure Container Apps.

## Files

| File | Purpose |
|---|---|
| [main.bicep](main.bicep) | Provisions Log Analytics, ACR, user-assigned managed identity, Container Apps Environment, and two Container Apps (backend + frontend). |
| [main.bicepparam](main.bicepparam) | Default parameter overrides (region, sizing). Secret values are **not** stored here — they come from `backend/.env` at deploy time. |
| [deploy.ps1](deploy.ps1) | End-to-end orchestrator: provisions infra, reads `backend/.env`, builds both images in ACR (no local Docker), and rolls the apps to the new image tags. Idempotent and re-runnable. |

## Architecture

```
                ┌───────────────────────────────────────┐
                │   Container Apps Environment          │
                │                                       │
   public ──►   │   ┌───────────────┐   internal HTTP   │
                │   │ ca-<prefix>-  │ ─────────────►    │
                │   │  frontend     │     ┌──────────┐  │
                │   │ (nginx:8080)  │     │ ca-<prefix>-│
                │   │  serves SPA + │     │  backend │  │
                │   │  proxies /api │     │ (FastAPI │  │
                │   └───────────────┘     │  :8000)  │  │
                │                         └──────────┘  │
                └───────────────────────────────────────┘
                              │ pull
                              ▼
                ┌─────────────────────────────┐
                │ Azure Container Registry    │
                │ acr<prefix><unique>         │
                └─────────────────────────────┘

      Backend reads from existing Azure resources via key auth:
        • Storage account (Blob)         • AI Search
        • Azure OpenAI                   • Document Intelligence
```

The frontend is the only externally reachable app. Its nginx layer reverse-
proxies `/api` and `/health` to the backend's internal Container Apps FQDN, so
the SPA always talks to its own origin (no CORS surprises).

## Prerequisites

- Azure CLI (`az`) signed in: `az login`
- A populated [backend/.env](../backend/.env) with the same Azure secrets the
  app uses locally (storage connection string, AI Search admin key, OpenAI key,
  Document Intelligence key, ADMIN_PASSWORD, etc.).
- Permission to create resources in subscription
  `9c245e09-df78-44f6-9253-a2a176e6f147` and resource group
  `rgJabAI-UAPExplorer`.

> **Local Docker is NOT required.** Image builds run inside Azure via
> `az acr build`.

## Usage

```powershell
# Full deploy (infra + build + roll)
pwsh ./infra/deploy.ps1

# Just rebuild images and update revisions
pwsh ./infra/deploy.ps1 -SkipInfra

# Only re-apply infra/secrets, no rebuild
pwsh ./infra/deploy.ps1 -SkipBuild
```

The script prints the public URL when done. Tail logs with:

```powershell
az containerapp logs show -n ca-uapexplorer-backend -g rgJabAI-UAPExplorer --follow
az containerapp logs show -n ca-uapexplorer-frontend -g rgJabAI-UAPExplorer --follow
```

## Notes on ports

The local dev backend runs on **8001** for convenience. Inside the container
the backend listens on **8000** (matches the existing `backend/Dockerfile`),
and Container Apps ingress targets that port. The local port and the ACA
target port are unrelated.
