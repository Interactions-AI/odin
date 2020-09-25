import connexion
import six
import flask
from midgard.server.models import *

#from midgard.server.models.gpu_device_info import GPUDeviceInfo  # noqa: E501
#from midgard.server.models.gpu_device_results import GPUDeviceResults
#from midgard.server.models.gpu_device_wrapper_definition import GPUDeviceWrapperDefinition
from midgard.server import util

Q = 'index,uuid,serial,name,utilization.gpu,utilization.memory,memory.free,memory.used,memory.total,temperature.gpu,temperature.memory,power.management,power.draw,power.limit,power.default_limit,power.min_limit,power.max_limit,clocks.current.memory,clocks.applications.memory,clocks.max,clocks.max.sm,compute-apps,enforced_power_limit,pci.bus_id,fan_speed,pstate,compute_mode,ecc.mode.current,ecc.mode.pending'


def get_gpu(id_):  # noqa: E501
    """Get GPU device info for a single device

     # noqa: E501

    :param id_: ID of GPU
    :type id_: str

    :rtype: GPUDeviceInfo
    """
    try:
        results = flask.globals.current_app.nvsmi.DeviceQuery(Q)
        output = [r for r in results if r['uuid'] == id_][0]['gpu']
        gpu_device_info = _to_camel(output)
        return GPUDeviceWrapperDefinition(gpu_device_info)
    except:
        return GPUDeviceWrapperDefinition()

def _to_camel(r: GPUDeviceInfo):
    applications_clocks = GPUClockInfo(**r['applications_clocks'])
    clocks = GPUClockInfo(**r['clocks'])
    ecc_mode = ECCModeInfo(**r['ecc_mode'])
    fb_memory_usage = FBMemoryUsageGPU(**r['fb_memory_usage'])
    max_clocks = GPUMaxClockInfo(**r['max_clocks'])
    pci = PCIInfoGPU(**r['pci'])
    power_readings = GPUPowerReadingInfo(**r['power_readings'])
    temperature = GPUTemperatureInfo(**r['temperature'])
    utilization = GPUUtilizationInfo(**r['utilization'])

    r['applications_clocks'] = applications_clocks
    r['clocks'] = clocks
    r['ecc_mode'] = ecc_mode
    r['fb_memory_usage'] = fb_memory_usage
    r['max_clocks'] = max_clocks
    r['pci'] = pci
    r['power_readings'] = power_readings
    r['temperature'] = temperature
    r['utilization'] = utilization
    return GPUDeviceInfo(**r)


def get_gpus(q=None):  # noqa: E501
    """Get info for all gpus

     # noqa: E501

    :param q: Get GPU devices by partial name match
    :type q: str

    :rtype: GPUDeviceInfo
    """
    try:
        results = flask.globals.current_app.nvsmi.DeviceQuery(Q)['gpu']
        gpu_device_infos = [_to_camel(r) for r in results]
    except:
        gpu_device_infos = []
    return GPUDeviceResults(gpu_device_infos)
