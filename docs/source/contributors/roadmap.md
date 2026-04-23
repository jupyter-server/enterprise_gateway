# Project Roadmap

We have plenty to do, now and in the future. Here's where we're headed:

## Completed in 3.x

- Spark 3.0 support (including pod template files)
- Spark Operator support via `SparkOperatorProcessProxy`
- Custom Resource Definition support via `CustomResourceProcessProxy`
- Session persistence (file-based and webhook-based)
- `KERNEL_VOLUMES` and `KERNEL_VOLUME_MOUNTS` for Kubernetes and Spark Operator kernels
- Authorizer class override support (`EG_AUTHORIZER_CLASS`)
- SSTI prevention in `KERNEL_POD_NAME` template substitution
- Python 3.9 and below dropped; Python 3.10+ required

## Planned for 4.0

- Kernel Provisioners
  - Provisioners will replace process proxies and enable Enterprise Gateway to remove its cap on `jupyter_client < 7` and `jupyter_server < 2`.
- Parameterized Kernels
  - Enable the ability to prompt for parameters
  - These will likely be based on kernel provisioners

## Wish list

- High Availability
  - Session persistence using a shared location (NoSQL DB) (file-based persistence has been implemented)
  - Active/active support
- Multi-gateway support on client-side
  - Enables the ability for a single Jupyter Server to be configured against multiple Gateway servers simultaneously. This work will primarily be in Jupyter Server.
- Pluggable load-balancers into `DistributedProcessProxy` (currently uses simple round-robin)
- Support for other resource managers
  - Slurm?
  - Mesos?
- User Environments
  - Improve the way user files are made available to remote kernels
- Administration UI
  - Dashboard with running kernels
  - Lifecycle management
  - Time running, stop/kill, Profile Management, etc

We'd love to hear any other use cases you might have and look forward to your contributions to Jupyter Enterprise Gateway!
