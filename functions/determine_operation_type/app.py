import os
import json
import re
import boto3

TMP_LOGS_BUCKET_NAME = os.environ['TMP_LOGS_BUCKET_NAME']
MIN_SIZE = int(os.environ['MIN_SIZE'])

s3_client = boto3.client('s3')


def lambda_handler(data, _context):
    # Get the files.
    bucket_name = data['bucket_name']
    files = get_files(data['files'])

    # Check for an empty file list
    if len(files) == 0:
        return "none"

    # Check file sizes.
    if all_files_large(bucket_name, files):
        return "copy_all"

    # Check for AWS account ID pattern in all filenames.
    if all(re.search(r'\b\d{12}\b', file) for file in files):
        return "aggregate_per_account"

    # Check for hourly pattern in all filenames.
    if all(re.search(r'\/(0[0-9]|1[0-9]|2[0-3])\/', file) for file in files):
        return "aggregate_per_hour"

    # If none of the conditions are met, return "aggregate_all".
    return "aggregate_all"


def all_files_large(bucket_name, files):
    for file in files:
        # Get file size from S3
        response = s3_client.head_object(Bucket=bucket_name, Key=file)
        size = response['ContentLength']

        if size < MIN_SIZE:
            return False
    return True


def get_files(thing):
    if isinstance(thing, list):
        return thing
    
    response = s3_client.get_object(
        Bucket=TMP_LOGS_BUCKET_NAME,
        Key=thing,
    )
    files = json.loads(response['Body'].read())
    return files
