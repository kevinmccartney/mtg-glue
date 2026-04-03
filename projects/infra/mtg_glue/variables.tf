variable "aws_region" {
  description = "AWS region to deploy resources into."
  type        = string
  default     = "us-east-1"
}

variable "notification_recipient_email" {
  description = "Email address that receives sync status notifications."
  type        = string
}

variable "notification_sender_email" {
  description = "Email address that sends sync status notifications (must be SES-verified)."
  type        = string
}

