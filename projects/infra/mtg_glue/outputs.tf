output "bucket_name" {
  description = "Name of the S3 bucket."
  value       = aws_s3_bucket.main.id
}

output "bucket_arn" {
  description = "ARN of the S3 bucket."
  value       = aws_s3_bucket.main.arn
}

output "notification_sender_email" {
  description = "SES-verified sender address for sync notifications."
  value       = aws_ses_email_identity.sender.email
}

output "notification_recipient_email" {
  description = "SES-verified recipient address for sync notifications."
  value       = aws_ses_email_identity.recipient.email
}

output "etl_ecr_repository_url" {
  description = "ECR URL to push the ETL image (use tag :latest)."
  value       = aws_ecr_repository.etl.repository_url
}

output "etl_ecs_cluster_name" {
  description = "ECS cluster running scheduled ETL tasks."
  value       = aws_ecs_cluster.etl.name
}

output "etl_task_definition_family" {
  description = "ECS task definition family for ETL."
  value       = aws_ecs_task_definition.etl.family
}

output "etl_secretsmanager_secret_name" {
  description = "Secrets Manager secret holding ECHOMTG_*, MOXFIELD_*, CAPSOLVER_* (JSON keys)."
  value       = aws_secretsmanager_secret.etl.name
}

output "etl_cloudwatch_log_group" {
  description = "CloudWatch log group for ETL container logs."
  value       = aws_cloudwatch_log_group.etl.name
}

output "etl_schedule_rule_name" {
  description = "EventBridge rule that triggers ETL on a schedule."
  value       = aws_cloudwatch_event_rule.etl.name
}

output "etl_manual_run_cli_example" {
  description = "One-off Fargate run using the default VPC's first subnet (smoke test after image push + secrets)."
  value = format(
    "%s\n",
    format(
      "aws ecs run-task --cluster %s --launch-type FARGATE --task-definition %s --network-configuration \"awsvpcConfiguration={subnets=[%s],securityGroups=[%s],assignPublicIp=ENABLED}\"",
      aws_ecs_cluster.etl.name,
      aws_ecs_task_definition.etl.family,
      data.aws_subnets.default.ids[0],
      aws_security_group.etl_task.id,
    ),
  )
}
