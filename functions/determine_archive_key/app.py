from calendar import month
import os
import json
import boto3

TMP_LOGS_BUCKET_NAME = os.environ['TMP_LOGS_BUCKET_NAME']
DEST_LOGS_BUCKET_NAME = os.environ['DEST_LOGS_BUCKET_NAME']
FINAL_AGGREGATION_PREFIX = os.environ['FINAL_AGGREGATION_PREFIX']

s3_client = boto3.client('s3')


def lambda_handler(data, _context):

    # If there already is an explicit key, just return it
    key = data.get('key')
    if key:
        return key

    # Get the files and their base names. Find the common prefix, if any.
    files = []
    for file in get_files(data['files']):
        base_name = (file.split('/')[-1]).split('.')[0]
        files.append(base_name)
    prefix = os.path.commonprefix(files).strip('-_')
    if not prefix:
        # No common prefix, use what we have
        prefix = data.get('log_type', 'Aggregated-Logs')

    # If this is an S3 access log bucket, there's no gzip encryption
    bucket_name = data['bucket_name']
    only_gz = 's3-access-logs' not in bucket_name

    # If we have a destination bucket, the prefix is the origin bucket name
    if DEST_LOGS_BUCKET_NAME:
        FINAL_AGGREGATION_PREFIX = bucket_name

    year, month, day = data['date'].split('-')  
    prefix = f"{FINAL_AGGREGATION_PREFIX}/{year}/{month}/{day}/{prefix}"
    if only_gz:
        prefix += '.gz'
    
    print(f"Prefix: {prefix}")
    return prefix


def get_files(thing):
    if isinstance(thing, list):
        return thing
    
    response = s3_client.get_object(
        Bucket=TMP_LOGS_BUCKET_NAME,
        Key=thing,
    )
    files = json.loads(response['Body'].read())
    return files
