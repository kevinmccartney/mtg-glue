terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Bootstrap intentionally uses local state — it creates the remote
  # backend that all other modules depend on.
}

provider "aws" {
  region = var.aws_region
}
