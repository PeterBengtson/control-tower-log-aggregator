from calendar import month
from curses import raw
import os
import json
import boto3
import random

TMP_LOGS_BUCKET_NAME = os.environ['TMP_LOGS_BUCKET_NAME']

s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')

def lambda_handler(data, _context):
    bucket_name = data['bucket_name']
    prefixes = data['region_prefixes']
    ct_log_type = data.get('ct_log_type', '')
    date = data['date']
    year, month, day = date.split('-')
    only_gz = True

    print(f"Getting files...")
    objects = []
    for raw_prefix in prefixes:
        prefix = f'{raw_prefix}{year}/{month}/{day}'
        objects.extend(list(s3_resource.Bucket(bucket_name).objects.filter(Prefix=prefix)))

    print(f"Total number of files: {len(objects)}")

    month_trimmed = month.lstrip('0')
    day_trimmed = day.lstrip('0')
    date_forms = [
        f'{year}-{month}-{day}',
        f'{year}-{month_trimmed}-{day_trimmed}',
        f'{year}/{month}/{day}/',
        f'{year}/{month_trimmed}/{day_trimmed}/',
        f'{year}{month}{day}',
    ]
    objects = list(filter(lambda x: is_wanted(x.key, date_forms, only_gz), objects))
    print(f"Total number of interesting files: {len(objects)}")

    files = list(map(lambda x: x.key, objects))
    return save_files(files, bucket_name, ct_log_type, date)


def is_wanted(key, date_forms, only_gz):
    if only_gz and not key.endswith('.gz'):
        return False
    for f in date_forms:
        if f in key:
            return True
    return False


def save_files(files, bucket_name, prefix, date):
    # If the number of files is small, then just return the file list as is
    if len(files) < 100:
        return files

    # For a long list, store it in a file and return the key to it
    noise = random.randint(100000000, 999999999)
    file_list_key = f'{bucket_name}-{prefix}-{date}-{noise}.json' if prefix else f'{bucket_name}-{date}-{noise}.json'

    response = s3_client.put_object(
        Body=json.dumps(files),
        Bucket=TMP_LOGS_BUCKET_NAME,
        Key=file_list_key,
    )

    return file_list_key
