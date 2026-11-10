// Mirrors modules/foundation (the Log Analytics part). Resource groups are created in main.bicep,
// because Bicep creates them at subscription scope.

param prefix string
param location string
param tags object
param retentionInDays int = 30

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${prefix}-avd'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: retentionInDays
  }
}

output id string = workspace.id
output name string = workspace.name
