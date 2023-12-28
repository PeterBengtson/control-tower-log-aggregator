import os
import json
import boto3
from botocore.exceptions import ClientError


TMP_LOGS_BUCKET_NAME = os.environ['TMP_LOGS_BUCKET_NAME']

s3_client = boto3.client('s3')


def lambda_handler(data, _context):
    bucket_name = data['bucket_name']
    files = get_files(data['files'])

    if not files:
        print("No files to delete. Returning.")
        return

    n_files = len(files)
    print(f"{n_files} files to delete...")

    # Prepare a list of objects to delete along with their versions
    objects_to_delete = []
    for file_key in files:
        try:
            # Handle pagination
            paginator = s3_client.get_paginator('list_object_versions')
            page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=file_key)
            for page in page_iterator:
                for version in page.get('Versions', []) + page.get('DeleteMarkers', []):
                    objects_to_delete.append({'Key': file_key, 'VersionId': version['VersionId']})
        except ClientError as e:
            print(f"An error occurred: {e}")
            return
        
    print(f"{len(objects_to_delete)} objects to delete...")

    # Delete objects in batches
    try:
        total_deleted = 0
        for i in range(0, len(objects_to_delete), 1000):  # S3 delete_objects API allows up to 1000 keys at once
            batch = objects_to_delete[i:i+1000]
            if batch:  # Ensure there are objects to delete
                response = s3_client.delete_objects(
                    Bucket=bucket_name,
                    Delete={
                        'Objects': batch,
                        'Quiet': False  # Set Quiet to False to get the list of deleted objects
                    }
                )
                deleted_items = response.get('Deleted', [])
                errors = response.get('Errors', [])
                total_deleted += len(deleted_items)
                print(f"Deleted {len(deleted_items)} items.")
                if errors:
                    print(f"Errors encountered: {errors}")
    except ClientError as e:
        print(f"An error occurred during deletion: {e}")

    if isinstance(data['files'], str):
        try:
            s3_client.delete_object(
                Bucket=TMP_LOGS_BUCKET_NAME,
                Key=data['files']
            )
        except ClientError as e:
            print(f"An error occurred when deleting the manifest file: {e}")


def get_files(thing):
    if isinstance(thing, list):
        return thing

    try:
        response = s3_client.get_object(
            Bucket=TMP_LOGS_BUCKET_NAME,
            Key=thing,
        )
        files = json.loads(response['Body'].read())
        return files
    except ClientError as e:
        print(f"An error occurred when retrieving the file list: {e}")
        return []

