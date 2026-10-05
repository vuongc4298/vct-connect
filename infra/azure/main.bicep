targetScope = 'resourceGroup'

@allowed(['southeastasia'])
param location string = 'southeastasia'
@description('Registry digest, including sha256:, of the backend image.')
param backendImageDigest string
@description('Registry digest, including sha256:, of the web image.')
param webImageDigest string
@description('Enable queue processing only after the migration Job succeeds.')
param enableProcessing bool = false
@description('Opt-in cached public HTML rendering. Unavailable Chromium sandbox retains HTTP evidence.')
param publicBrowserFallback bool = false
@description('Opt in to paid reports only after migration and a report queue audit.')
param enableTextReports bool = false
@description('Non-secret worker report settings; backend validation enforces limits. Budget is a lifetime ledger cap.')
param textReportSettings object = {
  YESCALE_CHAT_ENDPOINT: 'https://api.yescale.io/v1/chat/completions'
  YESCALE_MODEL: 'deepseek-v4.1-flash'
  YESCALE_MODEL_VERSION: 'operator-observed-20261005'
  YESCALE_EXPECTED_RETURNED_MODEL: 'deepseek-v4-1-flash-260910'
  YESCALE_THINKING: 'disabled'
  TEXT_REPORT_BUDGET_USD: '0.09'
  TEXT_REPORT_CALL_CEILING_USD: '0.10'
  YESCALE_INPUT_USD_PER_MILLION: '0.15'
  YESCALE_OUTPUT_USD_PER_MILLION: '0.60'
  TEXT_REPORT_MAX_INPUT_BYTES: '24000'
  TEXT_REPORT_MAX_OUTPUT_TOKENS: '2400'
  TEXT_REPORT_DEADLINE_SECONDS: '120'
}
param registryName string
param vaultName string
param clerkPublishableKey string
param clerkIssuer string
@allowed(['vct-connect-standard'])
param serviceBusNamespace string = 'vct-connect-standard'
@allowed(['vct-analyse'])
param serviceBusQueue string = 'vct-analyse'
param runtimeIdentityName string = 'vct-connect-dev-runtime'

@minValue(32)
@maxValue(1024)
param postgresStorageGiB int = 32
@allowed(['Standard_B1ms', 'Standard_B2s', 'Standard_D2s_v3'])
param postgresSku string = 'Standard_B1ms'
@allowed(['Burstable', 'GeneralPurpose'])
param postgresTier string = 'Burstable'
@minValue(1)
@maxValue(10)
param workerMaxExecutions int = 3
@minValue(1)
@maxValue(10)
param apiMaxReplicas int = 2
@minValue(1)
@maxValue(10)
param webMaxReplicas int = 2
@minValue(30)
@maxValue(300)
param jobPollingSeconds int = 30
@description('Temporary per-browser guest fixture submissions per admission window.')
@minValue(1)
@maxValue(10000)
param guestBrowserLimit int = 3
@description('Temporary shared guest fixture submissions per admission window.')
@minValue(1)
@maxValue(1000000)
param guestGlobalLimit int = 100
@description('Temporary customer fixture submissions per admission window.')
@minValue(1)
@maxValue(100000)
param customerLimit int = 20
@description('Admission window duration in seconds.')
@minValue(60)
@maxValue(31536000)
param admissionWindowSeconds int = 86400

var suffix = uniqueString(resourceGroup().id)
var postgresName = 'vct-connect-${suffix}'
var webName = 'vct-connect-dev-web'
var apiName = 'vct-connect-dev-api'
var dispatcherName = 'vct-connect-dev-dispatcher'
var jobName = 'vct-connect-dev-analysis'
var backendImage = '${registryName}.azurecr.io/vct-backend@${backendImageDigest}'
var webImage = '${registryName}.azurecr.io/vct-web@${webImageDigest}'
var databaseSecretUrl = '${vault.properties.vaultUri}secrets/database-url'
var clerkSecretUrl = '${vault.properties.vaultUri}secrets/clerk-secret-key'
var workerSecrets = concat([
  { name: 'database-url', keyVaultUrl: databaseSecretUrl, identity: runtimeIdentity.id }
], enableTextReports ? [
  { name: 'yescale-api-key', keyVaultUrl: '${vault.properties.vaultUri}secrets/yescale-api-key', identity: runtimeIdentity.id }
] : [])
var configuredReportEnvironment = [for setting in items(textReportSettings): { name: setting.key, value: string(setting.value) }]
var reportEnvironment = concat([
  { name: 'TEXT_REPORT_ENABLED', value: string(enableTextReports) }
], enableTextReports ? concat([
  { name: 'YESCALE_API_KEY', secretRef: 'yescale-api-key' }
], configuredReportEnvironment) : [])

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}
resource vault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: vaultName
}
resource runtimeIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: runtimeIdentityName
}
resource existingQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' existing = {
  name: '${serviceBusNamespace}/${serviceBusQueue}'
}
resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' existing = {
  name: postgresName
}

