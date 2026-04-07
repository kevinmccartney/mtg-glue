# Scheduled ECS Fargate task: EchoMTG → Moxfield ETL (S3, SES).
# EventBridge → Step Functions (ecs:runTask.sync, retries) → ECS; exhausted failures → SQS DLQ.

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_ecr_repository" "etl" {
  name                 = "mtg-glue-etl"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecs_cluster" "etl" {
  name = "mtg-glue"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "etl" {
  name              = "/ecs/mtg-glue/etl"
  retention_in_days = 30
}

resource "aws_secretsmanager_secret" "etl" {
  name        = "mtg-glue/etl-env"
  description = "Credentials for ECS mtg-glue ETL task (update values after apply)."
}

resource "aws_secretsmanager_secret_version" "etl" {
  secret_id = aws_secretsmanager_secret.etl.id
  secret_string = jsonencode({
    ECHOMTG_USERNAME  = "CHANGE_ME"
    ECHOMTG_PASSWORD  = "CHANGE_ME"
    MOXFIELD_USERNAME = "CHANGE_ME"
    MOXFIELD_PASSWORD = "CHANGE_ME"
    CAPSOLVER_API_KEY = "CHANGE_ME"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "etl_execution" {
  name               = "mtg-glue-etl-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role_policy_attachment" "etl_execution_ecs" {
  role       = aws_iam_role.etl_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "etl_execution_secrets" {
  statement {
    sid    = "GetSecrets"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
    ]
    resources = [aws_secretsmanager_secret.etl.arn]
  }
}

resource "aws_iam_role_policy" "etl_execution_secrets" {
  name   = "secrets"
  role   = aws_iam_role.etl_execution.id
  policy = data.aws_iam_policy_document.etl_execution_secrets.json
}

resource "aws_iam_role" "etl_task" {
  name               = "mtg-glue-etl-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "etl_task" {
  statement {
    sid    = "S3"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.main.arn,
      "${aws_s3_bucket.main.arn}/*",
    ]
  }

  statement {
    sid       = "SES"
    effect    = "Allow"
    actions   = ["ses:SendEmail", "ses:SendRawEmail"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "etl_task" {
  name   = "s3-ses"
  role   = aws_iam_role.etl_task.id
  policy = data.aws_iam_policy_document.etl_task.json
}

locals {
  etl_secret_arn = aws_secretsmanager_secret.etl.arn

  etl_container = {
    name      = "etl"
    image     = "${aws_ecr_repository.etl.repository_url}:latest"
    essential = true
    environment = [
      { name = "AWS_DEFAULT_REGION", value = var.aws_region },
      { name = "AWS_REGION", value = var.aws_region },
      { name = "S3_BUCKET", value = aws_s3_bucket.main.id },
      { name = "MTG_GLUE_CONFIG_S3_KEY", value = "config/config.yaml" },
      { name = "S3_CSV_RETENTION_COUNT", value = tostring(var.s3_csv_retention_count) },
      { name = "NOTIFICATION_SENDER_EMAIL", value = var.notification_sender_email },
      { name = "NOTIFICATION_RECIPIENT_EMAIL", value = var.notification_recipient_email },
      { name = "PYTHONUNBUFFERED", value = "1" },
    ]
    secrets = [
      { name = "ECHOMTG_USERNAME", valueFrom = "${local.etl_secret_arn}:ECHOMTG_USERNAME::" },
      { name = "ECHOMTG_PASSWORD", valueFrom = "${local.etl_secret_arn}:ECHOMTG_PASSWORD::" },
      { name = "MOXFIELD_USERNAME", valueFrom = "${local.etl_secret_arn}:MOXFIELD_USERNAME::" },
      { name = "MOXFIELD_PASSWORD", valueFrom = "${local.etl_secret_arn}:MOXFIELD_PASSWORD::" },
      { name = "CAPSOLVER_API_KEY", valueFrom = "${local.etl_secret_arn}:CAPSOLVER_API_KEY::" },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.etl.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }
}

resource "aws_ecs_task_definition" "etl" {
  family                   = "mtg-glue-etl"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.etl_cpu)
  memory                   = tostring(var.etl_memory)
  execution_role_arn       = aws_iam_role.etl_execution.arn
  task_role_arn            = aws_iam_role.etl_task.arn

  container_definitions = jsonencode([local.etl_container])

  depends_on = [
    aws_iam_role_policy_attachment.etl_execution_ecs,
    aws_iam_role_policy.etl_execution_secrets,
    aws_secretsmanager_secret_version.etl,
  ]
}

resource "aws_security_group" "etl_task" {
  name        = "mtg-glue-etl-task"
  description = "Egress-only for mtg-glue ETL Fargate task"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_sqs_queue" "etl_sfn_dlq" {
  name                      = "mtg-glue-etl-sfn-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

data "aws_iam_policy_document" "sfn_etl_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sfn_etl" {
  name               = "mtg-glue-sfn-etl"
  assume_role_policy = data.aws_iam_policy_document.sfn_etl_assume.json
}

data "aws_iam_policy_document" "sfn_etl" {
  statement {
    sid    = "ECSRun"
    effect = "Allow"
    actions = [
      "ecs:RunTask",
    ]
    resources = [
      replace(
        aws_ecs_task_definition.etl.arn,
        ":${aws_ecs_task_definition.etl.revision}",
        ":*",
      ),
    ]
  }

  statement {
    sid    = "ECSObserve"
    effect = "Allow"
    actions = [
      "ecs:StopTask",
      "ecs:DescribeTasks",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "EventBridgeSync"
    effect = "Allow"
    actions = [
      "events:PutTargets",
      "events:PutRule",
      "events:DescribeRule",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "PassRoles"
    effect = "Allow"
    actions = [
      "iam:PassRole",
    ]
    resources = [
      aws_iam_role.etl_execution.arn,
      aws_iam_role.etl_task.arn,
    ]
  }

  statement {
    sid    = "Dlq"
    effect = "Allow"
    actions = [
      "sqs:SendMessage",
    ]
    resources = [aws_sqs_queue.etl_sfn_dlq.arn]
  }
}

resource "aws_iam_role_policy" "sfn_etl" {
  name   = "etl-ecs-dlq"
  role   = aws_iam_role.sfn_etl.id
  policy = data.aws_iam_policy_document.sfn_etl.json
}

resource "aws_sqs_queue_policy" "etl_sfn_dlq" {
  queue_url = aws_sqs_queue.etl_sfn_dlq.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSfnRoleDlq"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.sfn_etl.arn
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.etl_sfn_dlq.arn
      },
    ]
  })
}

locals {
  sfn_etl_definition = jsonencode({
    Comment = "Run mtg-glue ETL on Fargate; retry transient failures; DLQ after exhaustion."
    StartAt = "RunEtl"
    States = {
      RunEtl = {
        Type     = "Task"
        Resource = "arn:aws:states:::ecs:runTask.sync"
        Parameters = {
          LaunchType     = "FARGATE"
          Cluster        = aws_ecs_cluster.etl.arn
          TaskDefinition = aws_ecs_task_definition.etl.family
          NetworkConfiguration = {
            AwsvpcConfiguration = {
              Subnets        = data.aws_subnets.default.ids
              SecurityGroups = [aws_security_group.etl_task.id]
              AssignPublicIp = "ENABLED"
            }
          }
          PlatformVersion = "LATEST"
        }
        Retry = [
          {
            ErrorEquals = [
              "States.TaskFailed",
              "States.Timeout",
              "ECS.ServerException",
              "ECS.AmazonECSException",
              "ECS.InvalidParameterException",
            ]
            IntervalSeconds = var.etl_sfn_retry_interval_seconds
            MaxAttempts     = var.etl_sfn_retry_max_attempts
            BackoffRate     = var.etl_sfn_retry_backoff_rate
          },
        ]
        TimeoutSeconds = var.etl_sfn_task_timeout_seconds
        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            ResultPath  = "$.error"
            Next        = "RecordFailure"
          },
        ]
        End = true
      }
      RecordFailure = {
        Type     = "Task"
        Resource = "arn:aws:states:::sqs:sendMessage"
        Parameters = merge(
          {
            QueueUrl = aws_sqs_queue.etl_sfn_dlq.url
          },
          { "MessageBody.$" = "States.JsonToString($.error)" },
        )
        End = true
      }
    }
  })
}

resource "aws_sfn_state_machine" "etl" {
  name     = "mtg-glue-etl"
  role_arn = aws_iam_role.sfn_etl.arn

  definition = local.sfn_etl_definition

  depends_on = [
    aws_iam_role_policy.sfn_etl,
    aws_sqs_queue_policy.etl_sfn_dlq,
  ]
}

data "aws_iam_policy_document" "eventbridge_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eventbridge_ecs" {
  name               = "mtg-glue-eventbridge-ecs"
  assume_role_policy = data.aws_iam_policy_document.eventbridge_assume.json
}

data "aws_iam_policy_document" "eventbridge_ecs" {
  statement {
    sid    = "StartSfn"
    effect = "Allow"
    actions = [
      "states:StartExecution",
    ]
    resources = [aws_sfn_state_machine.etl.arn]
  }
}

resource "aws_iam_role_policy" "eventbridge_ecs" {
  name   = "run-etl"
  role   = aws_iam_role.eventbridge_ecs.id
  policy = data.aws_iam_policy_document.eventbridge_ecs.json
}

resource "aws_cloudwatch_event_rule" "etl" {
  name                = "mtg-glue-etl-schedule"
  description         = "Trigger mtg-glue ETL Step Functions execution on a schedule"
  schedule_expression = var.etl_schedule_expression
  state               = var.etl_schedule_enabled ? "ENABLED" : "DISABLED"
}

resource "aws_cloudwatch_event_target" "etl" {
  rule      = aws_cloudwatch_event_rule.etl.name
  arn       = aws_sfn_state_machine.etl.arn
  role_arn  = aws_iam_role.eventbridge_ecs.arn
  target_id = "etl"
  input     = jsonencode({})

  depends_on = [
    aws_iam_role_policy.eventbridge_ecs,
    aws_sfn_state_machine.etl,
  ]
}

# Preserve ECS cluster in state when upgrading from aws_ecs_cluster.main (same AWS name "mtg-glue").
moved {
  from = aws_ecs_cluster.main
  to   = aws_ecs_cluster.etl
}
