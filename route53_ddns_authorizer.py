# This implements a single HTTP basic auth Lambda custom authorizer.  It
# expects to find the username and password set via the environment.  It then
# parses the Authorization header and returns success if it matches the
# configuration.

from __future__ import print_function

import base64
import json
import logging
import os

logger = logging.getLogger()


class AuthorizerException(Exception):
    pass


class InvalidAuthorizationHeaderException(AuthorizerException):
    pass


class OnlyBasicException(AuthorizerException):
    pass


def decode_authorization(auth_header):
    split = auth_header.strip().split(' ')

    if len(split) != 2:
        logger.error('Invalid authorization header: "%s"' % (auth_header))
        raise InvalidAuthorizationHeaderException()

    if split[0] != 'Basic':
        logger.error('Only "Basic" authentication is supported (%s)' %
                     (auth_header))
        raise OnlyBasicException()

    decoded = base64.b64decode(split[1])

    username, password = decoded.split(':', 1)
    return (username, password)


def check_authorization(event, username, password):

    if 'authorizationToken' not in event:
        logger.error("No authorizationToken field, malformed event?")
        return False

    token = event['authorizationToken']
    header_user, header_pass = decode_authorization(token)

    if header_user != username:
        return False

    return header_pass == password


def check_authorization_against_env(event):
    if 'USERNAME' not in os.environ:
        logger.error("USERNAME must be set in environment")
        raise KeyError("Internal configuration error")

    if 'PASSWORD' not in os.environ:
        logger.error("PASSWORD must be set in environment")
        return KeyError("Internal configuration error")

    return check_authorization(event,
                               os.environ['USERNAME'],
                               os.environ['PASSWORD'])


def handler(event, context):
    if 'DEBUG' in os.environ and os.environ['DEBUG'] == 'true':
        logger.setLevel(logging.DEBUG)
        event_json = json.dumps(event, indent=2)
        logger.debug('Received event: ' + event_json)
    else:
        logger.setLevel(logging.INFO)

    if not check_authorization_against_env(event):
        raise Exception('Unauthorized')

    policy_allow = {
        'principalId': os.environ['USERNAME'],
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': 'Allow',
                    'Resource': event['methodArn'],
                }
            ],
        },
    }

    return policy_allow
