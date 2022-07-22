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

    # we need to have a garbage/dummy file with size > 5MB
    # so we create and upload this
    # this key will also be the key of final merged file
    with open(dummy_file_path, 'wb') as f:
        # slightly > 5MB
        f.seek(1024 * 5200) 
        f.write(b'0')

    with open(dummy_file_path, 'rb') as f:
        s3_client.upload_fileobj(f, TMP_LOGS_BUCKET_NAME, merged_key)

    os.remove(dummy_file_path)

    # get the number of bytes of the garbage/dummy-file
    # needed to strip out these garbage/dummy bytes from the final merged file
    bytes_garbage = s3_resource.Object(TMP_LOGS_BUCKET_NAME, merged_key).content_length

    # for each small file you want to concat
    for key_mini_file in input_files:

        # initiate multipart upload with merged.json object as target
        mpu = s3_client.create_multipart_upload(Bucket=TMP_LOGS_BUCKET_NAME, Key=merged_key)
            
        part_responses = []
        # Perform multipart copy where the final file is the first part 
        # and the small file is the second part. Yes, there will be one
        # multipart upload for each small file, since all files but the
        # last one must be > 5MB. For this reason, this is best done in
        # a bucket without versioning enabled, unless you want an enormous
        # number of versions with delete markers after the operation.
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

        # complete the multipart upload
        # content of merged will now be merged.json + mini file
        response = s3_client.complete_multipart_upload(
            Bucket=TMP_LOGS_BUCKET_NAME,
            Key=merged_key,
            MultipartUpload={'Parts': part_responses},
            UploadId=mpu['UploadId']
        )

    # get the number of bytes from the final merged file
    bytes_merged = s3_resource.Object(TMP_LOGS_BUCKET_NAME, merged_key).content_length

    # initiate a new multipart upload, this time to the destination bucket
    mpu = s3_client.create_multipart_upload(
        Bucket=dest_bucket_name, 
        Key=merged_key,
        StorageClass='STANDARD_IA'
    )            
    # do a single copy from the merged file specifying byte range where the 
    # dummy/garbage bytes are excluded
    response = s3_client.upload_part_copy(
        Bucket=dest_bucket_name,
        CopySource={'Bucket': TMP_LOGS_BUCKET_NAME, 'Key': merged_key},
        Key=merged_key,
        PartNumber=1,
        UploadId=mpu['UploadId'],
        CopySourceRange='bytes={}-{}'.format(bytes_garbage, bytes_merged-1)
    )
    # complete the multipart upload
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
