# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

import requests
from .base import GatewayTestBase

class TestGatewayApp(GatewayTestBase):
    def test_startup(self):
        '''Root of kernels resource should be OK.'''
        resp = requests.get(TestGatewayApp.base_url()+'/api/kernels')
        self.assertEqual(resp.status_code, 200)

    def test_headless(self):
        '''Other notebook resources should not exist.'''
        resp = requests.get(TestGatewayApp.base_url()+'/api/contents')
        self.assertEqual(resp.status_code, 404)
        resp = requests.get(TestGatewayApp.base_url())
        self.assertEqual(resp.status_code, 404)
        resp = requests.get(TestGatewayApp.base_url()+'/tree')
        self.assertEqual(resp.status_code, 404)
