variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "S3 bucket for the Iceberg lakehouse"
  type        = string
  default     = "rta-lakehouse"
}

variable "database_name" {
  description = "Glue catalog database"
  type        = string
  default     = "realtime_alpha"
}
