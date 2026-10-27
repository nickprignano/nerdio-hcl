# Nerdio Manager Marketplace template

Optional for `nerdio_install = "marketplace"`. By default (`nerdio_template_file = null`),
`modules/nerdio-manager` discovers a Nerdio Manager deployment you create directly in the Azure
portal Marketplace, so no exported template file is needed. The default terraform install
(`modules/nerdio-core`) doesn't use a template either.

If you want Terraform itself to deploy the Marketplace ARM template (`nerdio_template_file = "../../../templates/nerdio-manager/template.json"`):

1. In the Azure portal, open **Nerdio Manager for Enterprise** from the Marketplace (not the
   "Billing Subscription" listing) and fill in the subscription, an empty resource group and region.
2. On **Review + create**, choose **Download a template for automation**.
3. Save `template.json` in this folder and copy the values from `parameters.json` into
   `nerdio_template_parameters` in your tfvars.
4. Commit the template. When Nerdio ships a new Marketplace version, export again and review the diff.

Nerdio updates the running app itself after install, so the module ignores later template edits
on an existing deployment. Re-exporting only matters for new environments.
