import datetime
import json
from contextlib import contextmanager

import pytz
import responses
from django.urls import reverse
from oscar.core.loading import get_model
from rest_framework import status
from testfixtures import LogCapture

from ecommerce.tests.testcases import TestCase

COUPON_CODE = 'COUPONTEST'
BUNDLE = 'bundle_identifier'

class ExecutiveEducation2UAPIViewSetTests(TestCase):

    def setUp(self):
        super().setUp()

        self.mock_settings = {
            'GET_SMARTER_OAUTH2_PROVIDER_URL': 'https://provider-url.com',
            'GET_SMARTER_OAUTH2_KEY': 'key',
            'GET_SMARTER_OAUTH2_SECRET': 'secret',
            'GET_SMARTER_API_URL': 'https://api-url.com',
        }

        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        responses.start()

        responses.add(
            responses.POST,
            self.mock_settings['GET_SMARTER_OAUTH2_PROVIDER_URL'] + '/oauth2/token',
            body=json.dumps({
                'access_token': 'abc',
                'expires_in': 60,
                'expires_at': datetime.datetime.now(pytz.utc).timestamp() + 60
            }),
            status=200,
        )

    def tearDown(self):
        super().tearDown()
        responses.reset()

    @responses.activate
    def test_get_terms_and_conditions_200(self):
        url = self.mock_settings['GET_SMARTER_API_URL'] + '/terms'
        terms_and_conditions = {
            'privacyPolicy': 'abcd',
            'websiteTermsOfUse': 'efgh',
        }

        responses.add(
            responses.GET,
            url,
            body=json.dumps(terms_and_conditions),
            status=200,
        )

        with self.settings(**self.mock_settings):
            path = reverse('executive_education_2u:executive_education_2u-get-terms-and-conditions')
            response = self.client.get(path)
            self.assertEqual(status.HTTP_200_OK, response.status_code)
            self.assertEqual(terms_and_conditions, response.json())

    @responses.activate
    def test_get_terms_and_conditions_500(self):
        url = self.mock_settings['GET_SMARTER_API_URL'] + '/terms'
        responses.add(
            responses.GET,
            url,
            status=500,
        )

        logger_name = 'ecommerce.extensions.executive_education_2u.views'

        with self.settings(**self.mock_settings), LogCapture(logger_name) as logger:
            path = reverse('executive_education_2u:executive_education_2u-get-terms-and-conditions')
            response = self.client.get(path)
            self.assertEqual(status.HTTP_500_INTERNAL_SERVER_ERROR, response.status_code)
            self.assertEqual('Failed to retrieve terms and conditions.', response.json())
            logger.check((logger_name, 'ERROR',
                f'500 Server Error: Internal Server Error for url: {url}'
            ))
