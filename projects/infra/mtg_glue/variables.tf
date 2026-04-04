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

variable "etl_schedule_expression" {
  description = "EventBridge schedule for the mtg-glue ETL ECS task (UTC)."
  type        = string
  default     = "cron(0 6 * * ? *)"
}

variable "etl_schedule_enabled" {
  description = "Whether the EventBridge ETL schedule is ENABLED."
  type        = bool
  default     = true
}

variable "etl_cpu" {
  description = "Fargate CPU units for ETL task (e.g. 1024, 2048)."
  type        = number
  default     = 2048
}

variable "etl_memory" {
  description = "Fargate memory (MiB) for ETL task; must pair with CPU."
  type        = number
  default     = 4096
}
