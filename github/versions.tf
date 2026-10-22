terraform {
  required_version = ">= 1.11"

  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.13"
    }
  }

  # No backend, on purpose. Every plan starts from an empty state and imports what already exists
  # (imports.tf), so the plan compares this code with GitHub itself: drift shows as a change, and
  # there's no state file to store, lock, protect or let go stale. See README.md.
}

# Reads GITHUB_TOKEN from the environment, never from a file or a variable. In the drift workflow
# it's a one-hour, read-only GitHub App token; for an apply it's your one-day fine-grained token.
provider "github" {
  owner = var.owner
}
