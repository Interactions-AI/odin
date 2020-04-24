# coding: utf-8

from __future__ import absolute_import

from flask import json
from six import BytesIO

from swagger_server.models.gpu_device_info import GPUDeviceInfo  # noqa: E501
from swagger_server.test import BaseTestCase


class TestMidgardController(BaseTestCase):
    """MidgardController integration test stubs"""

    def test_get_gpu(self):
        """Test case for get_gpu

        Get GPU device info for a single device
        """
        response = self.client.open(
            '/v1/gpus/{id}'.format(id='id_example'),
            method='GET')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_get_gpus(self):
        """Test case for get_gpus

        Get info for all gpus
        """
        query_string = [('q', 'q_example')]
        response = self.client.open(
            '/v1/gpus',
            method='GET',
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    import unittest
    unittest.main()
