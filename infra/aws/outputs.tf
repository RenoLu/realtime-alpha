output "bucket" {
  value = aws_s3_bucket.lakehouse.bucket
}

output "glue_database" {
  value = aws_glue_catalog_database.lakehouse.name
}

output "athena_workgroup" {
  value = aws_athena_workgroup.rta.name
}
