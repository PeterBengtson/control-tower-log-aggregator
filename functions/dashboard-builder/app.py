import os
import boto3
import cfnresponse
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


CONTROL_TOWER_BUCKET = os.environ['CONTROL_TOWER_BUCKET']
BUCKET_PREFIXES = os.environ['BUCKET_PREFIXES']
DASHBOARD_NAME = os.environ['DASHBOARD_NAME']
REGION = os.environ['REGION']
COMMON_DESTINATION_BUCKET = os.environ['COMMON_DESTINATION_BUCKET']
COMBINE_LOG_FILES_SM_ARN = os.environ['COMBINE_LOG_FILES_SM_ARN']

BODY_FIXED = """
    {
        "widgets": [
            {
                "height": 7,
                "width": 8,
                "y": 0,
                "x": 8,
                "type": "metric",
                "properties": {
                    "metrics": [
                        [ { "expression": "m1 / 60000", "label": "Execution Time", "id": "e1", "region": "<REGION>", "yAxis": "left" } ],
                        [ "AWS/States", "ExecutionTime", 
                            "StateMachineArn", "<COMBINE_LOG_FILES_SM_ARN>", 
                            { "region": "<REGION>", "id": "m1", "visible": false } ]
                    ],
                    "view": "timeSeries",
                    "stacked": false,
                    "region": "<REGION>",
                    "period": 86400,
                    "stat": "Maximum",
                    "yAxis": {
                        "left": {
                            "label": "Minutes",
                            "showUnits": false,
                            "min": 0
                        },
                        "right": {
                            "label": "",
                            "showUnits": false
                        }
                    },
                    "legend": {
                        "position": "bottom"
                    },
                    "title": "Log Processor Execution Time"
                }
            },
            {
                "height": 7,
                "width": 8,
                "y": 0,
                "x": 16,
                "type": "metric",
                "properties": {
                    "metrics": [
                        [ "AWS/States", "ExecutionsFailed", 
                            "StateMachineArn", "<COMBINE_LOG_FILES_SM_ARN>", 
                            { "region": "<REGION>" } ]
                    ],
                    "view": "timeSeries",
                    "stacked": false,
                    "region": "<REGION>",
                    "period": 86400,
                    "stat": "Sum",
                    "title": "Log Processor ExecutionsFailed",
                    "yAxis": {
                        "left": {
                            "min": 0
                        }
                    }
                }
            },
            {
                "height": 7,
                "width": 8,
                "y": 0,
                "x": 0,
                "type": "metric",
                "properties": {
                    "metrics": [
                        [ "AWS/States", "ConsumedCapacity", "ServiceMetric", "StateTransition", { "region": "<REGION>" } ]
                    ],
                    "view": "timeSeries",
                    "stacked": false,
                    "region": "<REGION>",
                    "period": 86400,
                    "stat": "Sum",
                    "title": "All State Transitions",
                    "yAxis": {
                        "left": {
                            "min": 0
                        }
                    }
                }
            },
            {
                "height": 6,
                "width": 8,
                "y": 7,
                "x": 0,
                "type": "metric",
                "properties": {
                    "view": "timeSeries",
                    "stacked": false,
                    "metrics": [
                        [ "AWS/S3", "BucketSizeBytes", 
                            "BucketName", "<COMMON_DESTINATION_BUCKET>", 
                            "StorageType", "StandardIAStorage",
                            { "period": 86400, "region": "<REGION>" } ]
                    ],
                    "region": "<REGION>",
                    "period": 300,
                    "yAxis": {
                        "left": {
                            "min": 0
                        }
                    },
                    "title": "Aggregated Logs Total Size"
                }
            },
            {
                "height": 6,
                "width": 8,
                "y": 7,
                "x": 8,
                "type": "metric",
                "properties": {
                    "view": "timeSeries",
                    "stacked": false,
                    "metrics": [
                        [ "AWS/S3", "NumberOfObjects", 
                            "BucketName", "<COMMON_DESTINATION_BUCKET>", 
                            "StorageType", "AllStorageTypes", 
                            { "period": 86400 } ]
                    ],
                    "region": "<REGION>",
                    "yAxis": {
                        "left": {
                            "min": 0
                        }
                    },
                    "title": "Aggregated Logs Total Number of Files"
                }
            },
            {
                "height": 6,
                "width": 8,
                "y": 7,
                "x": 16,
                "type": "metric",
                "properties": {
                    "metrics": [
                        [ { "expression": "m1 / m2", "label": "AverageSize", "id": "e1", "region": "<REGION>", "yAxis": "left" } ],
                        [ "AWS/S3", "BucketSizeBytes", 
                            "BucketName", "<COMMON_DESTINATION_BUCKET>", 
                            "StorageType", "StandardIAStorage", 
                            { "id": "m1", "visible": false, "region": "<REGION>" } ],
                        [ ".", "NumberOfObjects", ".", ".", ".", "AllStorageTypes", { "id": "m2", "visible": false, "region": "<REGION>" } ]
                    ],
                    "view": "timeSeries",
                    "stacked": false,
                    "region": "<REGION>",
                    "stat": "Maximum",
                    "period": 86400,
                    "title": "Average Aggregated Logs File size",
                    "yAxis": {
                        "left": {
                            "min": 0,
                            "showUnits": false,
                            "label": "Size"
                        },
                        "right": {
                            "showUnits": true,
                            "label": ""
                        }
                    },
                    "legend": {
                        "position": "hidden"
                    },
                    "liveData": false
                }
            }<BODY_VARIABLE>
        ]
    }
"""
BODY_FIXED = BODY_FIXED.replace('<REGION>', REGION)
BODY_FIXED = BODY_FIXED.replace('<COMBINE_LOG_FILES_SM_ARN>', COMBINE_LOG_FILES_SM_ARN)
BODY_FIXED = BODY_FIXED.replace('<COMMON_DESTINATION_BUCKET>', COMMON_DESTINATION_BUCKET)

