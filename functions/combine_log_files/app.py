import boto3
import os
import json

TMP_LOGS_BUCKET_NAME = os.environ['TMP_LOGS_BUCKET_NAME']
DEST_LOGS_BUCKET_NAME = os.environ['DEST_LOGS_BUCKET_NAME']

s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')


def lambda_handler(data, _context):

    source_bucket_name = data['bucket_name']
    dest_bucket_name = DEST_LOGS_BUCKET_NAME or source_bucket_name
    merged_key = data['key']
    input_files = get_files(data['files'])

    if not input_files:
        print("No files specified")
        return

    dummy_file = 'dummy_file'
    dummy_file_path = f'/tmp/{dummy_file}'

    s3_client = boto3.client('s3')
    s3_resource = boto3.resource('s3')

    # The beauty of copying this way is that it is done entirely within S3, without actually
    # down- or uploading anything. However, as multipart uploads require that all files but 
    # the last one be > 5MB, we need to upload a file of this size to the scratchpad temp bucket 
    # as a starting point. The key used is the same as that of the final merged file.
    with open(dummy_file_path, 'wb') as f:
        # slightly > 5MB
        f.seek(1024 * 5200) 
        f.write(b'0')

    with open(dummy_file_path, 'rb') as f:
        s3_client.upload_fileobj(f, TMP_LOGS_BUCKET_NAME, merged_key)

    os.remove(dummy_file_path)

    # This is the actual size of the dummy file. We need it later to strip away the
    # dummy bytes from the final merged file.
    bytes_garbage = s3_resource.Object(TMP_LOGS_BUCKET_NAME, merged_key).content_length

    # We now perform a series of two-file multipart uploads, one for each log file we need to
    # aggregate. We could do several at a time if all of them were > 5MB (except the last one);
    # that would be an optimisation worth making, especially since log files do not need to be
    # concatenated in order. But this version simply does them one at a time.
    for key_mini_file in input_files:

        # Initiate the multipart upload
        mpu = s3_client.create_multipart_upload(Bucket=TMP_LOGS_BUCKET_NAME, Key=merged_key)
            
        part_responses = []
        # The following is best done in a bucket without versioning enabled, unless you want 
        # an enormous number of versions with delete markers after the operation.
        for n, copy_key in enumerate([merged_key, key_mini_file]):
            part_number = n + 1
            copy_response = s3_client.upload_part_copy(
                Bucket=TMP_LOGS_BUCKET_NAME,
                Key=merged_key,
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
        response = s3_client.complete_multipart_upload(
            Bucket=TMP_LOGS_BUCKET_NAME,
            Key=merged_key,
            MultipartUpload={'Parts': part_responses},
            UploadId=mpu['UploadId']
        )

    # All log files have now been added to the dummy file in the temp bucket.
    # Get the size of the result (which includes the +5MB dummy bytes)
    bytes_merged = s3_resource.Object(TMP_LOGS_BUCKET_NAME, merged_key).content_length

    # Initiate the final move of the result from the temp bucket to the chosen destination 
    # bucket, and also store the result using the Standard Infrequent Access storage class.
    mpu = s3_client.create_multipart_upload(
        Bucket=dest_bucket_name, 
        Key=merged_key,
        StorageClass='STANDARD_IA'
    )            
    # All we need here is a single part consisting of everything except the dummy bytes.
    response = s3_client.upload_part_copy(
        Bucket=dest_bucket_name,
        CopySource={'Bucket': TMP_LOGS_BUCKET_NAME, 'Key': merged_key},
        Key=merged_key,
        PartNumber=1,
        UploadId=mpu['UploadId'],
        CopySourceRange='bytes={}-{}'.format(bytes_garbage, bytes_merged-1)
    )
    # Do the upload
    response = s3_client.complete_multipart_upload(
        Bucket=dest_bucket_name,
        Key=merged_key,
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
    response = s3_client.delete_object(
        Bucket=TMP_LOGS_BUCKET_NAME,
        Key=merged_key,
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
