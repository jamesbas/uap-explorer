// =====================================================================
// UAP Explorer — Azure Container Apps deployment
// ---------------------------------------------------------------------
// Provisions:
//   • Log Analytics workspace
//   • Azure Container Registry (ACR)
//   • User-assigned managed identity (with AcrPull on the ACR)
//   • Container Apps Environment
//   • Backend Container App  (internal ingress, port 8000)
//   • Frontend Container App (external ingress, port 8080, nginx → backend)
//
// First deploy uses a placeholder public image so resources can be created
// before the real images exist in ACR. The deploy.ps1 script then runs
// `az acr build` and updates each app with the real image tag.
// =====================================================================

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Short name used as a prefix in resource names. Lowercase, 2-12 chars.')
@minLength(2)
@maxLength(12)
param namePrefix string = 'uapexplorer'

@description('Image reference for the backend container. Use the placeholder default for the first deploy; the deploy script will update it after building the real image.')
param backendImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Image reference for the frontend container. Use the placeholder default for the first deploy; the deploy script will update it after building the real image.')
param frontendImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

// ---- Backend secrets (passed in by the deploy script from backend/.env) ----
@secure()
@description('Admin password for the UAP Explorer admin UI / token endpoint.')
param adminPassword string = ''

@description('Azure Storage account that holds source PDFs/images.')
param azureStorageAccount string = ''

@description('Blob container name (typically uap-files).')
param azureStorageContainer string = 'uap-files'

@secure()
@description('Storage account connection string used by the backend.')
param azureStorageConnectionString string = ''

@description('Azure AI Search endpoint URL.')
param azureSearchEndpoint string = ''

@secure()
@description('Azure AI Search admin key.')
param azureSearchAdminKey string = ''

@description('Azure AI Search index name.')
param azureSearchIndexName string = 'uap-explorer-chunks'

@description('Azure OpenAI endpoint URL.')
param azureOpenAIEndpoint string = ''

@secure()
@description('Azure OpenAI API key.')
param azureOpenAIKey string = ''

@description('Azure OpenAI chat deployment name.')
param azureOpenAIDeployment string = 'gpt-5.2-chat'

@description('Azure OpenAI embedding deployment name.')
param azureOpenAIEmbeddingDeployment string = 'text-embedding-3-large'

@description('Azure OpenAI API version.')
param azureOpenAIApiVersion string = '2024-12-01-preview'

@description('Azure Document Intelligence endpoint URL.')
param azureDocIntelligenceEndpoint string = ''

@secure()
@description('Azure Document Intelligence API key.')
param azureDocIntelligenceKey string = ''

@description('Container CPU cores (per replica).')
param backendCpu string = '0.5'
@description('Container memory (per replica).')
param backendMemory string = '1Gi'
@description('Frontend CPU cores (per replica).')
param frontendCpu string = '0.25'
@description('Frontend memory (per replica).')
param frontendMemory string = '0.5Gi'

@description('Backend min replicas. Set to 1 to keep a warm replica and avoid cold-start latency.')
param backendMinReplicas int = 1
@description('Frontend min replicas. Frontend cold start is short, so 0 is usually fine.')
param frontendMinReplicas int = 0
@description('Max replicas (applies to both apps).')
param maxReplicas int = 2

// ---------------------------------------------------------------------
// Resource names
// ---------------------------------------------------------------------
var unique = uniqueString(resourceGroup().id, namePrefix)
var acrName = toLower('acr${namePrefix}${unique}')
var logName = 'log-${namePrefix}'
var envName = 'cae-${namePrefix}'
var uamiName = 'id-${namePrefix}'
var backendAppName = 'ca-${namePrefix}-backend'
var frontendAppName = 'ca-${namePrefix}-frontend'
// Storage account name: 3-24 chars, lowercase letters/digits only.
var appDataStorageAccountName = toLower(substring('st${namePrefix}${unique}', 0, 24))
var appDataShareName = 'appdata'
var appDataEnvStorageName = 'appdata'

// ---------------------------------------------------------------------
// Log Analytics workspace
// ---------------------------------------------------------------------
resource log 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ---------------------------------------------------------------------
// User-assigned managed identity (for ACR pull and future MI-based access)
// ---------------------------------------------------------------------
resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: uamiName
  location: location
}

// ---------------------------------------------------------------------
// Azure Container Registry
// ---------------------------------------------------------------------
resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: acrName
  location: location
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
  }
}

// AcrPull role on the ACR for the UAMI
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, uami.id, acrPullRoleId)
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
  }
}

// ---------------------------------------------------------------------
// Storage account + Azure Files share for persistent backend data
// (mounted into the backend Container App at /app/data so generated
// reports, summaries, extracted JSON, and ingestion status survive
// container restarts, revision updates, and replica churn).
// ---------------------------------------------------------------------
resource appDataStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: appDataStorageAccountName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource appDataFileService 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: appDataStorage
  name: 'default'
}

resource appDataShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: appDataFileService
  name: appDataShareName
  properties: {
    accessTier: 'TransactionOptimized'
    shareQuota: 100
  }
}

// ---------------------------------------------------------------------
// Container Apps Environment
// ---------------------------------------------------------------------
resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: envName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: log.properties.customerId
        sharedKey: log.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// Register the Azure Files share with the Container Apps Environment so
