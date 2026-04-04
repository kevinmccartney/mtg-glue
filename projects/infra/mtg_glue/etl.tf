# Scheduled ECS Fargate task: EchoMTG → Moxfield ETL (S3, SES).

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
    sid    = "RunTask"
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
}

resource "aws_iam_role_policy" "eventbridge_ecs" {
  name   = "run-etl"
  role   = aws_iam_role.eventbridge_ecs.id
  policy = data.aws_iam_policy_document.eventbridge_ecs.json
}

resource "aws_cloudwatch_event_rule" "etl" {
  name                = "mtg-glue-etl-schedule"
  description         = "Trigger mtg-glue ETL ECS task on a schedule"
  schedule_expression = var.etl_schedule_expression
  state               = var.etl_schedule_enabled ? "ENABLED" : "DISABLED"
}

resource "aws_cloudwatch_event_target" "etl" {
  rule      = aws_cloudwatch_event_rule.etl.name
  arn       = aws_ecs_cluster.etl.arn
  role_arn  = aws_iam_role.eventbridge_ecs.arn
  target_id = "etl"

  depends_on = [aws_iam_role_policy.eventbridge_ecs]

  ecs_target {
    task_count          = 1
    task_definition_arn = aws_ecs_task_definition.etl.arn
    launch_type         = "FARGATE"
    platform_version    = "LATEST"

    network_configuration {
      subnets          = data.aws_subnets.default.ids
      security_groups  = [aws_security_group.etl_task.id]
      assign_public_ip = true
    }
  }
}

# Preserve ECS cluster in state when upgrading from aws_ecs_cluster.main (same AWS name "mtg-glue").
moved {
  from = aws_ecs_cluster.main
  to   = aws_ecs_cluster.etl
}

