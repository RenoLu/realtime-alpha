# Glue catalog + an Iceberg table over the outcomes dataset — the AWS analog of the
# DuckDB-over-Parquet query layer, queryable by Athena.

resource "aws_glue_catalog_database" "lakehouse" {
  name = var.database_name
}

resource "aws_glue_catalog_table" "outcomes" {
  name          = "outcomes"
  database_name = aws_glue_catalog_database.lakehouse.name
  table_type    = "EXTERNAL_TABLE"

  open_table_format_input {
    iceberg_input {
      metadata_operation = "CREATE"
      version            = "2"
    }
  }

  storage_descriptor {
    location = "s3://${aws_s3_bucket.lakehouse.bucket}/outcomes/"

    columns {
      name = "symbol"
      type = "string"
    }
    columns {
      name = "strategy_id"
      type = "string"
    }
    columns {
      name = "horizon_s"
      type = "int"
    }
    columns {
      name = "yhat"
      type = "double"
    }
    columns {
      name = "realized_return"
      type = "double"
    }
    columns {
      name = "hit"
      type = "boolean"
    }
    columns {
      name = "abs_error"
      type = "double"
    }
    columns {
      name = "confidence"
      type = "double"
    }
    columns {
      name = "ref_price"
      type = "double"
    }
    columns {
      name = "realized_price"
      type = "double"
    }
    columns {
      name = "pred_ts"
      type = "bigint"
    }
    columns {
      name = "scored_ts"
      type = "bigint"
    }
    columns {
      name = "model_ver"
      type = "string"
    }
  }
}
