# coding: utf-8

from __future__ import absolute_import
from datetime import date, datetime  # noqa: F401

from typing import List, Dict  # noqa: F401

from midgard.server.models.base_model_ import Model
from midgard.server.models.ecc_mode_info import ECCModeInfo  # noqa: F401,E501
from midgard.server.models.fb_memory_usage_gpu import FBMemoryUsageGPU  # noqa: F401,E501
from midgard.server.models.gpu_clock_info import GPUClockInfo  # noqa: F401,E501
from midgard.server.models.gpu_max_clock_info import GPUMaxClockInfo  # noqa: F401,E501
from midgard.server.models.gpu_power_reading_info import GPUPowerReadingInfo  # noqa: F401,E501
from midgard.server.models.gpu_temperature_info import GPUTemperatureInfo  # noqa: F401,E501
from midgard.server.models.gpu_utilization_info import GPUUtilizationInfo  # noqa: F401,E501
from midgard.server.models.pci_info_gpu import PCIInfoGPU  # noqa: F401,E501
from midgard.server import util


class GPUDeviceInfo(Model):
    """NOTE: This class is auto generated by the swagger code generator program.

    Do not edit the class manually.
    """
    def __init__(self, id: str=None, uuid: str=None, product_name: str=None, product_brand: str=None, serial: str=None, minor_number: str=None, pci: PCIInfoGPU=None, performance_state: str=None, fb_memory_usage: FBMemoryUsageGPU=None, compute_mode: str=None, utilization: GPUUtilizationInfo=None, ecc_mode: ECCModeInfo=None, temperature: GPUTemperatureInfo=None, power_readings: GPUPowerReadingInfo=None, clocks: GPUClockInfo=None, applications_clocks: GPUClockInfo=None, max_clocks: GPUMaxClockInfo=None, processes: List[str]=None):  # noqa: E501
        """GPUDeviceInfo - a model defined in Swagger

        :param id: The id of this GPUDeviceInfo.  # noqa: E501
        :type id: str
        :param uuid: The uuid of this GPUDeviceInfo.  # noqa: E501
        :type uuid: str
        :param product_name: The product_name of this GPUDeviceInfo.  # noqa: E501
        :type product_name: str
        :param product_brand: The product_brand of this GPUDeviceInfo.  # noqa: E501
        :type product_brand: str
        :param serial: The serial of this GPUDeviceInfo.  # noqa: E501
        :type serial: str
        :param minor_number: The minor_number of this GPUDeviceInfo.  # noqa: E501
        :type minor_number: str
        :param pci: The pci of this GPUDeviceInfo.  # noqa: E501
        :type pci: PCIInfoGPU
        :param performance_state: The performance_state of this GPUDeviceInfo.  # noqa: E501
        :type performance_state: str
        :param fb_memory_usage: The fb_memory_usage of this GPUDeviceInfo.  # noqa: E501
        :type fb_memory_usage: FBMemoryUsageGPU
        :param compute_mode: The compute_mode of this GPUDeviceInfo.  # noqa: E501
        :type compute_mode: str
        :param utilization: The utilization of this GPUDeviceInfo.  # noqa: E501
        :type utilization: GPUUtilizationInfo
        :param ecc_mode: The ecc_mode of this GPUDeviceInfo.  # noqa: E501
        :type ecc_mode: ECCModeInfo
        :param temperature: The temperature of this GPUDeviceInfo.  # noqa: E501
        :type temperature: GPUTemperatureInfo
        :param power_readings: The power_readings of this GPUDeviceInfo.  # noqa: E501
        :type power_readings: GPUPowerReadingInfo
        :param clocks: The clocks of this GPUDeviceInfo.  # noqa: E501
        :type clocks: GPUClockInfo
        :param applications_clocks: The applications_clocks of this GPUDeviceInfo.  # noqa: E501
        :type applications_clocks: GPUClockInfo
        :param max_clocks: The max_clocks of this GPUDeviceInfo.  # noqa: E501
        :type max_clocks: GPUMaxClockInfo
        :param processes: The processes of this GPUDeviceInfo.  # noqa: E501
        :type processes: List[str]
        """
        self.swagger_types = {
            'id': str,
            'uuid': str,
            'product_name': str,
            'product_brand': str,
            'serial': str,
            'minor_number': str,
            'pci': PCIInfoGPU,
            'performance_state': str,
            'fb_memory_usage': FBMemoryUsageGPU,
            'compute_mode': str,
            'utilization': GPUUtilizationInfo,
            'ecc_mode': ECCModeInfo,
            'temperature': GPUTemperatureInfo,
            'power_readings': GPUPowerReadingInfo,
            'clocks': GPUClockInfo,
            'applications_clocks': GPUClockInfo,
            'max_clocks': GPUMaxClockInfo,
            'processes': List[str]
        }

        self.attribute_map = {
            'id': 'id',
            'uuid': 'uuid',
            'product_name': 'productName',
            'product_brand': 'productBrand',
            'serial': 'serial',
            'minor_number': 'minorNumber',
            'pci': 'pci',
            'performance_state': 'performanceState',
            'fb_memory_usage': 'fbMemoryUsage',
            'compute_mode': 'computeMode',
            'utilization': 'utilization',
            'ecc_mode': 'eccMode',
            'temperature': 'temperature',
            'power_readings': 'powerReadings',
            'clocks': 'clocks',
            'applications_clocks': 'applicationsClocks',
            'max_clocks': 'maxClocks',
            'processes': 'processes'
        }
        self._id = id
        self._uuid = uuid
        self._product_name = product_name
        self._product_brand = product_brand
        self._serial = serial
        self._minor_number = minor_number
        self._pci = pci
        self._performance_state = performance_state
        self._fb_memory_usage = fb_memory_usage
        self._compute_mode = compute_mode
        self._utilization = utilization
        self._ecc_mode = ecc_mode
        self._temperature = temperature
        self._power_readings = power_readings
        self._clocks = clocks
        self._applications_clocks = applications_clocks
        self._max_clocks = max_clocks
        self._processes = processes

    @classmethod
    def from_dict(cls, dikt) -> 'GPUDeviceInfo':
        """Returns the dict as a model

        :param dikt: A dict.
        :type: dict
        :return: The GPUDeviceInfo of this GPUDeviceInfo.  # noqa: E501
        :rtype: GPUDeviceInfo
        """
        return util.deserialize_model(dikt, cls)

    @property
    def id(self) -> str:
        """Gets the id of this GPUDeviceInfo.


        :return: The id of this GPUDeviceInfo.
        :rtype: str
        """
        return self._id

    @id.setter
    def id(self, id: str):
        """Sets the id of this GPUDeviceInfo.


        :param id: The id of this GPUDeviceInfo.
        :type id: str
        """

        self._id = id

    @property
    def uuid(self) -> str:
        """Gets the uuid of this GPUDeviceInfo.


        :return: The uuid of this GPUDeviceInfo.
        :rtype: str
        """
        return self._uuid

    @uuid.setter
    def uuid(self, uuid: str):
        """Sets the uuid of this GPUDeviceInfo.


        :param uuid: The uuid of this GPUDeviceInfo.
        :type uuid: str
        """

        self._uuid = uuid

    @property
    def product_name(self) -> str:
        """Gets the product_name of this GPUDeviceInfo.


        :return: The product_name of this GPUDeviceInfo.
        :rtype: str
        """
        return self._product_name

    @product_name.setter
    def product_name(self, product_name: str):
        """Sets the product_name of this GPUDeviceInfo.


        :param product_name: The product_name of this GPUDeviceInfo.
        :type product_name: str
        """

        self._product_name = product_name

    @property
    def product_brand(self) -> str:
        """Gets the product_brand of this GPUDeviceInfo.


        :return: The product_brand of this GPUDeviceInfo.
        :rtype: str
        """
        return self._product_brand

    @product_brand.setter
    def product_brand(self, product_brand: str):
        """Sets the product_brand of this GPUDeviceInfo.


        :param product_brand: The product_brand of this GPUDeviceInfo.
        :type product_brand: str
        """

        self._product_brand = product_brand

    @property
    def serial(self) -> str:
        """Gets the serial of this GPUDeviceInfo.


        :return: The serial of this GPUDeviceInfo.
        :rtype: str
        """
        return self._serial

    @serial.setter
    def serial(self, serial: str):
        """Sets the serial of this GPUDeviceInfo.


        :param serial: The serial of this GPUDeviceInfo.
        :type serial: str
        """

        self._serial = serial

    @property
    def minor_number(self) -> str:
        """Gets the minor_number of this GPUDeviceInfo.


        :return: The minor_number of this GPUDeviceInfo.
        :rtype: str
        """
        return self._minor_number

    @minor_number.setter
    def minor_number(self, minor_number: str):
        """Sets the minor_number of this GPUDeviceInfo.


        :param minor_number: The minor_number of this GPUDeviceInfo.
        :type minor_number: str
        """

        self._minor_number = minor_number

    @property
    def pci(self) -> PCIInfoGPU:
        """Gets the pci of this GPUDeviceInfo.


        :return: The pci of this GPUDeviceInfo.
        :rtype: PCIInfoGPU
        """
        return self._pci

    @pci.setter
    def pci(self, pci: PCIInfoGPU):
        """Sets the pci of this GPUDeviceInfo.


        :param pci: The pci of this GPUDeviceInfo.
        :type pci: PCIInfoGPU
        """

        self._pci = pci

    @property
    def performance_state(self) -> str:
        """Gets the performance_state of this GPUDeviceInfo.


        :return: The performance_state of this GPUDeviceInfo.
        :rtype: str
        """
        return self._performance_state

    @performance_state.setter
    def performance_state(self, performance_state: str):
        """Sets the performance_state of this GPUDeviceInfo.


        :param performance_state: The performance_state of this GPUDeviceInfo.
        :type performance_state: str
        """

        self._performance_state = performance_state

    @property
    def fb_memory_usage(self) -> FBMemoryUsageGPU:
        """Gets the fb_memory_usage of this GPUDeviceInfo.


        :return: The fb_memory_usage of this GPUDeviceInfo.
        :rtype: FBMemoryUsageGPU
        """
        return self._fb_memory_usage

    @fb_memory_usage.setter
    def fb_memory_usage(self, fb_memory_usage: FBMemoryUsageGPU):
        """Sets the fb_memory_usage of this GPUDeviceInfo.


        :param fb_memory_usage: The fb_memory_usage of this GPUDeviceInfo.
        :type fb_memory_usage: FBMemoryUsageGPU
        """

        self._fb_memory_usage = fb_memory_usage

    @property
    def compute_mode(self) -> str:
        """Gets the compute_mode of this GPUDeviceInfo.


        :return: The compute_mode of this GPUDeviceInfo.
        :rtype: str
        """
        return self._compute_mode

    @compute_mode.setter
    def compute_mode(self, compute_mode: str):
        """Sets the compute_mode of this GPUDeviceInfo.


        :param compute_mode: The compute_mode of this GPUDeviceInfo.
        :type compute_mode: str
        """

        self._compute_mode = compute_mode

    @property
    def utilization(self) -> GPUUtilizationInfo:
        """Gets the utilization of this GPUDeviceInfo.


        :return: The utilization of this GPUDeviceInfo.
        :rtype: GPUUtilizationInfo
        """
        return self._utilization

    @utilization.setter
    def utilization(self, utilization: GPUUtilizationInfo):
        """Sets the utilization of this GPUDeviceInfo.


        :param utilization: The utilization of this GPUDeviceInfo.
        :type utilization: GPUUtilizationInfo
        """

        self._utilization = utilization

    @property
    def ecc_mode(self) -> ECCModeInfo:
        """Gets the ecc_mode of this GPUDeviceInfo.


        :return: The ecc_mode of this GPUDeviceInfo.
        :rtype: ECCModeInfo
        """
        return self._ecc_mode

    @ecc_mode.setter
    def ecc_mode(self, ecc_mode: ECCModeInfo):
        """Sets the ecc_mode of this GPUDeviceInfo.


        :param ecc_mode: The ecc_mode of this GPUDeviceInfo.
        :type ecc_mode: ECCModeInfo
        """

        self._ecc_mode = ecc_mode

    @property
    def temperature(self) -> GPUTemperatureInfo:
        """Gets the temperature of this GPUDeviceInfo.


        :return: The temperature of this GPUDeviceInfo.
        :rtype: GPUTemperatureInfo
        """
        return self._temperature

    @temperature.setter
    def temperature(self, temperature: GPUTemperatureInfo):
        """Sets the temperature of this GPUDeviceInfo.


        :param temperature: The temperature of this GPUDeviceInfo.
        :type temperature: GPUTemperatureInfo
        """

        self._temperature = temperature

    @property
    def power_readings(self) -> GPUPowerReadingInfo:
        """Gets the power_readings of this GPUDeviceInfo.


        :return: The power_readings of this GPUDeviceInfo.
        :rtype: GPUPowerReadingInfo
        """
        return self._power_readings

    @power_readings.setter
    def power_readings(self, power_readings: GPUPowerReadingInfo):
        """Sets the power_readings of this GPUDeviceInfo.


        :param power_readings: The power_readings of this GPUDeviceInfo.
        :type power_readings: GPUPowerReadingInfo
        """

        self._power_readings = power_readings

    @property
    def clocks(self) -> GPUClockInfo:
        """Gets the clocks of this GPUDeviceInfo.


        :return: The clocks of this GPUDeviceInfo.
        :rtype: GPUClockInfo
        """
        return self._clocks

    @clocks.setter
    def clocks(self, clocks: GPUClockInfo):
        """Sets the clocks of this GPUDeviceInfo.


        :param clocks: The clocks of this GPUDeviceInfo.
        :type clocks: GPUClockInfo
        """

        self._clocks = clocks

    @property
    def applications_clocks(self) -> GPUClockInfo:
        """Gets the applications_clocks of this GPUDeviceInfo.


        :return: The applications_clocks of this GPUDeviceInfo.
        :rtype: GPUClockInfo
        """
        return self._applications_clocks

    @applications_clocks.setter
    def applications_clocks(self, applications_clocks: GPUClockInfo):
        """Sets the applications_clocks of this GPUDeviceInfo.


        :param applications_clocks: The applications_clocks of this GPUDeviceInfo.
        :type applications_clocks: GPUClockInfo
        """

        self._applications_clocks = applications_clocks

    @property
    def max_clocks(self) -> GPUMaxClockInfo:
        """Gets the max_clocks of this GPUDeviceInfo.


        :return: The max_clocks of this GPUDeviceInfo.
        :rtype: GPUMaxClockInfo
        """
        return self._max_clocks

    @max_clocks.setter
    def max_clocks(self, max_clocks: GPUMaxClockInfo):
        """Sets the max_clocks of this GPUDeviceInfo.


        :param max_clocks: The max_clocks of this GPUDeviceInfo.
        :type max_clocks: GPUMaxClockInfo
        """

        self._max_clocks = max_clocks

    @property
    def processes(self) -> List[str]:
        """Gets the processes of this GPUDeviceInfo.


        :return: The processes of this GPUDeviceInfo.
        :rtype: List[str]
        """
        return self._processes

    @processes.setter
    def processes(self, processes: List[str]):
        """Sets the processes of this GPUDeviceInfo.


        :param processes: The processes of this GPUDeviceInfo.
        :type processes: List[str]
        """

        self._processes = processes
