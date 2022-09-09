import boto3
import os
import json

FIVE_MB = 5 * 1024 * 1024

TMP_LOGS_BUCKET_NAME = os.environ['TMP_LOGS_BUCKET_NAME']
DEST_LOGS_BUCKET_NAME = os.environ['DEST_LOGS_BUCKET_NAME']
AGGREGATION_REGIONS = os.environ['AGGREGATION_REGIONS'].split(',')

# Create the 5MB file at lambda startup time
filler_file_path = f'/tmp/five_mb_file'
with open(filler_file_path, 'wb') as f:
    f.seek(FIVE_MB)
    f.write(b'0')

s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')


def lambda_handler(data, _context):
    source_bucket_name = data['bucket_name']
    dest_bucket_name = DEST_LOGS_BUCKET_NAME or source_bucket_name
    final_key = data['key']
    log_files = get_files(data['files'])
    main_log_type = data.get('log_type')   # This is only true for a main log file

    if not log_files:
        print("No files specified")
        return

    # As multipart uploads require that all files but the last one be >= 5MB, we need to 
    # upload a file of this size to the scratchpad temp bucket as a starting point. The 
    # key used is the same as that of the final merged file.
    with open(filler_file_path, 'rb') as f:
        s3_client.upload_fileobj(f, TMP_LOGS_BUCKET_NAME, final_key)

    # We now perform a series of two-file multipart uploads, one for each log file we need to
    # aggregate.
    for log_file in log_files:

        if not aggregatable(log_file, main_log_type):
            continue

        # Initiate the multipart upload
        mpu = s3_client.create_multipart_upload(Bucket=TMP_LOGS_BUCKET_NAME, Key=final_key)
            
        part_responses = []
        # The following is best done in a bucket without versioning enabled, unless you want 
        # an enormous number of versions with delete markers after the operation.
        for n, copy_key in enumerate([final_key, log_file]):
            part_number = n + 1
            copy_response = s3_client.upload_part_copy(
                Bucket=TMP_LOGS_BUCKET_NAME,
                Key=final_key,
                CopySource={
                    'Bucket': TMP_LOGS_BUCKET_NAME if n == 0 else source_bucket_name, 
                    'Key': copy_key
                },
                PartNumber=part_number,
                UploadId=mpu['UploadId']
            )

            part_responses.append(
                {
                    'ETag': copy_response['CopyPartResult']['ETag'], 
                    'PartNumber':part_number
                }
            )

        # Finish the multipart upload for this log file to the temp bucket.
        s3_client.complete_multipart_upload(
            Bucket=TMP_LOGS_BUCKET_NAME,
            Key=final_key,
            MultipartUpload={'Parts': part_responses},
            UploadId=mpu['UploadId']
        )

    # All log files have now been added to the dummy file in the temp bucket.
    # Get the size of the result (which includes the +5MB dummy bytes)
    total_bytes = s3_resource.Object(TMP_LOGS_BUCKET_NAME, final_key).content_length

    # Initiate the final move of the result from the temp bucket to the chosen destination 
    # bucket, and also store the result using the Standard Infrequent Access storage class.
    mpu = s3_client.create_multipart_upload(
        Bucket=dest_bucket_name, 
        Key=final_key,
        StorageClass='STANDARD_IA'
    )            
    # All we need here is a single part consisting of everything except the filler bytes.
    response = s3_client.upload_part_copy(
        Bucket=dest_bucket_name,
        CopySource={'Bucket': TMP_LOGS_BUCKET_NAME, 'Key': final_key},
        Key=final_key,
        PartNumber=1,
        UploadId=mpu['UploadId'],
        CopySourceRange=f'bytes={FIVE_MB}-{total_bytes-1}'
    )
    # Do the upload
    s3_client.complete_multipart_upload(
        Bucket=dest_bucket_name,
        Key=final_key,
        MultipartUpload={
            'Parts': [
                {
                    'ETag': response['CopyPartResult']['ETag'], 
                    'PartNumber': 1
                }
            ]
        },
        UploadId=mpu['UploadId']
    )
    # The final result is now in place in the destination bucket.

    # Delete the versionless merged version from the temp bucket
    s3_client.delete_object(
        Bucket=TMP_LOGS_BUCKET_NAME,
        Key=final_key,
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


def aggregatable(log_file, main_log_type):
    if not main_log_type:
        return True
    if not AGGREGATION_REGIONS:
        return True
    for region in AGGREGATION_REGIONS:
        if region in log_file:
            return True
    return False

