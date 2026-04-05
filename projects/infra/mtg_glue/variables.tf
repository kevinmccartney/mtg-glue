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
  description = "EventBridge schedule (UTC) that starts the mtg-glue ETL Step Functions execution."
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

variable "etl_sfn_task_timeout_seconds" {
  description = "Step Functions timeout for ecs:runTask.sync (whole ETL run, including waits)."
  type        = number
  default     = 21600
}

variable "etl_sfn_retry_max_attempts" {
  description = "Max attempts for the ECS sync task state after an error (includes the first run)."
  type        = number
  default     = 3
}

variable "etl_sfn_retry_interval_seconds" {
  description = "Base delay before the first retry of the ECS sync task state."
  type        = number
  default     = 120
}

variable "etl_sfn_retry_backoff_rate" {
  description = "Step Functions retry backoff multiplier for the ECS sync task state."
  type        = number
  default     = 2.0
}
