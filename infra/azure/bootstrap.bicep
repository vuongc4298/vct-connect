targetScope = 'resourceGroup'

@description('Only the approved Southeast Asia development target is supported.')
@allowed(['southeastasia'])
param location string = 'southeastasia'

@description('Immutable GitHub OIDC subject allowed to deploy from main.')
@allowed(['repo:vuongc4298@156062555/vct-connect@1393991860:ref:refs/heads/main'])
param githubSubject string = 'repo:vuongc4298@156062555/vct-connect@1393991860:ref:refs/heads/main'

@description('Object ID of the operator who will seed the two Key Vault secrets.')
param operatorObjectId string

@allowed(['vct-connect-standard'])
param serviceBusNamespace string = 'vct-connect-standard'
@allowed(['vct-analyse'])
param serviceBusQueue string = 'vct-analyse'
@allowed(['Basic', 'Standard', 'Premium'])
param registrySku string = 'Basic'

var suffix = uniqueString(resourceGroup().id)
var registryName = 'vctconnect${suffix}'
var vaultName = 'vctconn-${suffix}'

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  sku: { name: registrySku }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: vaultName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enabledForTemplateDeployment: true
    publicNetworkAccess: 'Enabled'
    softDeleteRetentionInDays: 30
  }
}

resource runtimeIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'vct-connect-dev-runtime'
  location: location
}

resource deployIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'vct-connect-dev-deploy'
  location: location
}

resource githubMain 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: deployIdentity
  name: 'github-main-immutable'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: githubSubject
    audiences: ['api://AzureADTokenExchange']
  }
}

resource existingQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' existing = {
  name: '${serviceBusNamespace}/${serviceBusQueue}'
}

resource runtimeAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, runtimeIdentity.id, 'AcrPull')
  scope: registry
  properties: {
    principalId: runtimeIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

resource deployAcrPush 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, deployIdentity.id, 'AcrPush')
  scope: registry
  properties: {
    principalId: deployIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8311e382-0749-4cb8-b61a-304f252e45ec')
  }
}

resource runtimeVaultReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, runtimeIdentity.id, 'Key Vault Secrets User')
  scope: vault
  properties: {
    principalId: runtimeIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  }
}

resource deployVaultReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, deployIdentity.id, 'Key Vault Secrets User')
  scope: vault
  properties: {
    principalId: deployIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  }
}

resource operatorVaultWriter 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, operatorObjectId, 'Key Vault Secrets Officer')
  scope: vault
  properties: {
    principalId: operatorObjectId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
  }
}

resource runtimeQueueSender 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(existingQueue.id, runtimeIdentity.id, 'Service Bus Sender')
  scope: existingQueue
  properties: {
    principalId: runtimeIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39')
  }
}

resource runtimeQueueReceiver 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(existingQueue.id, runtimeIdentity.id, 'Service Bus Receiver')
  scope: existingQueue
  properties: {
    principalId: runtimeIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0')
  }
}

resource deployContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, deployIdentity.id, 'Contributor')
  scope: resourceGroup()
  properties: {
    principalId: deployIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c')
  }
}

output registryLoginServer string = registry.properties.loginServer
output vaultName string = vault.name
output deployClientId string = deployIdentity.properties.clientId
output runtimeIdentityId string = runtimeIdentity.id
