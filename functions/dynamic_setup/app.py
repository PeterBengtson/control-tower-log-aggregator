from datetime import date
from datetime import timedelta


def lambda_handler(data, _context):

    data['bucket_names'] = data['bucket_names'].split(',')

    explicit_date = data.get('date')
    if not explicit_date:
        today = date.today()
        yesterday = today - timedelta(days = 1)
        data['date'] = str(yesterday)

    return data

