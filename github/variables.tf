variable "owner" {
  description = "The account that owns the repository. The drift workflow and plan.sh pass it from GitHub or git."
  type        = string
}

variable "repository" {
  description = "The repository name, without the owner."
  type        = string
}
