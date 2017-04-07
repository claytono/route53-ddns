import logging
import unittest

import route53_ddns


class TestRoute53DDNS(unittest.TestCase):
    def test_get_source_ip(self):
        event = {
            'requestContext': {
                'identity': {
                    'sourceIp': "173.73.171.92",
                },
            },
        }

        result = route53_ddns.get_source_ip(event)
        self.assertEqual(result, "173.73.171.92")

    def test_get_source_ip_noip(self):
        event = {}

        with self.assertRaises(route53_ddns.Error):
            route53_ddns.get_source_ip(event)

    def test_get_domain_candidates(self):
        c = route53_ddns.get_domain_candidates('hostname.domain.com.')
        self.assertEqual(
            c,
            ['hostname.domain.com.', 'domain.com.', 'com.']
            )

    def test_parse_hostname_param(self):
        cases = [
            ('test.hostname.com', ['test.hostname.com.']),
            ('test.hostname.com.', ['test.hostname.com.']),
            ('test.com.,test2.com',
                ['test.com.', 'test2.com.'])

        ]

        for case in cases:
            r = route53_ddns.parse_hostname_param(case[0])
            self.assertEqual(case[1], r)

    def test_handler_no_querystringparameters(self):
        event = {}
        response = route53_ddns.handler(event, {})
        self.assertEqual(response['statusCode'], 400)

    def test_handler_null_querystringparameters(self):
        event = {
            'queryStringParameters': None,
        }

        response = route53_ddns.handler(event, {})
        self.assertEqual(response['statusCode'], 400)

    def test_handler_no_hostname(self):
        event = {
            'queryStringParameters': {
            },
        }

        response = route53_ddns.handler(event, {})
        self.assertEqual(response['statusCode'], 400)

    def test_handler_unknown_parameter(self):
        event = {
            'queryStringParameters': {
                'hostname': 'test.internal',
                'unknown': 123,
            },
        }

        response = route53_ddns.handler(event, {})
        self.assertEqual(response['statusCode'], 400)


if __name__ == '__main__':
    logging.basicConfig()
    unittest.main()
