// Parameters for bicep/identity.bicep, from the same answers file as Terraform (see platform.bicepparam).
// Add the Nerdio hostname once it exists:
//   az deployment sub create ... --parameters bicep/environments/example/identity.bicepparam \
//     --parameters app_service_hostname=<hostname>

using '../../identity.bicep'

var answers = any(loadJsonContent('../../../environments/example/01-platform/setup.auto.tfvars.json'))
var entra = answers.?entra_app ?? {}

param display_name = entra.?display_name ?? 'nerdio-nmw-app'
param create_entra_app = answers.?create_entra_app ?? true
param existing_client_id = entra.?existing_client_id
param owner_object_ids = entra.?owner_object_ids ?? []
param wvd_admin_object_ids = entra.?wvd_admin_object_ids ?? []
param grant_admin_consent = entra.?grant_admin_consent ?? false
param enable_mail_send = entra.?enable_mail_send ?? false
param create_rest_api_client = entra.?create_rest_api_client ?? true
param rest_api_federated_credentials = entra.?rest_api_federated_credentials ?? {}
param rest_api_additional_principal_object_ids = entra.?rest_api_additional_principal_object_ids ?? []
