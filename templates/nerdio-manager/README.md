# Nerdio Manager Marketplace template

Nerdio doesn't publish a stable ARM template URL for Nerdio Manager for Enterprise, so the kit
deploys whatever template you export from the Azure Marketplace and pins it here.

1. In the Azure portal, open **Nerdio Manager for Enterprise** from the Marketplace (not the
   "Billing Subscription" listing) and fill in the subscription, an empty resource group and region.
2. On **Review + create**, choose **Download a template for automation**.
3. Save `template.json` in this folder and copy the values from `parameters.json` into
   `nerdio_template_parameters` in your tfvars.
4. Commit the template. When Nerdio ships a new Marketplace version, export again and review the diff.

Nerdio updates the running app itself after install, so the module ignores later template edits
on an existing deployment. Re-exporting only matters for new environments.
