import os

c = get_config()

c.BaseProcessProxy.response_address = '0.0.0.0:8877'

c.MappingKernelManager.cull_idle_timeout = 3600

c.MappingKernelManager.cull_interval = 600

# Timeouts for remote kernel initialization
c.RemoteProcessProxy.socket_timeout = 5.0       # Network socket timeout
c.RemoteProcessProxy.prepare_timeout = 120.0     # Timeout for kernel preparation

# List of allowed remote hosts where kernels can run
c.EnterpriseGatewayApp.remote_hosts = [
]

# Custom load balancing (round-robin, least-connection, fcfs)
c.EnterpriseGatewayApp.load_balancing_algorithm = "fcfs"

# Kernel containers will use ports within this range
c.RemoteProcessProxy.port_range = "40000..50000"

c.DistributedProcessProxy.disable_host_key_checking = True

# Optional: specify custom SSH key for launching kernels on remote nodes
# c.DistributedProcessProxy.ssh_key_filename = '/home/jovyan/.ssh/id_rsa'

c.Application.log_level = "DEBUG"

# Log format for application messages
c.Application.log_format = '[%(levelname)1.1s %(asctime)s.%(msecs).03d %(name)s] %(message)s'

# Debug output (if ssh_key_filename is enabled)
print(f"[INFO] Default SSH key for DistributedProcessProxy set to: {c.DistributedProcessProxy.ssh_key_filename}")