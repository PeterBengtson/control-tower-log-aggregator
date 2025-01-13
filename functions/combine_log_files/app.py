import boto3
import os
import json
import time
import logging

# Configure the logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)


FIVE_MB = 5 * 1024 * 1024

TMP_LOGS_BUCKET_NAME = os.environ['TMP_LOGS_BUCKET_NAME']
DEST_LOGS_BUCKET_NAME = os.environ['DEST_LOGS_BUCKET_NAME']

AGGREGATION_REGIONS = os.environ.get('AGGREGATION_REGIONS', "[]")
AGGREGATION_REGIONS = json.loads(AGGREGATION_REGIONS.replace("'", '"'))


# Create the 5MB file at lambda startup time
filler_file_path = f'/tmp/five_mb_file'
with open(filler_file_path, 'wb') as f:
    f.seek(FIVE_MB - 1)
    f.write(b'\x00')

s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')


def lambda_handler(data, context):
    source_bucket_name = data['bucket_name']
    dest_bucket_name = DEST_LOGS_BUCKET_NAME or source_bucket_name
    final_key = data['key']
    log_files = get_files(data['files'])
    main_log_type = data.get('log_type')   # This is only true for a main log file

    # Access continuationMarker from the nested combineMainLogsResult if it exists
    combine_main_logs_result = data.get('combineMainLogsResult', {})
    continuation_marker = combine_main_logs_result.get('continuationMarker', 0)

    if not log_files:
        logger.info("No files specified")
        return {'status': 'no-op'}
    
    start_time = time.time()
    remaining_time = context.get_remaining_time_in_millis() / 1000.0  # Convert to seconds

    # if not main_log_type or continuation_marker != 0:
    #     logger.info(f"Final key: {final_key}")
    #     logger.info(f"Number of aggregate files: {len(log_files)}")
    #     logger.info(f"Continuation marker: {continuation_marker}")

    # As multipart uploads require that all files but the last one be >= 5MB, we need to 
    # upload a file of this size to the scratchpad temp bucket as a starting point. The 
    # key used is the same as that of the final merged file.
    if continuation_marker == 0:  # Only upload the filler file if starting from the beginning
        with open(filler_file_path, 'rb') as f:
            s3_client.upload_fileobj(f, TMP_LOGS_BUCKET_NAME, final_key)

    # We now perform a series of two-file multipart uploads, one for each log file we need to
    # aggregate.
    # Resume or start the aggregation process
    for index, log_file in enumerate(log_files[continuation_marker:], start=continuation_marker):
        # if continuation_marker != 0:
        #     logger.info(f"Index: {index}, Log file: {log_file}")

        # Check if there is enough time left to process another file
        elapsed_time = time.time() - start_time
        if (remaining_time - elapsed_time) < 120:  # Less than 2 minutes left
            logger.info(f"Lambda might time out, returning continuationMarker for next invocation: {index}")
            return {'continuationMarker': index}  # Return the index of the next file to process

        if not aggregatable(log_file, main_log_type):
            continue

        # if not main_log_type or continuation_marker != 0:
        #     logger.info(f"Aggregating index {index}: {log_file}...")

        # Start timing the aggregation for this file
        # file_start_time = time.time()

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
                    'PartNumber': part_number
                }
            )

        # Finish the multipart upload for this log file to the temp bucket.
        s3_client.complete_multipart_upload(
            Bucket=TMP_LOGS_BUCKET_NAME,
            Key=final_key,
            MultipartUpload={'Parts': part_responses},
            UploadId=mpu['UploadId']
        )

        # Calculate and print the time taken to aggregate this file
        # file_elapsed_time = time.time() - file_start_time
        # if not main_log_type or continuation_marker != 0:
        #     logger.info(f"Time elapsed: {file_elapsed_time} seconds")


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

    # Return status
    return {'status': 'done'}


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

