import boto3
from datetime import datetime, timedelta

def lambda_handler(data, _context):
    start_date_str = data['start_date']
    end_date_str = data['end_date']
    datelist = []

    # Convert string dates to datetime objects
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

    # Generate all dates from start_date to end_date, inclusive, in the format 'YYYY-MM-DD'
    delta = end_date - start_date  # timedelta

    for i in range(delta.days + 1):
        day = start_date + timedelta(days=i)
        datelist.append(day.strftime('%Y-%m-%d'))

    return datelist
