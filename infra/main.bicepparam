using './main.bicep'

// Override these per environment as needed.
param namePrefix    = 'uapexplorer'
param location      = 'eastus'

// Workload sizing (defaults are fine for small dev/demo)
param backendCpu    = '0.5'
param backendMemory = '1Gi'
param frontendCpu   = '0.25'
param frontendMemory = '0.5Gi'
// Backend kept warm (minReplicas=1) to avoid 10-30s cold-start latency on
// first request after idle. Frontend cold start is short, so leave at 0.
param backendMinReplicas  = 1
param frontendMinReplicas = 0
param maxReplicas   = 2

// Image refs left at defaults (placeholders) — deploy.ps1 will rebuild and
// update them. Secrets are *not* hard-coded here: deploy.ps1 reads them
// from backend/.env at deploy time and passes them in via --parameters.
