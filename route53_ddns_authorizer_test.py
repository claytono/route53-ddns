import logging
import os
import unittest

import route53_ddns_authorizer as authorizer


class TestRoute53DDNSAuthorizer(unittest.TestCase):

    def test_decode_authorization(self):
        # 0 = input, 1 = output, 2 = exception class on error
        cases = [
            ('Basic dXNlcjpwYXNz', ('user', 'pass'), None),
            ('', None,
             authorizer.InvalidAuthorizationHeaderException),
            ('1 2 3',
             None,
             authorizer.InvalidAuthorizationHeaderException),
            ('Digest garbage',
             None,
             authorizer.OnlyBasicException),
        ]

        for case in cases:
            print(case)
            if case[1] is not None:
                result = authorizer.decode_authorization(case[0])
                self.assertEqual(result, case[1])

            if case[2] is not None:
                with self.assertRaises(case[2]):
                    authorizer.decode_authorization(case[0])

    def test_check_authorization_no_token(self):
        result = authorizer.check_authorization({}, 'user', 'pass')
        self.assertFalse(result)

    def test_check_authorization(self):
        event = {
            'authorizationToken': 'Basic dXNlcjpwYXNz'
        }
        result = authorizer.check_authorization(event,
                                                'user', 'pass')
        self.assertTrue(result)

        result = authorizer.check_authorization(event,
                                                'user', 'badpass')
        self.assertFalse(result)

    def test_handler_no_auth_username(self):
        del os.environ['USERNAME']
        os.environ['PASSWORD'] = 'pass'
        event = {
            'authorizationToken': 'Basic dXNlcjpwYXNz'
        }

        with self.assertRaises(KeyError):
            authorizer.handler(event, {})

    def test_handler_no_auth_password(self):
        os.environ['USERNAME'] = 'user'
        del os.environ['PASSWORD']
        event = {
            'authorizationToken': 'Basic dXNlcjpwYXNz'
        }

        with self.assertRaises(KeyError):
            authorizer.handler(event, {})

    def test_handler_auth(self):
        os.environ['USERNAME'] = 'user'
        os.environ['PASSWORD'] = 'pass'
        event = {
            'authorizationToken': 'Basic dXNlcjpwYXNz',
            'methodArn': 'arn:fake:number',
        }

        policy = authorizer.handler(event, {})
        self.assertEqual(policy['principalId'], 'user')

    def test_handler_bad_user(self):
        os.environ['USERNAME'] = 'baduser'
        os.environ['PASSWORD'] = 'pass'
        event = {
            'authorizationToken': 'Basic dXNlcjpwYXNz',
            'methodArn': 'arn:fake:number',
        }

        with self.assertRaises(Exception) as context:
            authorizer.handler(event, {})

        self.assertTrue('Unauthorized' in context.exception)

    def test_handler_bad_pass(self):
        os.environ['USERNAME'] = 'user'
        os.environ['PASSWORD'] = 'badpass'
        event = {
            'authorizationToken': 'Basic dXNlcjpwYXNz',
            'methodArn': 'arn:fake:number',
        }

        with self.assertRaises(Exception) as context:
            authorizer.handler(event, {})

        self.assertTrue('Unauthorized' in context.exception)


if __name__ == '__main__':
    logging.basicConfig()
    unittest.main()
