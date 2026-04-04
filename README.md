# MTG Glue

Personal tooling for EchoMTG → Moxfield collection sync, S3 exports, and email notifications.

## Deploying the ETL to AWS

The scheduled job runs as an **ECS Fargate** task (see `projects/infra/mtg_glue/etl.tf`): **EventBridge** triggers **RunTask** on a cron; the container runs `python -m etl.echo_moxfield_etl` under **Xvfb** with the CapSolver browser extension.

### Prerequisites

- [Poetry](https://python-poetry.org/), [Docker](https://www.docker.com/), [Terraform](https://www.terraform.io/) (≥ 1.5), [AWS CLI](https://aws.amazon.com/cli/), and [Task](https://taskfile.dev/).
- An AWS account; SES sender and recipient emails verified in that account (Terraform creates the identity resources).

### 1. Environment file

Copy `.env.example` to `.env` and set at least:

- `AWS_REGION`, `TF_STATE_BUCKET` (S3 bucket for Terraform state; create manually or via bootstrap below).
- `NOTIFICATION_SENDER_EMAIL`, `NOTIFICATION_RECIPIENT_EMAIL` (must match what you pass into Terraform).

Local CLI usage also uses `ECHOMTG_*`, `MOXFIELD_*`, `CAPSOLVER_API_KEY`, and `S3_BUCKET` as needed; the **ECS task** does not read `.env`—it uses IAM roles and **Secrets Manager** (next steps).

### 2. Terraform: bootstrap (first time only)

If you do not yet have a state bucket and DynamoDB lock table:

```bash
task infra:init:bootstrap
task infra:apply:bootstrap
```

Then point `TF_STATE_BUCKET` in `.env` at that bucket.

### 3. Terraform: `mtg_glue` stack

```bash
task infra:init:mtg-glue
task infra:plan:mtg-glue    # review
task infra:apply:mtg-glue
```

This provisions the **S3** data bucket, **SES** identities, **ECR** repository `mtg-glue-etl`, **ECS** cluster `mtg-glue`, Fargate **task definition**, **Secrets Manager** secret `mtg-glue/etl-env`, **CloudWatch** logs, security group, and the **EventBridge** schedule (default: daily at 06:00 UTC; override with Terraform variables `etl_schedule_expression`, `etl_schedule_enabled`, `etl_cpu`, `etl_memory` in `projects/infra/mtg_glue/variables.tf` or `-var` flags).

### 4. Secrets and config in AWS

1. **Secrets Manager** — Open secret `mtg-glue/etl-env` and set JSON keys: `ECHOMTG_USERNAME`, `ECHOMTG_PASSWORD`, `MOXFIELD_USERNAME`, `MOXFIELD_PASSWORD`, `CAPSOLVER_API_KEY`. Terraform only seeds placeholders; updating values in the console is normal.

2. **Config YAML** — Upload your merged config to the **same bucket** Terraform created for data (see `terraform output bucket_name`):

   ```bash
   aws s3 cp config.yaml "s3://$(terraform -chdir=projects/infra/mtg_glue output -raw bucket_name)/config/config.yaml"
   ```

   The task sets `MTG_GLUE_CONFIG_S3_KEY=config/config.yaml` so the ETL loads config from that object. Start from `config.yaml.example` if you do not have a local `config.yaml`.

### 5. Build and push the container image

With AWS credentials in your environment (for example `eval "$(task env:aws-export)"` if you use SSO):

```bash
task etl:push-ecr
```

This builds the `etl` service from `docker-compose.yml`, tags `mtg-glue-etl:local` as `:latest` in ECR, and pushes.

The Compose service sets **`platform: linux/amd64`** so the image matches **Fargate (x86)**. On **Apple Silicon**, a plain local build is `arm64`, which leads to `CannotPullContainerError` in ECS; rebuilding after this setting fixes that (first build may be slower due to emulation). To use **Graviton (ARM) Fargate** instead, you would change the ECS task CPU architecture and remove or set `platform: linux/arm64`—this repo targets the default x86 Fargate platform.

### 6. Smoke test before relying on the schedule

```bash
task etl:smoke-run
```

Run the printed `aws ecs run-task ...` command once. Check **CloudWatch** log group from `terraform output etl_cloudwatch_log_group`.

### 7. Schedule

After a successful smoke test, leave the EventBridge rule enabled (default). To pause scheduled runs without tearing down infra, set `etl_schedule_enabled = false` and re-apply, or disable the rule in the AWS console.

---

## Local development (short)

```bash
poetry install
cp config.yaml.example config.yaml   # then edit; file is gitignored
poetry run moxfield-import --help
task etl:build
```

Run the full sync on your machine with visible browsers: `projects/etl/run_headed_local.sh` (see comments in that script for CapSolver setup).

## Useful Task targets

| Task | Purpose |
|------|---------|
| `task etl:build` | Build Docker image `mtg-glue-etl:local` |
| `task etl:run` | Shell in the ETL container |
| `task etl:push-ecr` | Build, tag `:latest`, push to ECR |
| `task etl:smoke-run` | Print a one-off `aws ecs run-task` example |
| `task infra:validate:mtg-glue` | `terraform validate` without remote backend |
