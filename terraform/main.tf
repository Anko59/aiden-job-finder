provider "aws" {
  region = "us-west-2"
}

resource "aws_s3_bucket" "aiden_bucket" {
  bucket = "aiden-app-bucket"
  acl    = "private"

  tags = {
    Name        = "AidenAppBucket"
    Environment = "Production"
  }
}


# Security Group for EC2
resource "aws_db_instance" "aiden_db" {
  allocated_storage    = 20
  storage_type         = "gp2"
  engine               = "postgres"
  engine_version       = "14.0"
  instance_class       = "db.t3.micro"
  name                 = "aiden_db"
  username             = var.db_username
  password             = var.db_password
  parameter_group_name = "default.postgres14"
  skip_final_snapshot  = true

  vpc_security_group_ids = [aws_security_group.db_sg.id]

  tags = {
    Name        = "AidenAppDatabase"
    Environment = "Production"
  }
}


resource "aws_elasticache_cluster" "aiden_redis" {
  cluster_id           = "aiden-redis-cluster"
  engine               = "redis"
  node_type            = "cache.t2.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis3.2"

  tags = {
    Name        = "AidenAppRedis"
    Environment = "Production"
  }
}

# ECR Repository for Django
resource "aws_ecr_repository" "django_repo" {
  name = "aiden-app-django"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "AidenAppDjangoRepo"
    Environment = "Production"
  }
}

# ECR Repository for Recommender
resource "aws_ecr_repository" "recommender_repo" {
  name = "aiden-app-recommender"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "AidenAppRecommenderRepo"
    Environment = "Production"
  }
}

# Security Group for Database
resource "aws_security_group" "db_sg" {
  name        = "allow-postgres"
  description = "Allow PostgreSQL traffic"
  vpc_id      = var.vpc_id

  ingress {
    description = "PostgreSQL"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Security Group for Elastic Beanstalk
resource "aws_elastic_beanstalk_application" "aiden_app" {
  name        = "aiden-app"
  description = "Aiden Django Application"
}

# Elastic Beanstalk Environment
resource "aws_elastic_beanstalk_environment" "aiden_env" {
  name                = "aiden-env"
  application         = aws_elastic_beanstalk_application.aiden_app.name
  solution_stack_name = "64bit Amazon Linux 2 v3.1.3 running Docker"

  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "DATABASE_URL"
    value     = "postgres://${var.db_username}:${var.db_password}@${aws_db_instance.aiden_db.address}:${aws_db_instance.aiden_db.port}/${aws_db_instance.aiden_db.name}"
  }

  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "AWS_ACCESS_KEY_ID"
    value     = var.aws_access_key_id
  }

  setting {
    namespace = "aws:elasticbeanstalk:application:environment"
    name      = "AWS_SECRET_ACCESS_KEY"
    value     = var.aws_secret_access_key
  }
}
