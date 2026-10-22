# This repository's GitHub settings. Change them here, in a pull request; the first plan shows
# only what differs from GitHub today.

# The repository's identity (description, homepage, which features are on) is read from GitHub
# rather than declared, so a fork of the kit keeps its own. Topics are declared.
data "github_repository" "this" {
  full_name = "${var.owner}/${var.repository}"
}

module "settings" {
  source = "../modules/github-settings"

  repository = var.repository
  branch     = "main"

  repo = {
    description     = data.github_repository.this.description
    homepage_url    = data.github_repository.this.homepage_url
    has_issues      = data.github_repository.this.has_issues
    has_projects    = data.github_repository.this.has_projects
    has_wiki        = data.github_repository.this.has_wiki
    has_discussions = data.github_repository.this.has_discussions
    topics          = [] # none today; open question in the spec
  }

  # ai-brain decision 0014 defaults (merge commits on, auto-merge allowed). Squash and rebase stay
  # on as today until the owner decides otherwise.
  merge = {}

  ruleset = {
    # Jobs of validate.yml, which runs on every pull request with no paths filter. kb-validate has
    # a paths filter, so it can't be required yet; kb-capture and auto-merge aren't adopted here.
    required_checks = ["terraform", "setup", "preflight-zipapp", "packer", "secrets"]
  }

  labels = {
    "kb-feedback"      = { color = "1d76db", description = "Knowledge base feedback" }
    "kb-known-error"   = { color = "d93f0b", description = "Known error for the troubleshooting catalog" }
    "kb-accepted"      = { color = "0e8a16", description = "Reviewed; turn into a KB pull request" }
    "kb-freshness"     = { color = "fbca04", description = "KB pages to re-check" }
    "kb-digest"        = { color = "0e8a16", description = "Knowledge base curator digest" }
    "kb-source"        = { color = "5319e7", description = "Expert or source nominated for the KB to follow" }
    "no-kb"            = { color = "ededed" }
    "handoff"          = { color = "ededed" }
    "handoff-proposed" = { color = "ededed" }
    "settings-drift"   = { color = "b60205", description = "GitHub settings differ from github/ (drift workflow)" }
  }
}
