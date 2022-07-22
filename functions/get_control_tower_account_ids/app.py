from calendar import month
import os
import boto3

ORG_ID = os.environ['ORG_ID']

client = boto3.client('s3')

def lambda_handler(data, _context):
    bucket_name = data['ct_bucket_name']

    print(f"Checking existence of {bucket_name}...")
    client.head_bucket(Bucket=bucket_name)
    print("Bucket exists.")

    response = client.list_objects_v2(
        Bucket=bucket_name,
        Delimiter='/',
        Prefix=f'{ORG_ID}/AWSLogs/'
    )

    account_prefixes = list(map(lambda x: x['Prefix'], response['CommonPrefixes']))
    print(account_prefixes)
    return account_prefixes
