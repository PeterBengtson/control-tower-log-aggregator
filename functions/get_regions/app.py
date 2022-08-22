from calendar import month
import os
import boto3

client = boto3.client('s3')

def lambda_handler(data, _context):
    bucket_name = data['bucket_name']
    log_type = data['log_type']
    prefix = data['account_prefix'] + log_type + '/'

    response = client.list_objects_v2(
        Bucket=bucket_name,
        Delimiter='/',
        Prefix=prefix
    )

    common_prefixes = list(map(lambda x: x['Prefix'], response.get('CommonPrefixes', [])))
    print(common_prefixes)
    return common_prefixes
