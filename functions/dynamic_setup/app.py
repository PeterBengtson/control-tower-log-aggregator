import boto3
from datetime import date
from datetime import timedelta

def lambda_handler(data, _context):
    s3 = boto3.client('s3')
    all_buckets = s3.list_buckets()

    # Split bucket name prefixes and filter out any empty strings
    bucket_name_prefixes = list(filter(None, data['bucket_names'].split(',')))
    result = []

    # If there are no valid prefixes, skip the matching process
    if bucket_name_prefixes:
        for bucket in all_buckets['Buckets']:
            for bucket_name_prefix in bucket_name_prefixes:
                if bucket['Name'].startswith(bucket_name_prefix.strip()):
                    result.append(bucket['Name'])
    else:
        # If we have no valid prefixes (an empty string was passed), we won't add any buckets to result
        pass

    data['bucket_names'] = result

    explicit_date = data.get('execution_input', {}).get('date')
    if explicit_date:
        data['date'] = explicit_date
    else:
        today = date.today()
        yesterday = today - timedelta(days=1)
        data['date'] = str(yesterday)
        
    # If we have specified an overriding input bucket name, use that bucket instead of the standard
    # Control Tower log bucket. This means we probably also have an explicit date and that we are
    # processing historical data, so the auxiliary log bucket processing will be skipped by setting
    # 'bucket_names' to the empty list.
    overriding_bucket_name = data.get('execution_input', {}).get('bucket_name')
    if overriding_bucket_name:
        data['bucket_name'] = overriding_bucket_name
        data['bucket_names'] = []        

    return data
