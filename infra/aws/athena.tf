resource "aws_athena_workgroup" "rta" {
  name = "realtime-alpha"

  configuration {
    result_configuration {
      output_location = "s3://${aws_s3_bucket.lakehouse.bucket}/_athena-results/"
    }
  }
}
