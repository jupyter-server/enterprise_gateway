"""Collection of all the metrics used by the Enterprise Gateway"""

import os

from prometheus_client import Histogram

metrics_prefix = os.environ.get("EG_METRICS_PREFIX", "enterprise_gateway")

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    'http_request_duration_seconds',
    'Request duration for all HTTP requests',
    ['method', 'handler', 'status_code'],
    namespace=metrics_prefix,
)

KERNEL_START_DURATION_SECONDS = Histogram(
    'kernel_start_duration_seconds',
    'Kernel startup duration',
    ['kernel_name', 'process_proxy'],
    buckets=[0.1, 0.25, 0.5, 1, 2.5, 5.0, 10.0, 15.0, 20.0, 30.0],
    namespace=metrics_prefix,
)

KERNEL_SHUTDOWN_DURATION_SECONDS = Histogram(
    'kernel_shutdown_duration_seconds',
    'Kernel startup duration for all HTTP requests',
    ['kernel_name', 'process_proxy'],
    buckets=[0.1, 0.25, 0.5, 1, 2.5, 5.0, 10.0, 15.0, 20.0, 30.0],
    namespace=metrics_prefix,
)
