param location string
param serverName string
param subnetId string
param privateDnsZoneId string
param vaultName string
param administratorLogin string
@secure()
param administratorPassword string
param postgresSku string
param postgresTier string
param postgresStorageGiB int

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: serverName
  location: location
  sku: {
    name: postgresSku
    tier: postgresTier
  }
  properties: {
    version: '16'
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorPassword
    storage: { storageSizeGB: postgresStorageGiB }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    network: {
      delegatedSubnetResourceId: subnetId
      privateDnsZoneArmResourceId: privateDnsZoneId
      publicNetworkAccess: 'Disabled'
    }
    highAvailability: { mode: 'Disabled' }
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: server
  name: 'vct'
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: vaultName
}

resource databaseUrl 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'database-url'
  properties: {
    value: 'postgresql://${administratorLogin}:${uriComponent(administratorPassword)}@${server.properties.fullyQualifiedDomainName}:5432/vct?sslmode=require'
  }
  dependsOn: [database]
}

output serverFqdn string = server.properties.fullyQualifiedDomainName
