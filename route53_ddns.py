# This implements a AWS Lambda function that provides a DynDNS v2 API
# compatible front-end for Route 53 hosted domains.

from __future__ import print_function

import json
import logging
import os

import boto3

DEFAULT_TTL = 5 * 60  # 5 minutes
logger = logging.getLogger()


class Error(Exception):
    """Exception to reporting all HTTP status errors"""
    def __init__(self, body, statuscode=400):
        self.body = body
        self.statuscode = statuscode

    def response(self):
        """Returns the dict for the raw response"""
        return error_response(self.body,
                              statuscode=self.statuscode)


def error_response(body, statuscode=400):
    return response(body, statuscode=statuscode)


def response(body, content_type='text/plain', statuscode=200):
    return {
        'statusCode': statuscode,
        'headers': {
            'Content-Type': content_type,
        },
        'body': body,
    }


def get_source_ip(event):
    """Retrieve requester IP address from event dict"""
    x = event.get('requestContext', {})
    x = x.get('identity', {})
    x = x.get('sourceIp', {})

    if x == {}:
        raise Error("myip not given and sourceIP cannot be determined")

    return x


def parse_hostname_param(hostname):
    """Parse the hostname field and qualify the entries

    This will take a comma delimited string of one or more hostnames and
    return an array of fully qualified hostnames.  Each will be terminated
    with a '.' character.
    """

    hostnames = []
    for hn in hostname.split(','):
        if hn.endswith('.'):
            hostnames.append(hn)
        else:
            hostnames.append(hn + '.')

    return hostnames


def get_params(event):
    """Parse the query string parameters from the lambda event

    This will look for the hostname, myip and system parameters.  If "myip" is
    missing, then it will call get_source_ip to pull it out of the event.  If
    any unknown fields are found, then an exception will be thrown.
    """
    if 'queryStringParameters' not in event:
        raise Error('No queryStringParameter field')

    if event['queryStringParameters'] is None:
        event['queryStringParameters'] = {}

    if 'hostname' not in event['queryStringParameters']:
        raise Error('hostname is a required parameter')

    p = {'hostname': event['queryStringParameters']['hostname']}
    del event['queryStringParameters']['hostname']

    # The hostname parameter can have multiple hostnames embedded.
    p['hostname'] = parse_hostname_param(p['hostname'])

    if 'myip' in event['queryStringParameters']:
        p['myip'] = event['queryStringParameters']['myip']
        del event['queryStringParameters']['myip']
    else:
        p['myip'] = get_source_ip(event)

    # Some versions of ddclient send the 'system' parameter which indicates
    # which API it is using.  This would be helpful if we end up implementing
    # more than one API, but for now we ignore it.
    event['queryStringParameters'].pop('system', None)

    if len(event['queryStringParameters']) != 0:
        msg = ("Unknown parameters:\n" +
               json.dumps(event['queryStringParameters']))
        raise Error(msg)

    return p


def get_domain_candidates(hostname):
    """Returns the domains that the hostname could be in.

    Returns an array of domains with the longest candidates first.  TLD is
    included because it could be an internal only zone.
    """

    if hostname[len(hostname) - 1] == '.':
        hostname = hostname[:len(hostname) - 1]

    candidates = []
    last = ''
    parts = reversed(hostname.split('.'))
    for part in parts:
        cur = part + '.' + last
        candidates.append(cur)
        last = cur

    return list(reversed(candidates))


def pick_zone(hostname, zones):
    """Find the longest match zone for the hostname

    Takes a list of all zones from Route53 and walks all candidates
    finding the longest match.  Returns the Route 53 domain id.
    """
    candidates = get_domain_candidates(hostname)

    for c in candidates:
        for z in zones['HostedZones']:
            if c == z['Name']:
                return z['Id']

    raise Error("No zone found for hostname.")


def find_zone(hostname):
    """Return the zone id of the matching Route 53 domain"""

    r53 = boto3.client('route53')
    zones = r53.list_hosted_zones_by_name()
    return pick_zone(hostname, zones)


def update_resource_record(zoneid, hostname, ip, ttl):
    """Update a Route53 record with new IP address and TTL

    Returns the Route53 response.
    """
    r53 = boto3.client('route53')
    result = r53.change_resource_record_sets(
        HostedZoneId=zoneid,
        ChangeBatch={
            'Changes': [{
                'Action': 'UPSERT',
                'ResourceRecordSet': {
                    'Name': hostname,
                    'Type': 'A',
                    'TTL': ttl,
                    'ResourceRecords': [
                        {'Value': ip},
                    ],
                },
            }],
        },
    )

    result = result['ChangeInfo']
    result['SubmittedAt'] = str(result['SubmittedAt'])

    return result


def handler(event, context):
    """Main lambda handler function"""
    if 'DEBUG' in os.environ and os.environ['DEBUG'] == 'true':
        logger.setLevel(logging.DEBUG)
        event_json = json.dumps(event, indent=2)
        logger.debug('Received event: ' + event_json)
    else:
        logger.setLevel(logging.INFO)

    response_body = ''
    try:
        if 'TTL' in os.environ:
            ttl = os.environ['TTL']
        else:
            ttl = DEFAULT_TTL

        params = get_params(event)
        for hostname in params['hostname']:
            zoneid = find_zone(hostname)
            update_resource_record(
                zoneid,
                hostname,
                params['myip'],
                ttl,
            )
            logger.info('Update complete for %s = %s' % (
                hostname, params['myip']))
            response_body += 'good ' + params['myip'] + "\n"

    except Error as e:
        return e.response()

    return response(response_body)
