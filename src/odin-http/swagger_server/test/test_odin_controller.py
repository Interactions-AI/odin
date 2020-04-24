# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.error import Error  # noqa: E501
from swagger_server.models.event_definition import EventDefinition  # noqa: E501
from swagger_server.models.pipeline_definition import PipelineDefinition  # noqa: E501
from swagger_server.test import BaseTestCase


class TestOdinController(BaseTestCase):
    """OdinController integration test stubs"""

    def test_create_job(self):
        """Test case for create_job

        Post a job
        """
        body = 'body_example'
        response = self.client.open(
            '/v1/job',
            method='POST',
            data=json.dumps(body),
            content_type='application/json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_create_pipeline(self):
        """Test case for create_pipeline

        Create a pipeline definition
        """
        body = PipelineDefinition()
        response = self.client.open(
            '/v1/pipeline',
            method='POST',
            data=json.dumps(body),
            content_type='application/json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_get_events(self):
        """Test case for get_events

        Get events associated with some resource or sub-resource
        """
        response = self.client.open(
            '/v1/events'.format(id='id_example'),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_get_job(self):
        """Test case for get_job

        Get a job status
        """
        response = self.client.open(
            '/v1/job'.format(id='id_example'),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_get_jobs(self):
        """Test case for get_jobs

        Get job info
        """
        query_string = [('q', 'q_example')]
        response = self.client.open(
            '/v1/jobs',
            method='GET',
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_get_pipeline(self):
        """Test case for get_pipeline

        Get pipeline chain info
        """
        response = self.client.open(
            '/v1/pipeline'.format(id='id_example'),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_get_pipelines(self):
        """Test case for get_pipelines

        Get pipeline chain info
        """
        query_string = [('q', 'q_example')]
        response = self.client.open(
            '/v1/pipelines',
            method='GET',
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
