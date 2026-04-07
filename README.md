# MTG Glue

Personal tooling for EchoMTG → Moxfield collection sync, S3 exports, and email notifications.

## Local development

- Install deps: `poetry install`
- **Pre-commit** (repo root): `poetry run pre-commit install` and `poetry run pre-commit install --hook-type commit-msg` — runs [pre-commit](https://pre-commit.com/) hooks (YAML, EOF/trailing space, **Black**, **isort**, **Flake8**, **Pylint**, **mypy** via Poetry; **Conventional Commits** on `commit-msg` via [conventional-pre-commit](https://github.com/compilerla/conventional-pre-commit)). Run all file hooks manually: `poetry run pre-commit run --all-files`
- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/) (enforced by the `commit-msg` hook and `poetry run cz check` in CI on PRs). Interactive helper: `task commit`; releases/changelog: [Commitizen](https://commitizen-tools.github.io/commitizen/) (`pyproject.toml` → `[tool.commitizen]`). **Custom commit types**: [conventional-pre-commit](https://github.com/compilerla/conventional-pre-commit) only allows the types listed in `.pre-commit-config.yaml` (`args` on `conventional-pre-commit`); add a new type there and list **every** type you want (passing `args` replaces the default set). For Commitizen, `feat` / `fix` / `refactor` / `perf` drive semver bumps via the built-in `commit_parser`; other types are valid for `cz check` but won’t affect version bumps unless you switch to `cz_customize` and extend `commit_parser` / `bump_map` (see [Commitizen customize](https://commitizen-tools.github.io/commitizen/customization/)).
- **Pylint** manually (from repo root): `PYTHONPATH=projects poetry run pylint projects/cli projects/lib projects/models projects/etl tests` — config in [`.pylintrc`](.pylintrc)
- Tests: `poetry run pytest`

## TODO

- [ ] Versioning
- [ ] Create debug mode
- [ ] Tests
- [ ] E2E tests

## Deploying the ETL to AWS

The scheduled job runs as an **ECS Fargate** task orchestrated by **Step Functions** (see `projects/infra/mtg_glue/etl.tf`): **EventBridge** starts a state machine on a cron; the `ecs:runTask.sync` state waits for the task to finish and **retries** on failure (for example flaky captcha). After retries are exhausted, a message is sent to an **SQS DLQ** (`terraform output etl_sfn_dlq_url`). The container still runs `python -m etl.echo_moxfield_etl` under **Xvfb** with the CapSolver browser extension.

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

This provisions the **S3** data bucket (with lifecycle rules that expire **noncurrent object versions** under `echomtg/` and `moxfield/` after seven days—see [`projects/infra/mtg_glue/main.tf`](projects/infra/mtg_glue/main.tf)), **SES** identities, **ECR** repository `mtg-glue-etl`, **ECS** cluster `mtg-glue`, Fargate **task definition**, **Step Functions** state machine `mtg-glue-etl`, **SQS** DLQ for exhausted failures, **Secrets Manager** secret `mtg-glue/etl-env`, **CloudWatch** logs, security group, and the **EventBridge** schedule (default: daily at 06:00 UTC). Override schedule, task size, Step Functions retry/timeout, or **how many timestamped CSVs to keep per export family** via `etl_schedule_expression`, `etl_schedule_enabled`, `etl_cpu`, `etl_memory`, `etl_sfn_task_timeout_seconds`, `etl_sfn_retry_max_attempts`, `etl_sfn_retry_interval_seconds`, `etl_sfn_retry_backoff_rate`, and `s3_csv_retention_count` in [`projects/infra/mtg_glue/variables.tf`](projects/infra/mtg_glue/variables.tf) or `-var` flags.

**S3 “last N” CSV retention:** S3 lifecycle alone cannot keep exactly the last _N_ objects. After each successful upload of the three timestamped exports, the ETL trims each family to the newest **20** objects by default (`echomtg/echomtg-export-*`, `moxfield/moxfield-import-*`, `moxfield/moxfield-collection-export-*`). The ECS task sets `S3_CSV_RETENTION_COUNT` from Terraform; for local runs, set the same variable in `.env` if you want a non-default value (`0` disables trimming).

### 4. Secrets and config in AWS

1. **Secrets Manager** — Open secret `mtg-glue/etl-env` and set JSON keys: `ECHOMTG_USERNAME`, `ECHOMTG_PASSWORD`, `MOXFIELD_USERNAME`, `MOXFIELD_PASSWORD`, `CAPSOLVER_API_KEY`. Terraform only seeds placeholders; updating values in the console is normal.

2. **Config YAML** — Put `./config.yaml` in the data bucket at `config/config.yaml` (same key the ECS task uses):

   ```bash
   task etl:upload-config
   ```

   Or manually: `aws s3 cp config.yaml "s3://$(terraform -chdir=projects/infra/mtg_glue output -raw bucket_name)/config/config.yaml"`. Start from `config.yaml.example` if needed.

### 5. Build and push the container image

With AWS credentials in your environment (for example `eval "$(task env:aws-export)"` if you use SSO):

```bash
task etl:push-ecr
```

This builds the `etl` service from `docker-compose.yml`, tags `mtg-glue-etl:local` as `:latest` in ECR, and pushes.

The Compose service sets **`platform: linux/amd64`** so the image matches **Fargate (x86)**. On **Apple Silicon**, a plain local build is `arm64`, which leads to `CannotPullContainerError` in ECS; rebuilding after this setting fixes that (first build may be slower due to emulation). To use **Graviton (ARM) Fargate** instead, you would change the ECS task CPU architecture and remove or set `platform: linux/arm64`—this repo targets the default x86 Fargate platform.

### 6. Smoke test before relying on the schedule

```bash
task etl:run:fargate
```

Starts a one-off Fargate task using `terraform output -raw etl_manual_run_cli_example` (same wiring as a manual `aws ecs run-task`). Check **CloudWatch** log group from `terraform output etl_cloudwatch_log_group`.

### 7. Schedule

After a successful smoke test, leave the EventBridge rule enabled (default). To pause scheduled runs without tearing down infra, set `etl_schedule_enabled = false` and re-apply, or disable the rule in the AWS console. Inspect failed scheduled runs in the **Step Functions** console (`terraform output etl_sfn_state_machine_arn`); if a run exhausted retries, check the DLQ for the error payload.

---

## Local development (short)

```bash
poetry install
cp config.yaml.example config.yaml   # then edit; file is gitignored
poetry run moxfield-import --help
task etl:build
```

Run the full sync on your machine with visible browsers: `task etl:run:headed` (same as `projects/etl/run_headed_local.sh`; see that script for CapSolver setup). Extra args after `--` are forwarded to the ETL module.

## Useful Task targets

| Task                           | Purpose                                               |
| ------------------------------ | ----------------------------------------------------- |
| `task etl:build`               | Build Docker image `mtg-glue-etl:local`               |
| `task etl:run:local`           | Shell in the ETL container                            |
| `task etl:run:headed`          | Full ETL on host (headed Playwright, not Docker)      |
| `task etl:upload-config`       | Upload `./config.yaml` to `s3://…/config/config.yaml` |
| `task etl:push-ecr`            | Build, tag `:latest`, push to ECR                     |
| `task etl:run:fargate`         | Start a one-off Fargate ETL task                      |
| `task infra:validate:mtg-glue` | `terraform validate` without remote backend           |
