# The S3 equivalent of the R2 lakehouse bucket. Private; raw features expire to keep it cheap.

resource "aws_s3_bucket" "lakehouse" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_public_access_block" "lakehouse" {
  bucket                  = aws_s3_bucket.lakehouse.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "lakehouse" {
  bucket = aws_s3_bucket.lakehouse.id

  rule {
    id     = "expire-raw-features"
    status = "Enabled"
    filter {
      prefix = "features/"
    }
    expiration {
      days = 90
    }
  }
}
