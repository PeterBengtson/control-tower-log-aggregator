import os
import json
import boto3

TMP_LOGS_BUCKET_NAME = os.environ['TMP_LOGS_BUCKET_NAME']

s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')

def lambda_handler(data, _context):

    bucket_name = data['bucket_name']
    files = get_files(data['files'])

    if not files:
        print("No files to delete.")
        return

    bucket = s3_resource.Bucket(bucket_name)
    [version.delete() for version in bucket.object_versions.all() if version.object_key in files]

    if isinstance(data['files'], str):
        s3_client.delete_object(
            Bucket=TMP_LOGS_BUCKET_NAME, 
            Key=data['files']
        )


def get_files(thing):
    if isinstance(thing, list):
        return thing
    
    response = s3_client.get_object(
        Bucket=TMP_LOGS_BUCKET_NAME,
        Key=thing,
    )
    files = json.loads(response['Body'].read())
    return files