// container apps in this env can mount it as a volume.
resource envAppDataStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: env
  name: appDataEnvStorageName
  properties: {
    azureFile: {
      accountName: appDataStorage.name
      accountKey: appDataStorage.listKeys().keys[0].value
      shareName: appDataShare.name
      accessMode: 'ReadWrite'
    }
  }
}

// ---------------------------------------------------------------------
// Backend Container App  (internal ingress; reachable from frontend over the
// Container Apps environment internal network)
// ---------------------------------------------------------------------
resource backendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: backendAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uami.id}': {}
    }
  }
  properties: {
    environmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false
        targetPort: 8000
        transport: 'auto'
        // Allow plain HTTP from the frontend nginx over the internal FQDN
        // so it doesn't get a 301 redirect to https (which the proxy would
        // forward verbatim and break the call).
        allowInsecure: true
      }
      registries: [
        {
          server: '${acr.name}.azurecr.io'
          identity: uami.id
        }
      ]
      secrets: [
        { name: 'admin-password', value: adminPassword }
        { name: 'storage-connection-string', value: azureStorageConnectionString }
        { name: 'search-admin-key', value: azureSearchAdminKey }
        { name: 'openai-key', value: azureOpenAIKey }
        { name: 'docintel-key', value: azureDocIntelligenceKey }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: backendImage
          resources: {
            cpu: json(backendCpu)
            memory: backendMemory
          }
          env: [
            { name: 'APP_ENV', value: 'production' }
            { name: 'BACKEND_HOST', value: '0.0.0.0' }
            { name: 'BACKEND_PORT', value: '8000' }
            // FRONTEND_URL is set by the deploy script after the frontend FQDN is known
            { name: 'FRONTEND_URL', value: '*' }
            { name: 'UAP_CSV_PATH', value: '/app/data/source/uap-csv.csv' }
            { name: 'UAP_FILE_ROOT', value: '/app/ufo_release_01_files' }
            { name: 'UAP_PROCESSED_ROOT', value: '/app/data/processed' }
            { name: 'AZURE_AUTH_MODE', value: 'key' }

            { name: 'ADMIN_PASSWORD', secretRef: 'admin-password' }

            { name: 'AZURE_STORAGE_ACCOUNT', value: azureStorageAccount }
            { name: 'AZURE_STORAGE_CONTAINER', value: azureStorageContainer }
            { name: 'AZURE_STORAGE_CONNECTION_STRING', secretRef: 'storage-connection-string' }

            { name: 'AZURE_SEARCH_ENDPOINT', value: azureSearchEndpoint }
            { name: 'AZURE_SEARCH_INDEX_NAME', value: azureSearchIndexName }
            { name: 'AZURE_SEARCH_ADMIN_KEY', secretRef: 'search-admin-key' }

            { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAIEndpoint }
            { name: 'AZURE_OPENAI_API_KEY', secretRef: 'openai-key' }
            { name: 'AZURE_OPENAI_DEPLOYMENT', value: azureOpenAIDeployment }
            { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: azureOpenAIEmbeddingDeployment }
            { name: 'AZURE_OPENAI_API_VERSION', value: azureOpenAIApiVersion }

            { name: 'AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT', value: azureDocIntelligenceEndpoint }
            { name: 'AZURE_DOCUMENT_INTELLIGENCE_KEY', secretRef: 'docintel-key' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8000 }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: { path: '/health', port: 8000 }
              initialDelaySeconds: 5
              periodSeconds: 15
            }
          ]
          volumeMounts: [
            {
              volumeName: 'appdata'
              mountPath: '/app/data/processed'
            }
          ]
        }
      ]
      volumes: [
        {
          name: 'appdata'
          storageType: 'AzureFile'
          storageName: appDataEnvStorageName
        }
      ]
      scale: {
        minReplicas: backendMinReplicas
        maxReplicas: maxReplicas
      }
    }
  }
  dependsOn: [
    acrPull
    envAppDataStorage
  ]
}

// ---------------------------------------------------------------------
// Frontend Container App (external ingress; nginx serves the SPA and
// reverse-proxies /api and /health to the backend internal FQDN)
// ---------------------------------------------------------------------
resource frontendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: frontendAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${uami.id}': {}
    }
  }
  properties: {
    environmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: '${acr.name}.azurecr.io'
          identity: uami.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: frontendImage
          resources: {
            cpu: json(frontendCpu)
            memory: frontendMemory
          }
          env: [
            { name: 'PORT', value: '8080' }
            // Backend internal FQDN reachable from inside the env over plain HTTP on 8000.
            { name: 'BACKEND_URL', value: 'http://${backendApp.properties.configuration.ingress.fqdn}' }
          ]
        }
      ]
      scale: {
        minReplicas: frontendMinReplicas
        maxReplicas: maxReplicas
      }
    }
  }
  dependsOn: [
    acrPull
  ]
}

// ---------------------------------------------------------------------
// Outputs (consumed by deploy.ps1)
// ---------------------------------------------------------------------
output acrName string = acr.name
output acrLoginServer string = acr.properties.loginServer
output backendAppName string = backendApp.name
output frontendAppName string = frontendApp.name
output backendInternalFqdn string = backendApp.properties.configuration.ingress.fqdn
output frontendUrl string = 'https://${frontendApp.properties.configuration.ingress.fqdn}'
output uamiId string = uami.id
output uamiPrincipalId string = uami.properties.principalId
output appDataStorageAccount string = appDataStorage.name
output appDataShareName string = appDataShare.name
