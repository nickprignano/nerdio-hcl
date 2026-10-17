variable "repository" {
  description = "Repository name (without the owner); the github provider's owner sets the account."
  type        = string
}

variable "branch" {
  description = "The branch the deploy pipeline's environments trust. The ruleset protects it."
  type        = string
  default     = "main"
}

variable "protect_branch" {
  description = <<-EOT
    Protect the branch with a ruleset: changes land through a pull request, and it can't be
    force-pushed or deleted. The apply environment trusts only this branch, so leaving it open
    means anyone who can push to it can change what an approved apply runs.
  EOT
  type        = bool
  default     = true
}

variable "actions_can_open_pull_requests" {
  description = <<-EOT
    Allow GitHub Actions to create and approve pull requests. kb-feedback needs it to open its
    pull request; without it, the workflow pushes a branch and asks you to open one.
  EOT
  type        = bool
  default     = true
}