BODY_VARIABLE = os.environ['BODY_VARIABLE']
FIRST_VARIABLE = os.environ['FIRST_VARIABLE']
REST_VARIABLE = os.environ['REST_VARIABLE']


s3 = boto3.client('s3')
cloudwatch = boto3.client('cloudwatch')


def lambda_handler(event, context):
    try:
        logger.info('Received event: %s', event)

        # Create or Update?
        request_type = event.get('RequestType', '')
        if request_type == 'Create' or request_type == 'Update':
            bucket_list = match_bucket_prefixes(BUCKET_PREFIXES)
            logger.info('Actual buckets: %s', bucket_list)

            body_variable = compute_body_variable(bucket_list, BODY_VARIABLE, FIRST_VARIABLE, REST_VARIABLE)
            logger.info('Body variable: %s', body_variable)
            body = BODY_FIXED.replace('<BODY_VARIABLE>', body_variable)
            logger.info('Body: %s', body)
            cloudwatch.put_dashboard(
                DashboardName=DASHBOARD_NAME,
                DashboardBody=body
            )

        elif request_type == 'Delete':
            cloudwatch.delete_dashboards(DashboardNames=[DASHBOARD_NAME])

        # Succeed
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
        # Add a log statement for successful completion
        logger.info('Function execution completed successfully')

    # If anything at all fails, just fail and return
    except Exception as e:
        logger.error('Error occurred: %s', str(e))
        response_data = {'Error': 'Error occurred: {}'.format(str(e))}
        cfnresponse.send(event, context, cfnresponse.FAILED, response_data)


def match_bucket_prefixes(bucket_names):
    all_buckets = s3.list_buckets()

    # Split bucket name prefixes and filter out any empty strings
    bucket_name_prefixes = list(filter(None, bucket_names.split(',')))
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

    return result


def compute_body_variable(bucket_list, body_variable, first_variable, rest_variable):
    if len(bucket_list) == 0:
        return ''
        
    replacement = first_variable.replace('<BUCKET_NAME>', CONTROL_TOWER_BUCKET)
    if len(bucket_list) > 1:
        replacement += ','
    body_variable = body_variable.replace('<FIRST_VARIABLE>', replacement)

    rest_lines = []
    for bucket in bucket_list:
        rest_lines.append(rest_variable.replace('<BUCKET_NAME>', bucket))
                          
    body_variable = body_variable.replace('<REST_VARIABLE>', ','.join(rest_lines))

    return ',' + body_variable
