from __future__ import print_function

import json
import logging
import os

import route53_ddns

# This is a test harass for doing basic local testing using a local copy of
# boto3 and local credientials.

if __name__ == '__main__':
    logging.basicConfig()

    event = {
        'headers': {
            'Authorization': 'Basic dXNlcjpwYXNz'
        },
        'queryStringParameters': {
            'hostname': 'test.internal,test2.internal.',
            'myip': '1.2.3.4',
        },
    }

    os.environ['DEBUG'] = 'true'
    response = route53_ddns.handler(event, {})
    print("RESPONSE:")
    print(json.dumps(response, indent=2))
