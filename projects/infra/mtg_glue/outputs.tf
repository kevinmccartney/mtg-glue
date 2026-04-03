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
