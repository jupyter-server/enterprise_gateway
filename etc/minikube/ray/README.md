# Ray + Jupyter Enterprise Gateway + JupyterHub on Minikube

This directory contains scripts and configuration files to deploy a complete Jupyter development environment on Minikube with Ray cluster support for distributed computing.

## Overview

This setup provides:

- **Minikube Kubernetes Cluster**: Local Kubernetes environment for testing and development
- **Ray Operator**: Manages Ray clusters for distributed Python workloads
- **Jupyter Enterprise Gateway**: Enables remote kernel execution on Ray and Kubernetes
- **JupyterHub**: Multi-user notebook server with custom spawner integration

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Minikube Cluster                      │
│                                                         │
│  ┌──────────────┐         ┌─────────────────────────┐   │
│  │  JupyterHub  │────────▶│  Enterprise Gateway     │   │
│  │  (hub ns)    │         │  (enterprise-gateway ns)│   │
│  └──────────────┘         └─────────────────────────┘   │
│         │                           │                   │
│         │                           │                   │
│         ▼                           ▼                   │
│  ┌──────────────┐         ┌─────────────────────────┐   │
│  │  User Pods   │         │   Ray Kernels           │   │
│  │  (Notebooks) │         │   (ray_python_operator) │   │
│  └──────────────┘         └─────────────────────────┘   │
│                                     │                   │
│                                     ▼                   │
│                           ┌─────────────────────────┐   │
│                           │   KubeRay Operator      │   │
│                           │   (Ray Clusters)        │   │
│                           └─────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

Before running the installation, ensure you have:

- **Docker Desktop**: Running and accessible
- **Minikube**: Installed (`brew install minikube` on macOS)
- **kubectl**: Kubernetes command-line tool
- **Helm 3**: Package manager for Kubernetes
- **EG_HOME**: Environment variable pointing to Enterprise Gateway repository root

```bash
# Example setup
export EG_HOME=/Users/lresende/opensource/jupyter/enterprise-gateway
```

## Installation

### Initial Cluster Setup

Run `install-minikube-ray.sh` to create a complete new cluster from scratch:

```bash
./install-minikube-ray.sh
```

**What this script does:**

1. **Launches Docker Desktop** (if not running)
1. **Stops existing Minikube cluster** named `ray` (if it exists)
1. **Starts Minikube** with:
   - Profile: `ray`
   - Driver: `docker`
   - Kubernetes version: `v1.31`
   - Memory: `12GB`
1. **Installs KubeRay Operator** (v1.5.0) via Helm
   - Manages Ray cluster lifecycle
   - Handles Ray pod scheduling and scaling
1. **Deploys Enterprise Gateway** via Helm chart
   - Uses local development build from `$EG_HOME/dist/`
   - Configured with `enterprise-gateway-minikube-helm.yaml`
   - Default kernel: `ray_python_operator`
   - Service exposed on NodePort 30088
1. **Applies Network Policy** (`enterprise-gateway-network.yaml`)
   - Allows all ingress/egress for Enterprise Gateway namespace
1. **Installs JupyterHub** (v4.3.1) via Helm
   - Custom KubeSpawner configuration
   - Integrates with Enterprise Gateway
   - Admin users: root, jovyan, lresende
   - Exposed via NodePort service
1. **Displays service URL** for JupyterHub proxy

**Expected Output:**

At the end of installation, you'll see the JupyterHub URL:

```
http://127.0.0.1:XXXXX
```

Open this URL in your browser to access JupyterHub.

### Notes on Installation Script

The script includes two options for cluster management (line 3-4):

```bash
minikube -p ray stop                              # Updates existing cluster
# minikube -p ray stop && minikube -p ray delete  # Creates fresh cluster
```

- **Default behavior**: Stops and restarts the existing cluster (preserves state)
- **Alternative**: Uncomment line 4 to completely delete and recreate the cluster

## Development Workflow

### Building and Updating Images

Use `update-minikube-ray.sh` when you've made changes to Enterprise Gateway or kernel images:

```bash
./update-minikube-ray.sh
```

**What this script does:**

1. **Navigates to EG_HOME** and builds distributions:

   ```bash
   make clean dist
   ```

   - Creates Helm chart tarball for Enterprise Gateway

1. **Builds and pushes Docker images**:

   ```bash
   make clean-enterprise-gateway enterprise-gateway push-enterprise-gateway \
        clean-kernel-ray-py kernel-ray-py push-kernel-ray-py \
        HUB_ORG=lresende TAG=dev
   ```

   - Builds `lresende/enterprise-gateway:dev`
   - Builds `lresende/kernel-ray-py:dev`
   - Pushes to DockerHub (requires authentication)

1. **Loads images into Minikube**:

   ```bash
   minikube image load lresende/enterprise-gateway:dev
   minikube image load lresende/kernel-ray-py:dev
   ```

   - Makes images available to Kubernetes without pulling from registry

1. **Restarts Enterprise Gateway deployment**:

   ```bash
   kubectl rollout restart deployment/enterprise-gateway -n enterprise-gateway
   ```

   - Picks up new image versions
   - Zero-downtime rolling update

1. **Displays Enterprise Gateway service URL** for verification

**When to use this script:**

- After modifying Enterprise Gateway source code
- After updating kernel image definitions
- When testing new features or bug fixes
- Before creating pull requests

**Note**: The script assumes you have push access to the `lresende` DockerHub organization. Modify `HUB_ORG` in the script if using a different registry.

## Configuration Files

### enterprise-gateway-minikube-helm.yaml

Helm values for Enterprise Gateway deployment:

