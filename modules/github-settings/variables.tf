variable "repository" {
  description = "Repository name (without the owner); the github provider's owner sets the account."
  type        = string
}

variable "repo" {
  description = <<-EOT
    What the repository page shows and which features it has on. These aren't conventions: set
    them to what the repository has today, so importing it plans no change.
  EOT
  type = object({
    description     = optional(string, "")
    homepage_url    = optional(string, "")
    topics          = optional(list(string), [])
    has_issues      = optional(bool, true)
    has_projects    = optional(bool, false)
    has_wiki        = optional(bool, false)
    has_discussions = optional(bool, false)
  })
  default = {}
}

variable "merge" {
  description = <<-EOT
    How pull requests merge. The defaults are ai-brain decision 0014's GitHub work conventions:
    merge commits (kb-auto-merge merges with --merge) and auto-merge allowed, so a low-risk pull
    request can merge itself once every required check is green.
  EOT
  type = object({
    allow_merge_commit     = optional(bool, true)
    allow_squash_merge     = optional(bool, true)
    allow_rebase_merge     = optional(bool, true)
    allow_auto_merge       = optional(bool, true)
    allow_update_branch    = optional(bool, false)
    delete_branch_on_merge = optional(bool, false)
  })
  default = {}
}

variable "branch" {
  description = "The default branch. The ruleset protects it, and the deploy pipeline's apply environment trusts it."
  type        = string
  default     = "main"
}

variable "ruleset" {
  description = <<-EOT
    The ruleset on the default branch (ai-brain decision 0014): changes land only through a pull
    request, the branch can't be deleted or force-pushed, and the listed checks must pass.
      required_checks      job names that run on every pull request, with no paths filter: a
                           required check that never reports holds every pull request
      checks_app_id        the GitHub App that must report them (15368 is GitHub Actions), so a
                           commit status from anything else can't satisfy a required check
      required_approvals   0, because the owner can't approve their own pull requests
      admin_bypass         let the repository admin role merge a pull request whose checks never
                           ran (pull requests only, never a direct push)
  EOT
  type = object({
    enabled            = optional(bool, true)
    name               = optional(string) # default protect-<branch>, the name the deploy bootstrap used
    required_checks    = optional(list(string), [])
    checks_app_id      = optional(number, 15368)
    required_approvals = optional(number, 0)
    admin_bypass       = optional(bool, true)
  })
  default = {}
}

variable "labels" {
  description = <<-EOT
    Issue labels the repository's workflows and issue forms rely on. Only these are managed;
    other labels are left alone. Colours are hex without the #.
  EOT
  type = map(object({
    color       = string
    description = optional(string, "")
  }))
  default = {}
}

variable "security" {
  description = <<-EOT
    Security settings (ai-brain decision 0016, step 11: push protection first, gitleaks as the
    backstop). Dependabot alerts and security updates are on by default.
  EOT
  type = object({
    secret_scanning             = optional(bool, true)
    push_protection             = optional(bool, true)
    dependabot_alerts           = optional(bool, true)
    dependabot_security_updates = optional(bool, true)
  })
  default = {}
}

variable "actions" {
  description = <<-EOT
    The default GITHUB_TOKEN stays read-only: every workflow declares its own permissions.
    can_open_pull_requests lets a workflow (kb-feedback) open its pull request with that token.
  EOT
  type = object({
    can_open_pull_requests = optional(bool, true)
  })
  default = {}
}
