# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
"""Tests for notebook-http mode."""

import os
import sys
import json

from .test_gatewayapp import TestGatewayAppBase, RESOURCES
from ..notebook_http.swagger.handlers import SwaggerSpecHandler
from tornado.testing import gen_test

class TestDefaults(TestGatewayAppBase):
    """Tests gateway behavior."""
    def setup_app(self):
        """Sets the notebook-http mode and points to a local test notebook as
        the basis for the API.
        """
        self.app.api = 'kernel_gateway.notebook_http'
        self.app.seed_uri = os.path.join(RESOURCES,
                                         'kernel_api{}.ipynb'.format(sys.version_info.major))

    @gen_test
    def test_api_get_endpoint(self):
        """GET HTTP method should be callable"""
        response = yield self.http_client.fetch(
            self.get_url('/hello'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
        self.assertEqual(response.body, b'hello world\n', 'Unexpected body in response to GET.')

    @gen_test
    def test_api_get_endpoint_with_path_param(self):
        """GET HTTP method should be callable with a path param"""
        response = yield self.http_client.fetch(
            self.get_url('/hello/governor'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
        self.assertEqual(response.body, b'hello governor\n', 'Unexpected body in response to GET.')

    @gen_test
    def test_api_get_endpoint_with_query_param(self):
        """GET HTTP method should be callable with a query param"""
        response = yield self.http_client.fetch(
            self.get_url('/hello/person?person=governor'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
        self.assertEqual(response.body, b'hello governor\n', 'Unexpected body in response to GET.')

    @gen_test
    def test_api_get_endpoint_with_multiple_query_params(self):
        """GET HTTP method should be callable with multiple query params"""
        response = yield self.http_client.fetch(
            self.get_url('/hello/persons?person=governor&person=rick'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
        self.assertEqual(response.body, b'hello governor, rick\n', 'Unexpected body in response to GET.')

    @gen_test
    def test_api_put_endpoint(self):
        """PUT HTTP method should be callable"""
        response = yield self.http_client.fetch(
            self.get_url('/message'),
            method='PUT',
            body='hola {}',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'PUT endpoint did not return 200.')

        response = yield self.http_client.fetch(
            self.get_url('/message'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
        self.assertEqual(response.body, b'hola {}\n', 'Unexpected body in response to GET after performing PUT.')

    @gen_test
    def test_api_post_endpoint(self):
        """POST endpoint should be callable"""
        expected = b'["Rick", "Maggie", "Glenn", "Carol", "Daryl"]\n'
        response = yield self.http_client.fetch(
            self.get_url('/people'),
            method='POST',
            body=expected.decode('UTF-8'),
            raise_error=False,
            headers={'Content-Type': 'application/json'}
        )
        self.assertEqual(response.code, 200, 'POST endpoint did not return 200.')
        self.assertEqual(response.body, expected, 'Unexpected body in response to POST.')

    @gen_test
    def test_api_delete_endpoint(self):
        """DELETE HTTP method should be callable"""
        expected = b'["Rick", "Maggie", "Glenn", "Carol", "Daryl"]\n'
        response = yield self.http_client.fetch(
            self.get_url('/people'),
            method='POST',
            body=expected.decode('UTF-8'),
            raise_error=False,
            headers={'Content-Type': 'application/json'}
        )
        response = yield self.http_client.fetch(
            self.get_url('/people/2'),
            method='DELETE',
            raise_error=False,
        )
        self.assertEqual(response.code, 200, 'DELETE endpoint did not return 200.')
        self.assertEqual(response.body, b'["Rick", "Maggie", "Carol", "Daryl"]\n', 'Unexpected body in response to DELETE.')

    @gen_test
    def test_api_error_endpoint(self):
        """Error in a cell should cause 500 HTTP status"""
        response = yield self.http_client.fetch(
            self.get_url('/error'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 500, 'Cell with error did not return 500 status code.')

    @gen_test
    def test_api_stderr_endpoint(self):
        """stderr output in a cell should be dropped"""
        response = yield self.http_client.fetch(
            self.get_url('/stderr'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.body, b'I am text on stdout\n', 'Unexpected text in response')

    @gen_test
    def test_api_unsupported_method(self):
        """Endpoints which do no support an HTTP verb should respond with 405.
        """
        response = yield self.http_client.fetch(
            self.get_url('/message'),
            method='DELETE',
            raise_error=False
        )
        self.assertEqual(response.code, 405, 'Endpoint which exists, but does not support DELETE, did not return 405 status code.')

    @gen_test
    def test_api_undefined(self):
        """Endpoints which are not registered at all should respond with 404.
        """
        response = yield self.http_client.fetch(
            self.get_url('/not/an/endpoint'),
            method='GET',
            raise_error=False
        )
        body = json.loads(response.body.decode('UTF-8'))
        self.assertEqual(response.code, 404, 'Endpoint which should not exist did not return 404 status code.')
        self.assertEqual(body['reason'], 'Not Found')

    @gen_test
    def test_api_access_http_header(self):
        """HTTP endpoints should be able to access request headers"""
        content_types = ['text/plain', 'application/json', 'application/atom+xml', 'foo']
        for content_type in content_types:
            response = yield self.http_client.fetch(
                self.get_url('/content-type'),
                method='GET',
                raise_error=False,
                headers={'Content-Type': content_type}
            )
            self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
            self.assertEqual(response.body.decode(encoding='UTF-8'), '{}\n'.format(content_type), 'Unexpected value in response')

    @gen_test
    def test_format_request_code_escaped_integration(self):
        """Quotes should be properly escaped in request headers."""
        #Test query with escaping of arguements and headers with multiple escaped quotes
        response = yield self.http_client.fetch(
            self.get_url('/hello/person?person=governor'),
            method='GET',
            headers={'If-None-Match': '\"\"9a28a9262f954494a8de7442c63d6d0715ce0998\"\"'},
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
        self.assertEqual(response.body, b'hello governor\n', 'Unexpected body in response to GET.')

    @gen_test
    def test_blocked_download_notebook_source(self):
        """Notebook source should not exist under the path /_api/source when
        `allow_notebook_download` is False or not configured.
        """
        response = yield self.http_client.fetch(
            self.get_url('/_api/source'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 404, "/_api/source found when allow_notebook_download is false")

    @gen_test
    def test_blocked_public(self):
        """Public static assets should not exist under the path /public when
        `static_path` is False or not configured.
        """
        response = yield self.http_client.fetch(
            self.get_url('/public'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 404, "/public found when static_path is false")

    @gen_test
    def test_api_returns_execute_result(self):
        """GET HTTP method should return the result of cell execution"""
        response = yield self.http_client.fetch(
            self.get_url('/execute_result'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
        self.assertEqual(response.body, b'{"text/plain": "2"}', 'Unexpected body in response to GET.')

    @gen_test
    def test_cells_concatenate(self):
        """Multiple cells with the same verb and path should concatenate."""
        response = yield self.http_client.fetch(
            self.get_url('/multi'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
        self.assertEqual(response.body, b'x is 1\n', 'Unexpected body in response to GET.')

    @gen_test
    def test_kernel_gateway_environment_set(self):
        """GET HTTP method should be callable with multiple query params"""
        response = yield self.http_client.fetch(
            self.get_url('/env_kernel_gateway'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'GET endpoint did not return 200.')
        self.assertEqual(response.body, b'KERNEL_GATEWAY is 1\n', 'Unexpected body in response to GET.')

class TestPublicStatic(TestGatewayAppBase):
    """Tests gateway behavior when public static assets are enabled."""
    def setup_app(self):
        """Sets the notebook-http mode and points to a local test notebook as
        the basis for the API. 
        """
        self.app.api = 'kernel_gateway.notebook_http'
        self.app.seed_uri = os.path.join(RESOURCES,
                                         'kernel_api{}.ipynb'.format(sys.version_info.major))

    def setup_configurables(self):
        """Configures the static path at the root of the resources/public folder."""
        self.app.personality.static_path = os.path.join(RESOURCES, 'public')

    @gen_test
    def test_get_public(self):
        """index.html should exist under `/public/index.html`."""
        response = yield self.http_client.fetch(
            self.get_url('/public/index.html'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(response.headers.get('Content-Type'), 'text/html')

class TestSourceDownload(TestGatewayAppBase):
    """Tests gateway behavior when notebook download is allowed."""
    def setup_app(self):
        """Sets the notebook-http mode, points to a local test notebook as
        the basis for the API, and enables downloads of that notebook.
        """
        self.app.api = 'kernel_gateway.notebook_http'
        self.app.seed_uri = os.path.join(RESOURCES,
                                         'kernel_api{}.ipynb'.format(sys.version_info.major))

    def setup_configurables(self):
        self.app.personality.allow_notebook_download = True

    @gen_test
    def test_download_notebook_source(self):
        """Notebook source should exist under the path `/_api/source`."""
        response = yield self.http_client.fetch(
            self.get_url('/_api/source'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200, "/_api/source did not correctly return the downloaded notebook")

class TestCustomResponse(TestGatewayAppBase):
    """Tests gateway behavior when the notebook contains ResponseInfo cells."""
    def setup_app(self):
        """Sets the notebook-http mode and points to a local test notebook as
        the basis for the API.
        """
        self.app.api = 'kernel_gateway.notebook_http'
        self.app.seed_uri = os.path.join(RESOURCES,
                                         'responses_{}.ipynb'.format(sys.version_info.major))

    @gen_test
    def test_setting_content_type(self):
        """A response cell should allow the content type to be set"""
        response = yield self.http_client.fetch(
            self.get_url('/json'),
            method='GET',
            raise_error=False
        )
        result = json.loads(response.body.decode('UTF-8'))
        self.assertEqual(response.code, 200, 'Response status was not 200')
        self.assertEqual(response.headers['Content-Type'], 'application/json', 'Incorrect mime type was set on response')
        self.assertEqual(result, {'hello' : 'world'}, 'Incorrect response value.')

    @gen_test
    def test_setting_response_status_code(self):
        """A response cell should allow the response status code to be set"""
        response = yield self.http_client.fetch(
            self.get_url('/nocontent'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 204, 'Response status was not 204')
        self.assertEqual(response.body, b'', 'Incorrect response value.')

    @gen_test
    def test_setting_etag_header(self):
        """A response cell should allow the etag header to be set"""
        response = yield self.http_client.fetch(
            self.get_url('/etag'),
            method='GET',
            raise_error=False
        )
        result = json.loads(response.body.decode('UTF-8'))
        self.assertEqual(response.code, 200, 'Response status was not 200')
        self.assertEqual(response.headers['Content-Type'], 'application/json', 'Incorrect mime type was set on response')
        self.assertEqual(result, {'hello' : 'world'}, 'Incorrect response value.')
        self.assertEqual(response.headers['Etag'], '1234567890', 'Incorrect Etag header value.')

class TestKernelPool(TestGatewayAppBase):
    """Tests gateway behavior with more than one kernel in the kernel pool."""
    def setup_app(self):
        """Sets the notebook-http mode, points to a local test notebook as
        the basis for the API, and spawns 3 kernels to service requests.
        """
        self.app.prespawn_count = 3
        self.app.api = 'kernel_gateway.notebook_http'
        self.app.seed_uri = os.path.join(RESOURCES,
                                         'kernel_api{}.ipynb'.format(sys.version_info.major))

    @gen_test
    def test_should_cycle_through_kernels(self):
        """Requests should cycle through kernels"""
        response = yield self.http_client.fetch(
            self.get_url('/message'),
            method='PUT',
            body='hola {}',
            raise_error=False
        )
        self.assertEqual(response.code, 200, 'PUT endpoint did not return 200.')

        for i in range(self.app.prespawn_count):
            response = yield self.http_client.fetch(
                self.get_url('/message'),
                method='GET',
                raise_error=False
            )

            if i != self.app.prespawn_count-1:
                self.assertEqual(response.body, b'hello {}\n', 'Unexpected body in response to GET after performing PUT.')
            else:
                self.assertEqual(response.body, b'hola {}\n', 'Unexpected body in response to GET after performing PUT.')
    @gen_test
    def test_concurrent_request_should_not_be_blocked(self):
        """Concurrent requests should not be blocked"""
        response_long_running = self.http_client.fetch(
            self.get_url('/sleep/6'),
            method='GET',
            raise_error=False
        )
        self.assertTrue(response_long_running.running(), 'Long HTTP Request is not running')
        response_short_running = yield self.http_client.fetch(
            self.get_url('/sleep/3'),
            method='GET',
            raise_error=False
        )
        self.assertTrue(response_long_running.running(), 'Long HTTP Request is not running')
        self.assertEqual(response_short_running.code, 200, 'Short HTTP Request did not return proper status code of 200')

    @gen_test
    def test_locking_semaphore_of_kernel_resources(self):
        """Kernel pool should prevent more than one request from running on a kernel at a time.
        """
        futures = []
        for _ in range(self.app.prespawn_count*2+1):
            futures.append(self.http_client.fetch(
                self.get_url('/sleep/1'),
                method='GET',
                raise_error=False
            ))

        count = 0
        for future in futures:
            yield future
            count += 1
            if count >= self.app.prespawn_count + 1:
                break

class TestSwaggerSpec(TestGatewayAppBase):
    """Tests gateway behavior when generating a  custom base URL is configured."""
    def setup_app(self):
        """Sets a different notebook for testing the swagger generation."""
        self.app.api = 'kernel_gateway.notebook_http'
        self.app.seed_uri = os.path.join(RESOURCES,
                                         'simple_api{}.ipynb'.format(sys.version_info.major))

    @gen_test
    def test_generation_of_swagger_spec(self):
        """Server should expose a swagger specification of its notebook-defined
        API.
        """
        expected_response = {
            "info": {
                "version": "0.0.0",
                "title": "simple_api{}".format(sys.version_info.major)
            },
            "paths": {
                "/name": {
                    "get": {"responses": {"200": {"description": "Success"}}},
                    "post": {"responses": {"200": {"description": "Success"}}}
                }
            },
            "swagger": "2.0"
        }

        response = yield self.http_client.fetch(
            self.get_url('/_api/spec/swagger.json'),
            method='GET',
            raise_error=False
        )
        result = json.loads(response.body.decode('UTF-8'))
        self.assertEqual(response.code, 200, "Swagger spec endpoint did not return the correct status code")
        self.assertEqual(result, expected_response, "Swagger spec endpoint did not return the correct value")
        self.assertIsNotNone(SwaggerSpecHandler.output, "Swagger spec output wasn't cached for later requests")

class TestBaseURL(TestGatewayAppBase):
    """Tests gateway behavior when a custom base URL is configured."""
    def setup_app(self):
        """Sets the custom base URL and enables the notebook-defined API."""
        self.app.base_url = '/fake/path'
        self.app.api = 'kernel_gateway.notebook_http'
        self.app.seed_uri = os.path.join(RESOURCES,
                                         'kernel_api{}.ipynb'.format(sys.version_info.major))

    def setup_configurables(self):
        self.app.personality.allow_notebook_download = True

    @gen_test
    def test_base_url(self):
        """Server should mount resources under the configured base."""
        # Should not exist at root
        response = yield self.http_client.fetch(
            self.get_url('/hello'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 404)

        response = yield self.http_client.fetch(
            self.get_url('/_api/spec/swagger.json'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 404)

        # Should exist under path
        response = yield self.http_client.fetch(
            self.get_url('/fake/path/hello'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200)

        response = yield self.http_client.fetch(
            self.get_url('/fake/path/_api/spec/swagger.json'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200)


class TestForceKernel(TestGatewayAppBase):
    """Tests gateway behavior when forcing a kernel spec."""
    def setup_app(self):
        """Sets the notebook-http mode, points to a local test notebook as
        the basis for the API, and forces a Python kernel.
        """
        self.app.api = 'kernel_gateway.notebook_http'
        self.app.seed_uri = os.path.join(RESOURCES, 'unknown_kernel.ipynb')
        self.app.force_kernel_name = 'python{}'.format(sys.version_info.major)

    @gen_test
    def test_force_kernel_spec(self):
        """Should start properly.."""
        response = yield self.http_client.fetch(
            self.get_url('/_api/spec/swagger.json'),
            method='GET',
            raise_error=False
        )
        self.assertEqual(response.code, 200)
