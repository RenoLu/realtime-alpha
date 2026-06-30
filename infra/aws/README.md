# infra/aws — the AWS lakehouse architecture (mirror, not the running demo)

This Terraform describes the **AWS-native** version of the data layer: an **S3** bucket
holding the same Hive-partitioned datasets, an **Iceberg** table in the **Glue** catalog,
and an **Athena** workgroup to query it — the cloud analog of the always-on
R2 + Parquet + DuckDB path the live demo actually runs.

**It is an artifact, not a running cost.** The free R2 path is what serves the demo 24/7;
this module exists to show the AWS architecture and is **applied on demand, then destroyed**.

```bash
terraform -chdir=infra/aws init        # downloads the AWS provider
terraform -chdir=infra/aws validate    # checked in CI; provisions nothing
terraform -chdir=infra/aws plan        # preview (needs AWS creds)
terraform -chdir=infra/aws apply        # demo on AWS...
terraform -chdir=infra/aws destroy      # ...then tear down to stay at $0
```

The Python app writes the identical Parquet layout to either backend (R2 or S3) via the
S3-compatible `R2Writer`, so the same data lands in either store with no code change.
