// Parameters for bicep/main.bicep, read from the same answers file Terraform uses.
// ./nerdio init writes environments/example/01-platform/setup.auto.tfvars.json (gitignored);
// this file maps it 1:1, so the schema, the chat and the Actions form drive both engines.
// For another environment, copy this folder and change the path below (Bicep can't take a
// variable in a file path).

using '../../main.bicep'

var answers = any(loadJsonContent('../../../environments/example/01-platform/setup.auto.tfvars.json'))

param prefix = answers.prefix
param control_plane_location = answers.?control_plane_location ?? 'eastus2'
param cloud = answers.?cloud ?? 'public'
param tags = answers.?tags ?? {}
param resource_groups = answers.resource_groups
param existing_resource_groups = answers.?existing_resource_groups ?? []
param existing_private_dns_zone_ids = answers.?existing_private_dns_zone_ids ?? {}
param extra_private_dns_zones = answers.?extra_private_dns_zones ?? []
param regions = answers.regions
param image_gallery = answers.?image_gallery
param enable_resource_locks = answers.?enable_resource_locks ?? false
