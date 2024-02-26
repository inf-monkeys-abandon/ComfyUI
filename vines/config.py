import os

REDIS_URL = os.getenv('REDIS_URL')

S3_ACCESS_KEY = os.environ.get('S3_ACCESS_KEY')
S3_SECRET_KEY = os.environ.get('S3_SECRET_KEY')
S3_MODEL_BUCKET = os.environ.get('S3_MODEL_BUCKET', 'models')
S3_PUBLIC_BUCKET = os.environ.get('S3_PUBLIC_BUCKET', 'public')
S3_ENDPOINT = os.environ.get('S3_ENDPOINT', '')
S3_REGION = os.environ.get('S3_REGION', '')
OSS_BASE_URL = os.environ.get('OSS_BASE_URL', '')
