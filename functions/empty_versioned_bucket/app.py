import os
import boto3

BUCKET_NAME = os.environ['BUCKET_NAME']

s3_resource = boto3.resource('s3')

def lambda_handler(_event, _context):
    if not BUCKET_NAME:
        return
        
    bucket = s3_resource.Bucket(BUCKET_NAME)
    [version.delete() for version in bucket.object_versions.all()]
