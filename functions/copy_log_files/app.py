import boto3
import os
import json
import time
import logging

# Configure the logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)


TMP_LOGS_BUCKET_NAME = os.environ['TMP_LOGS_BUCKET_NAME']
DEST_LOGS_BUCKET_NAME = os.environ['DEST_LOGS_BUCKET_NAME']


s3_client = boto3.client('s3')


def lambda_handler(data, context):
    date = data['date'].replace("-", "/")
    source_bucket_name = data['bucket_name']
    dest_bucket_name = DEST_LOGS_BUCKET_NAME or source_bucket_name
    log_files = get_files(data['files'])

    # Access continuationMarker from the nested combineMainLogsResult if it exists
    combine_main_logs_result = data.get('combineMainLogsResult', {})
    continuation_marker = combine_main_logs_result.get('continuationMarker', 0)

    if continuation_marker > 0:
        logger.info(f"Continuing operation from index {continuation_marker}")

    if not log_files:
        logger.info("No files specified")
        return {'status': 'no-op'}
    
    start_time = time.time()
    remaining_time = context.get_remaining_time_in_millis() / 1000.0  # Convert to seconds

    # Resume or start the copy process
    for index, log_file in enumerate(log_files[continuation_marker:], start=continuation_marker):

        # Check if there is enough time left to process another file
        elapsed_time = time.time() - start_time
        if (remaining_time - elapsed_time) < 120:  # Less than 2 minutes left
            logger.info(f"Lambda might time out, returning continuationMarker for next invocation: {index}")
            return {'continuationMarker': index}  # Return the index of the next file to process

        # Get the basename of the source file
        base_name = os.path.basename(log_file)

        # Define the destination key
        destination_key = f"{source_bucket_name}/{date}/{base_name}"

        # Copy the file from the source to the destination using boto3.copy_object
        try:
            s3_client.copy_object(
                Bucket=dest_bucket_name,
                Key=destination_key,
                CopySource={'Bucket': source_bucket_name, 'Key': log_file},
                StorageClass='STANDARD_IA'
            )
            logger.info(f"Successfully copied {log_file} to {dest_bucket_name}/{destination_key}")

        except Exception as e:
            logger.error(f"Failed to copy {log_file}: {str(e)}")
            # Depending on the requirements, you might want to raise the exception,
            # return an error status, or handle it in some other way.
            # For this example, we'll skip the rest of the files and return an error.
            return {'status': 'error', 'message': str(e)}

    # All files have now been copied. Return status of done.
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
