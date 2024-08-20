output "s3_bucket_name" {
  value = aws_s3_bucket.aiden_bucket.bucket
}

output "rds_endpoint" {
  value = aws_db_instance.aiden_db.endpoint
}

output "elasticache_endpoint" {
  value = aws_elasticache_cluster.aiden_redis.cache_nodes[0].address
}

output "elasticbeanstalk_environment_url" {
  value = aws_elastic_beanstalk_environment.aiden_env.endpoint_url
}