resource network 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: 'vct-connect-dev-vnet'
  location: location
  properties: { addressSpace: { addressPrefixes: ['10.48.0.0/16'] } }
}
resource appsSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-11-01' = {
  parent: network
  name: 'container-apps'
  properties: {
    addressPrefix: '10.48.0.0/23'
    delegations: [{ name: 'container-apps', properties: { serviceName: 'Microsoft.App/environments' } }]
  }
}
resource postgresSubnet 'Microsoft.Network/virtualNetworks/subnets@2023-11-01' = {
  parent: network
  name: 'postgres'
  properties: {
    addressPrefix: '10.48.2.0/28'
    delegations: [{ name: 'postgres', properties: { serviceName: 'Microsoft.DBforPostgreSQL/flexibleServers' } }]
  }
}
resource privateDns 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'private.postgres.database.azure.com'
  location: 'global'
}
resource privateDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: privateDns
  name: 'vct-connect-dev-vnet'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: { id: network.id }
  }
}

module postgres './postgres.bicep' = {
  name: 'postgres-dev'
  params: {
    location: location
    serverName: postgresName
    subnetId: postgresSubnet.id
    privateDnsZoneId: privateDns.id
    vaultName: vault.name
    administratorLogin: 'vctadmin'
    administratorPassword: vault.getSecret('postgres-admin-password')
    postgresSku: postgresSku
    postgresTier: postgresTier
    postgresStorageGiB: postgresStorageGiB
  }
  dependsOn: [privateDnsLink]
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'vct-connect-dev-logs'
  location: location
  properties: { retentionInDays: 30, sku: { name: 'PerGB2018' } }
}
resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'vct-connect-dev-env'
  location: location
  properties: {
    vnetConfiguration: { infrastructureSubnetId: appsSubnet.id, internal: false }
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
    workloadProfiles: [{ name: 'Consumption', workloadProfileType: 'Consumption' }]
  }
}

resource postgresDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'vct-connect-dev-diagnostics'
  scope: postgresServer
  properties: {
    workspaceId: logs.id
    logs: [{ categoryGroup: 'allLogs', enabled: true }]
    metrics: [{ category: 'AllMetrics', enabled: true }]
  }
  dependsOn: [postgres]
}

resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: apiName
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${runtimeIdentity.id}': {} } }
  properties: {
    environmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: false, targetPort: 8000, transport: 'http', allowInsecure: false }
      registries: [{ server: registry.properties.loginServer, identity: runtimeIdentity.id }]
      secrets: [
        { name: 'database-url', keyVaultUrl: databaseSecretUrl, identity: runtimeIdentity.id }
        { name: 'clerk-secret-key', keyVaultUrl: clerkSecretUrl, identity: runtimeIdentity.id }
      ]
    }
    template: {
      containers: [{
        name: 'api'
        image: backendImage
        env: [
          { name: 'DATABASE_URL', secretRef: 'database-url' }
          { name: 'CLERK_SECRET_KEY', secretRef: 'clerk-secret-key' }
          { name: 'CLERK_ISSUER', value: clerkIssuer }
          { name: 'CLERK_AUTHORIZED_PARTIES', value: 'https://${webName}.${environment.properties.defaultDomain},chrome-extension://klggcepemjjbphjclpiabgpfgdbgiljj' }
          { name: 'CLERK_AUDIENCE', value: 'vct-connect-api' }
          { name: 'DEVELOPER_MODE', value: 'false' }
          { name: 'API_RUNTIME', value: 'azure' }
          { name: 'QUEUE_TRANSPORT', value: 'azure' }
          { name: 'GUEST_BROWSER_LIMIT', value: string(guestBrowserLimit) }
          { name: 'GUEST_GLOBAL_LIMIT', value: string(guestGlobalLimit) }
          { name: 'CUSTOMER_LIMIT', value: string(customerLimit) }
          { name: 'ADMISSION_WINDOW_SECONDS', value: string(admissionWindowSeconds) }
          { name: 'AZURE_SERVICE_BUS_NAMESPACE', value: serviceBusNamespace }
          { name: 'AZURE_SERVICE_BUS_QUEUE', value: serviceBusQueue }
          { name: 'AZURE_CLIENT_ID', value: runtimeIdentity.properties.clientId }
        ]
        resources: { cpu: json('0.5'), memory: '1Gi' }
      }]
      scale: { minReplicas: 1, maxReplicas: apiMaxReplicas }
    }
  }
  dependsOn: [postgres]
}

resource web 'Microsoft.App/containerApps@2024-03-01' = {
  name: webName
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${runtimeIdentity.id}': {} } }
  properties: {
    environmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: true, targetPort: 3000, transport: 'http', allowInsecure: false }
      registries: [{ server: registry.properties.loginServer, identity: runtimeIdentity.id }]
    }
    template: {
      containers: [{
        name: 'web'
        image: webImage
        env: [
          { name: 'API_INTERNAL_ORIGIN', value: 'http://${apiName}' }
          { name: 'NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY', value: clerkPublishableKey }
        ]
        resources: { cpu: json('0.5'), memory: '1Gi' }
      }]
      scale: { minReplicas: 1, maxReplicas: webMaxReplicas }
    }
  }
  dependsOn: [api]
}