- **Image**: `lresende/enterprise-gateway:dev`
- **Kernel Configuration**:
  - Allowed kernels: `ray_python_operator`, `python_kubernetes`
  - Default kernel: `ray_python_operator`
  - Launch/timeout settings: 500 seconds (helpful for debugging)
  - Idle timeout: 3600 seconds (1 hour)
- **Service**: NodePort on 30088 (HTTP) and 30077 (responses)
- **RBAC**: Enabled with `enterprise-gateway-sa` service account
- **KIP**: Enabled for pre-pulling kernel images from Docker Hub

### jupyterhub-config.yaml

JupyterHub configuration with custom spawner:

- **Database**: In-memory SQLite (not for production!)
- **Authenticator**: Admin users configured (root, jovyan, lresende)
- **Custom Spawner**: `CustomKubeSpawner` extends KubeSpawner
  - Sets `JUPYTER_GATEWAY_URL` to Enterprise Gateway service
  - Configures kernel namespace: `enterprise-gateway`
  - Sets service account: `enterprise-gateway-sa`
  - Passes username to kernels via environment variables
- **Single-user Image**: `quay.io/jupyterhub/k8s-singleuser-sample:4.3.1`
- **Storage**: Ephemeral (type: none) - notebooks are not persisted
- **Default UI**: JupyterLab (`/lab`)

### enterprise-gateway-network.yaml

Kubernetes NetworkPolicy that allows all traffic to/from Enterprise Gateway namespace:

- Required for Enterprise Gateway to communicate with kernels
- Allows kernels in the same namespace to connect back to gateway
- In production, consider more restrictive policies

## Usage

### Access JupyterHub

1. After installation, open the URL displayed by the script
1. Log in with username: `root`, `jovyan`, or `lresende` (any password works in dev mode)
1. Wait for your user pod to start (first launch may take 1-2 minutes)

### Launch a Ray Kernel

1. In JupyterLab, create a new notebook
1. Select kernel: **Ray Python (ray_python_operator)**
1. Run Python code that executes on Ray:

```python
import ray
ray.init(address='auto')

@ray.remote
def compute_pi(n):
    import random
    count = sum(1 for _ in range(n)
                if random.random()**2 + random.random()**2 <= 1)
    return 4.0 * count / n

# Distributed computation across Ray cluster
futures = [compute_pi.remote(1000000) for _ in range(10)]
results = ray.get(futures)
print(f"Pi estimate: {sum(results) / len(results)}")
```

### Verify Cluster Status

```bash
# Check all pods across namespaces
kubectl get pods --all-namespaces

# Check Enterprise Gateway logs
kubectl logs -n enterprise-gateway deployment/enterprise-gateway -f

# Check JupyterHub logs
kubectl logs -n hub deployment/hub -f

# List running Ray clusters
kubectl get rayclusters --all-namespaces

# Access Enterprise Gateway directly
minikube -p ray service enterprise-gateway -n enterprise-gateway --url
```

## Troubleshooting

### Minikube won't start

```bash
# Clean up and retry
minikube -p ray delete
./install-minikube-ray.sh
```

### Pods stuck in ImagePullBackOff

```bash
# Verify images are loaded
minikube -p ray image ls | grep lresende

# Re-run update script
./update-minikube-ray.sh
```

### Kernels fail to start

Check timeout settings and logs:

```bash
# View Enterprise Gateway logs
kubectl logs -n enterprise-gateway deployment/enterprise-gateway --tail=100

# Check kernel pods
kubectl get pods -n enterprise-gateway -l kernel_id

# Describe a failing pod
kubectl describe pod -n enterprise-gateway <kernel-pod-name>
```

### JupyterHub can't connect to Enterprise Gateway

Verify the service URL configuration:

```bash
# Get Enterprise Gateway service URL
kubectl get svc -n enterprise-gateway enterprise-gateway

# Should show: http://enterprise-gateway.enterprise-gateway:8888
# This matches JUPYTER_GATEWAY_URL in jupyterhub-config.yaml
```

### Ray cluster issues

```bash
# Check KubeRay operator
kubectl get pods -l app.kubernetes.io/name=kuberay-operator

# View operator logs
kubectl logs -l app.kubernetes.io/name=kuberay-operator -f
```

## Cleanup

### Stop the cluster (preserves state)

```bash
minikube -p ray stop
```

### Delete everything

```bash
minikube -p ray delete
```

This removes all data, configurations, and the Minikube VM.

## Development Tips

1. **Faster iteration**: Use `imagePullPolicy: Never` in Helm configs during development to force local image usage

1. **Debug mode**: Both Enterprise Gateway and JupyterHub are configured with debug logging enabled

1. **Resource monitoring**:

   ```bash
   # Watch resource usage
   kubectl top nodes
   kubectl top pods --all-namespaces
   ```

1. **Port forwarding** (alternative to NodePort):

   ```bash
   kubectl port-forward -n hub svc/proxy-public 8000:80
   kubectl port-forward -n enterprise-gateway svc/enterprise-gateway 8888:8888
   ```

1. **Multi-arch builds**: Uncomment the `MULTIARCH_BUILD=true` line in `update-minikube-ray.sh` if building for ARM and x86 architectures

## References

- [Jupyter Enterprise Gateway Documentation](https://jupyter-enterprise-gateway.readthedocs.io/)
- [KubeRay Documentation](https://docs.ray.io/en/latest/cluster/kubernetes/index.html)
- [JupyterHub on Kubernetes](https://z2jh.jupyter.org/)
- [Ray Documentation](https://docs.ray.io/)

## License

This configuration is part of the Jupyter Enterprise Gateway project. See the parent repository for license information.
