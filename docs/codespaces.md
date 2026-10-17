# Working from GitHub Codespaces

[GitHub Codespaces](https://docs.github.com/en/codespaces) gives you VS Code with a real terminal
in the browser, an iPad included. It's an optional workbench for the kit. Azure Cloud Shell stays
the baseline every step is tested against ([decision 0012](knowledge/decisions/0012-cloud-shell-baseline.md)),
and long applies belong on the [deploy pipeline](pipeline.md).

| | Cloud Shell | Codespaces |
|---|---|---|
| Editor | Basic | Full VS Code with the Terraform extension |
| Idle timeout | About 20 minutes, not adjustable | 30 minutes by default, up to 240 |
| Signed in to Azure | Already | `az login --use-device-code` |
| Graph PowerShell (`./nerdio fix roles`) | Built in | Not installed; use Cloud Shell for it |
| Cost | Free, plus a small storage account | Free monthly allowance on personal accounts, then billed |

## One-time setting

Raise the idle timeout: on GitHub, choose your profile picture > **Settings** > **Codespaces** >
**Default idle timeout**, enter `240` and save. While you're there, check the **Default retention
period**: GitHub deletes a stopped codespace after it (30 days unless you change it).

## Start a codespace

1. Open the repository and choose **Code** > **Codespaces** > **Create codespace on main**. The
   2-core machine is enough. On an iPad, **Add to Home Screen** opens it full screen.
2. Wait for the first build. The [dev container](../.devcontainer/devcontainer.json) installs the
   Azure CLI, Terraform, tflint and the GitHub CLI, then `post-create.sh` installs `nerdio/nme`
   from Nerdio's own release (never a re-hosted copy; see [guardrails](guardrails.md)).
3. Sign in to Azure and pick the subscription:

   ```bash
   az login --use-device-code               # enter the code it shows at the link, in another tab
   az account show --query name -o tsv      # the right subscription? else: az account set --subscription "<name>"
   ```

   If Conditional Access blocks device-code sign-in in your tenant, work from Cloud Shell there.
4. Carry on exactly as in [Cloud Shell](cloud-shell.md): `./nerdio init`, `./nerdio preflight`,
   then `./scripts/cloudshell-bootstrap.sh platform` to plan. The script reads the IDs from
   `az account show`, so nothing is typed in.

## Things to know

- **State lives in the codespace.** Terraform's state file (its record of what it built) sits in
  the repository folder, gitignored. Deleting the codespace deletes it, and so does the retention
  period above. For anything you'll keep, move state to the pipeline (`scripts/pipeline/bootstrap.sh
  --adopt`, see [pipeline.md](pipeline.md)) before you delete the codespace.
- **A codespace still idles out.** It stops after the timeout like Cloud Shell does, just later.
  Rerunning an apply resumes from state, but the pipeline avoids the problem altogether.
- **Uploads.** The marketplace install looks for the exported template zip in your home
  directory. Drag it into the Explorer, then `mv` it to `~`.
- **Secrets.** The same rules apply: secrets never go into chat, the repository or Codespaces
  settings for this kit. Stage 2 reads the REST secret from Key Vault with your sign-in.