resource dispatcher 'Microsoft.App/containerApps@2024-03-01' = if (enableProcessing) {
  name: dispatcherName
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${runtimeIdentity.id}': {} } }
  properties: {
    environmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      registries: [{ server: registry.properties.loginServer, identity: runtimeIdentity.id }]
      secrets: workerSecrets
    }
    template: {
      containers: [{
        name: 'dispatcher'
        image: backendImage
        command: ['python', '-m', 'backend.worker.main']
        env: concat([
          { name: 'DATABASE_URL', secretRef: 'database-url' }
          { name: 'QUEUE_TRANSPORT', value: 'azure' }
          { name: 'AZURE_SERVICE_BUS_NAMESPACE', value: serviceBusNamespace }
          { name: 'AZURE_SERVICE_BUS_QUEUE', value: serviceBusQueue }
          { name: 'WORKER_MODE', value: 'dispatcher' }
          { name: 'API_RUNTIME', value: 'worker' }
          { name: 'AZURE_CLIENT_ID', value: runtimeIdentity.properties.clientId }
        ], reportEnvironment)
        resources: { cpu: json('0.5'), memory: '1Gi' }
      }]
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
  dependsOn: [postgres]
}

resource analysisJob 'Microsoft.App/jobs@2025-01-01' = if (enableProcessing) {
  name: jobName
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${runtimeIdentity.id}': {} } }
  properties: {
    environmentId: environment.id
    configuration: {
      triggerType: 'Event'
      replicaRetryLimit: 1
      replicaTimeout: 900
      registries: [{ server: registry.properties.loginServer, identity: runtimeIdentity.id }]
      secrets: workerSecrets
      eventTriggerConfig: {
        parallelism: 1
        replicaCompletionCount: 1
        scale: {
          minExecutions: 0
          maxExecutions: workerMaxExecutions
          pollingInterval: jobPollingSeconds
          rules: [{
            name: 'analysis-queue'
            type: 'azure-servicebus'
            identity: runtimeIdentity.id
            metadata: {
              namespace: serviceBusNamespace
              queueName: serviceBusQueue
              messageCount: '1'
            }
          }]
        }
      }
    }
    template: {
      containers: [{
        name: 'analysis'
        image: backendImage
        command: ['python', '-m', 'backend.worker.main']
        env: concat([
          { name: 'DATABASE_URL', secretRef: 'database-url' }
          { name: 'QUEUE_TRANSPORT', value: 'azure' }
          { name: 'AZURE_SERVICE_BUS_NAMESPACE', value: serviceBusNamespace }
          { name: 'AZURE_SERVICE_BUS_QUEUE', value: serviceBusQueue }
          { name: 'WORKER_MODE', value: 'job' }
          { name: 'PUBLIC_BROWSER_FALLBACK', value: string(publicBrowserFallback) }
          { name: 'API_RUNTIME', value: 'worker' }
          { name: 'PROCESSING_LEASE_SECONDS', value: '780' }
          { name: 'AZURE_LOCK_RENEWAL_SECONDS', value: '780' }
          { name: 'AZURE_CLIENT_ID', value: runtimeIdentity.properties.clientId }
        ], reportEnvironment)
        resources: { cpu: json('0.5'), memory: '1Gi' }
      }]
    }
  }
  dependsOn: [postgres]
}

resource migrationJob 'Microsoft.App/jobs@2025-01-01' = {
  name: 'vct-connect-dev-migrate'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${runtimeIdentity.id}': {} } }
  properties: {
    environmentId: environment.id
    configuration: {
      triggerType: 'Manual'
      replicaRetryLimit: 0
      replicaTimeout: 600
      manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
      registries: [{ server: registry.properties.loginServer, identity: runtimeIdentity.id }]
      secrets: [{ name: 'database-url', keyVaultUrl: databaseSecretUrl, identity: runtimeIdentity.id }]
    }
    template: {
      containers: [{
        name: 'migrate'
        image: backendImage
        command: ['python', '-m', 'backend.app.migrations', 'apply']
        env: [{ name: 'DATABASE_URL', secretRef: 'database-url' }]
        resources: { cpu: json('0.5'), memory: '1Gi' }
      }]
    }
  }
  dependsOn: [postgres]
}

output webUrl string = 'https://${webName}.${environment.properties.defaultDomain}'
output apiName string = api.name
output dispatcherName string = dispatcherName
output analysisJobName string = jobName
output migrationJobName string = migrationJob.name
output postgresServerFqdn string = postgres.outputs.serverFqdn
output serviceBusQueueId string = existingQueue.id
