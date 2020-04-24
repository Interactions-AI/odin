**GET /gpus**

```
curl http://localhost:29999/v1/gpus
{
  "gpus": [
    {
      "applicationsClocks": {
        "memClock": "N/A",
        "unit": "MHz"
      },
      "clocks": {
        "memClock": 405,
        "unit": "MHz"
      },
      "computeMode": "Default",
      "eccMode": {
        "currentEcc": "N/A",
        "pendingEcc": "N/A"
      },
      "fbMemoryUsage": {
        "free": 7952.25,
        "total": 7952.3125,
        "unit": "MiB",
        "used": 0.0625
      },
      "id": "0000:01:00.0",
      "maxClocks": {
        "smClock": 2100,
        "unit": "MHz"
      },
      "minorNumber": "0",
      "pci": {
        "pciBusId": "0000:01:00.0"
      },
      "performanceState": "P8",
      "powerReadings": {
        "defaultPowerLimit": "N/A",
        "maxPowerLimit": "N/A",
        "minPowerLimit": "N/A",
        "powerDraw": 3.524,
        "powerLimit": "N/A",
        "powerManagement": "N/A",
        "powerState": "P8",
        "unit": "W"
      },
      "productBrand": "GeForce",
      "productName": "GeForce RTX 2080 with Max-Q Design",
      "serial": "N/A",
      "temperature": {
        "gpuTemp": 45,
        "gpuTempMaxThreshold": 99,
        "gpuTempSlowThreshold": 94,
        "unit": "C"
      },
      "utilization": {
        "gpuUtil": 0,
        "memoryUtil": 0,
        "unit": "%"
      },
      "uuid": "GPU-1b9a3804-64b6-3c05-cbb2-757cc8907437"
    }
  ]
}
```


