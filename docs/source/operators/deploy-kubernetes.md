# Kubernetes deployments

## Overview

This section describes how to deploy Enterprise Gateway into an existing Kubernetes cluster.

Enterprise Gateway is provisioned as a Kubernetes _deployment_ and exposed as a Kubernetes _service_. Enterprise Gateway can leverage load balancing and high availability functionality provided by Kubernetes (although HA cannot be fully realized until Enterprise Gateway supports persistent sessions).

The following sample kernel specifications apply to Kubernetes deployments:

- R_kubernetes
- python_kubernetes
- python_tf_gpu_kubernetes
- python_tf_kubernetes
- scala_kubernetes
- spark_R_kubernetes
- spark_python_kubernetes
- spark_scala_kubernetes
- spark_python_operator

Enterprise Gateway deployments use the [elyra/enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) image from the Enterprise Gateway dockerhub organization [elyra](https://hub.docker.com/r/elyra/) along with other kubernetes-based images. See [Docker Images](../contributors/docker.md) for image details.

When deployed within a [spark-on-kubernetes](https://spark.apache.org/docs/latest/running-on-kubernetes.html) cluster, Enterprise Gateway can easily support cluster-managed kernels distributed across the cluster. Enterprise Gateway will also provide standalone (i.e., _vanilla_) kernel invocation (where spark contexts are not automatically created) which also benefits from their distribution across the cluster.

````{note}
If you plan to use kernel specifications derived from the `spark_python_operator` sample, ensure that the
[Kubernetes Operator for Apache Spark is installed](https://github.com/GoogleCloudPlatform/spark-on-k8s-operator#installation)
in your Kubernetes cluster.

```{tip}
To ensure the proper flow of environment variables to your spark application, make sure the
webhook server is enabled when deploying the helm chart:

`helm install my-release spark-operator/spark-operator --namespace spark-operator --set webhook.enable=true`
````

We are using helm templates to manage Kubernetes resource configurations, which allows an end-user to easily customize their Enterprise Gateway deployment.

There are two main deployment scenarios if RBAC is enabled in your Kubernetes cluster:

1. Deployment user has **_Cluster Administrator Access_**. In this scenario, you have full access to the cluster and can deploy all components as needed.
1. Deployment user has **_Namespace Administrator Access_**. This is typical for shared multi-tenant environments where each Team has control over their namespace, but not the cluster. In this scenario, your cluster Administrator can deploy the RBAC resources and Kernel Image Puller and you can deploy Enterprise Gateway.

## Prerequisites

- Install and configure [kubectl](https://kubernetes.io/docs/tasks/tools/) and [helm3](https://helm.sh/docs/intro/install/) on your workstation.

- Create the kubernetes namespace where you want to deploy Enterprise Gateway, for example:

  ```sh
  kubectl create namespace enterprise-gateway
  ```

- If you use RBAC, you will need cluster Admin access to configure RBAC resources

- If you plan to use Private docker registry, you will need to have credentials (see configuration steps below)

Once the Kubernetes cluster is configured and `kubectl` is demonstrated to be working, it is time to deploy Enterprise Gateway. There are a couple of different deployment options - using helm or kubectl.

## Deploying with helm

Choose this option if you want to deploy via a [helm](https://helm.sh/) chart. You can customize your deployment using value files - review the configuration section below for details.

### Create the Enterprise Gateway kubernetes service and deployment

You can execute the helm command from the checked-out release of the Enterprise Gateway git [repository](https://github.com/jupyter-server/enterprise_gateway.git):

```bash
helm  upgrade --install  enterprise-gateway \
  etc/kubernetes/helm/enterprise-gateway \
   --kube-context [mycluster-context-name] \
   --namespace [namespace-name]

```

Alternatively, the helm chart tarball is also accessible as an asset on our [release](https://github.com/jupyter-server/enterprise_gateway/releases) page, replace \[VERSION\] with specific release version you want to use:

```bash
helm  upgrade --install  enterprise-gateway \
  https://github.com/jupyter-server/enterprise_gateway/releases/download/v[VERSION]/jupyter_enterprise_gateway_helm-[VERSION].tar.gz \
   --kube-context [mycluster-context-name] \
   --namespace [namespace-name]
```

### Access to Enterprise Gateway from outside the cluster

Take a look at the Kubernetes [documentation](https://kubernetes.io/docs/tasks/access-application-cluster/access-cluster-services/#ways-to-connect) on how you can access the Kubernetes service from outside the cluster.

A Kubernetes Ingress is the most user-friendly way of interacting with the service and that is what we will cover in this section.
If you do not have a Kubernetes Ingress configured on your cluster the easiest way to get access will be using the NodePort service.

#### Kubernetes Ingress Setup

##### Prerequisites

- Ingress controller deployed on your Kubernetes cluster. Review the Kubernetes [documentation](https://kubernetes.io/docs/concepts/services-networking/ingress/) for available options.
- Wildcard DNS record is configured to point to the IP of the LoadBalancer, which frontends your ingress controller
- Review specific Ingress controller configuration to enable wildcard path support if you are using Kubernetes version \< v1.18
- With Kubernetes v1.18 Ingress uses `PathType` parameter which is set to `Prefix` in the helm chart by default, so no additional configuration is required
- Refer to your ingress controller documentation on how to set up TLS with your ingress

##### Update Helm deployment to enable ingress

Create file `values-ingress.yaml` with the following content:

```bash
ingress:
  enabled: true
  # Ingress resource host
  hostName: "[unique-fully-qualified-domain-name]"

```

Add this file to your helm command and apply to the cluster replacing \[PLACEHOLDER\] with appropriate values for your environment:

```bash
helm  upgrade --install enterprise-gateway \
  etc/kubernetes/helm/enterprise-gateway \
   --kube-context [mycluster-context-name] \
   --namespace [namespace-name] \
   -f values-ingress.yaml
```

## Basic Full Configuration Example of Enterprise Gateway Deployment

### Option 1. Use Kubernetes Ingress

Create file `values-full.yaml` with the following content:

```bash
service:
  type: "ClusterIP"
  ports:
    # The primary port on which Enterprise Gateway is servicing requests.
    - name: "http"
      port: 8888
      targetPort: 8888
    # The  port on which Enterprise Gateway will receive kernel connection info responses.
    - name: "http-response"
      port: 8877
      targetPort: 8877
deployment:
  # Update CPU/Memory as needed
  resources:
    limits:
      cpu: 2
      memory: 10Gi
    requests:
      cpu: 1
      memory: 2Gi
  # Update to deploy multiple replicas of EG.
  replicas: 2
  # Give Enteprise Gateway some time to gracefully shutdown
  terminationGracePeriodSeconds: 60

kip:
  enabled: false # turn this off, if running DaemonSets is restricted by your cluster Administrator

ingress:
  enabled: true
  # Ingress resource host
  hostName: "[unique-fully-qualified-domain-name]"

```

### Option 2. Use NodePort Service

Create file `values-full.yaml` with the following content, you can set the node port value or have Kubernetes allocate a random port:

```bash
service:
  type: "NodePort"
  ports:
    # The primary port on which Enterprise Gateway is servicing requests.
    - name: "http"
      port: 8888
      targetPort: 8888
    #  nodePort: 32652 # optional nodePort
    # The  port on which Enterprise Gateway will receive kernel connection info responses.
    - name: "http-response"
      port: 8877
      targetPort: 8877
    #  nodePort: 30481 # optional nodePort

deployment:
  # Update CPU/Memory as needed
  resources:
    limits:
      cpu: 2
      memory: 10Gi
    requests:
      cpu: 1
      memory: 2Gi
  # Update to deploy multiple replicas of EG.
  replicas: 2
  # Give Enteprise Gateway some time to gracefully shutdown
  terminationGracePeriodSeconds: 60

kip:
  enabled: false # turn this off, if running DaemonSets is restricted by your cluster Administrator

ingress:
  enabled: false
```

### Option 3. Use NodePort Service with Private Docker Registry

Create file `values-full.yaml` with the following content, you can set the node port value or have Kubernetes allocate a random port:

```bash
global:
  # Create RBAC resources
  rbac: true
  # ImagePullSecrets for a ServiceAccount, list of secrets in the same namespace
  # to use for pulling any images in pods that reference this ServiceAccount.
  # Must be set for any cluster configured with private docker registry.
  imagePullSecrets:
    - private-registry-key # provide the name of the secret to use

# You can optionally create imagePull Secrets
imagePullSecretsCreate:
  enabled: false
  annotations: {}
    # this annotation allows you to keep the secret even if the helm release is deleted
    # "helm.sh/resource-policy": "keep"
  secrets:
    - private-registry-key # provide the name of the secret to create

service:
  type: "NodePort"
  ports:
    # The primary port on which Enterprise Gateway is servicing requests.
    - name: "http"
      port: 8888
      targetPort: 8888
    #  nodePort: 32652 # optional nodePort
    # The  port on which Enterprise Gateway will receive kernel connection info responses.
    - name: "http-response"
      port: 8877
      targetPort: 8877
    #  nodePort: 30481 # optional nodePort

# Enterprise Gateway image name and tag to use from private registry.
image: private.io/elyra/enterprise-gateway:dev

deployment:
  # Update CPU/Memory as needed
  resources:
    limits:
      cpu: 2
      memory: 10Gi
    requests:
      cpu: 1
      memory: 2Gi
  # Update to deploy multiple replicas of EG.
  replicas: 2
  # Give Enteprise Gateway some time to gracefully shutdown
  terminationGracePeriodSeconds: 60

kip:
  enabled: false # turn this off, if running DaemonSets is restricted by your cluster Administrator
  # Kernel Image Puller image name and tag to use from private registry.
  image: private.io/elyra/kernel-image-puller:dev

ingress:
  enabled: false
```

### Deploy with helm

Add values file to your helm command and apply to the cluster replacing \[PLACEHOLDER\] with appropriate values for your environment:

```bash
helm  upgrade --install enterprise-gateway
  etc/kubernetes/helm/enterprise-gateway \
   --kube-context [mycluster-context-name] \
   --namespace [namespace-name] \
   -f values-full.yaml
```

if you are using private registry add setting base64 encoded secret value to you command:
`--set imagePullSecretsCreate.secrets[0].data="UHJvZCBTZWNyZXQgSW5mb3JtYXRpb24K"`

### Deploy with kubectl

Choose this deployment option if you want to deploy directly from Kubernetes template files with kubectl, rather than using a package manager like helm.

Add values file to your helm command and generate `yaml` files replacing \[PLACEHOLDER\] with appropriate values for your environment:

```bash
helm template \
  --output-dir [/tmp/mydeployment] \
  enterprise-gateway \
  etc/kubernetes/helm/enterprise-gateway \
   --namespace [namespace-name] \
   -f values-full.yaml
```

if you are using private registry add setting base64 encoded secret value to you command:
`--set imagePullSecretsCreate.secrets[0].data="UHJvZCBTZWNyZXQgSW5mb3JtYXRpb24K"`

Now you can review generated `yaml` files and apply them to your Kubernetes cluster:

```bash
kubectl apply -f /tmp/mydeployment/enterprise-gateway/templates/
```

```{important}
Never store secrets in your source code control files!
```

### Validation

You can start jupyter notebook to connect to the configured endpoint `http://jupyter-e-gw.example.com`

## Advanced Configuration Example of Enterprise Gateway Deployment

If you need to deploy Enterprise Gateway to a restricted Kubernetes cluster with _RBAC_ and _PodSecurityPolicies_ enabled, you may want to consider deploying Enterprise Gateway components as separate helm releases:

### 1. Helm release which will configure required RBAC, PSP, and service accounts

- Typically, this will be done by the Cluster Administrator.

Create `values-rbac.yaml` file with the following content:

```bash
global:
  # Create RBAC resources
  rbac: true
  serviceAccountName: 'enterprise-gateway-sa'

deployment:
  enabled: false

ingress:
  enabled: false

kip:
  enabled: false
  serviceAccountName: 'kernel-image-puller-sa'
  podSecurityPolicy:
    create: true
```

Run helm deploy:

```bash
helm  upgrade --install enterprise-gateway \
  etc/kubernetes/helm/enterprise-gateway \
   --kube-context [mycluster-context-name] \
   --namespace [namespace-name] \
   -f values-rbac.yaml
```

### 2. Helm release to deploy Kernel Image Puller

- Typically, this will be done by the Cluster Administrator.

Create `values-kip.yaml` file with the following content:

```bash
global:
  # Create RBAC resources
  rbac: true

deployment:
  enabled: false

ingress:
  enabled: false

# Kernel Image Puller (daemonset)
kip:
  enabled: true
  serviceAccountName: 'kernel-image-puller-sa'
  podSecurityPolicy:
    create: false
  resources:
    limits:
      cpu: 100m
      memory: 200Mi
    requests:
      cpu: 50m
      memory: 100Mi
```

Run helm deploy:

```bash
helm  upgrade --install enterprise-gateway \
  etc/kubernetes/helm/enterprise-gateway \
   --kube-context [mycluster-context-name] \
   --namespace [namespace-name] \
   -f values-kip.yaml
```

### 3. Helm release to deploy Enterprise Gateway

- This can be done by namespace Administrator.

Create `values-eg.yaml` file with the following content:

```bash
global:
  rbac: false

service:
  type: "ClusterIP"
  ports:
    # The primary port on which Enterprise Gateway is servicing requests.
    - name: "http"
      port: 8888
      targetPort: 8888
      # nodePort: 32652 # optional nodePort
    # The  port on which Enterprise Gateway will receive kernel connection info responses.
    - name: "http-response"
      port: 8877
      targetPort: 8877
      # nodePort: 30481 # optional nodePort

deployment:
  enabled: true
  resources:
    limits:
      cpu: 2
      memory: 10Gi
    requests:
      cpu: 500m
      memory: 2Gi
  # Update to deploy multiple replicas of EG.
  replicas: 1
  # Give Enteprise Gateway some time to gracefully shutdown
  terminationGracePeriodSeconds: 60

ingress:
  enabled: true
  # Ingress resource host
  hostName: "[unique-fully-qualified-domain-name]"

kip:
  enabled: false

```

Run helm deploy:

```bash
helm  upgrade --install enterprise-gateway \
  etc/kubernetes/helm/enterprise-gateway \
   --kube-context [mycluster-context-name] \
   --namespace [namespace-name] \
   -f values-eg.yaml
```

## Helm Configuration Parameters

Here are the values that you can set when deploying the helm chart. You
can override them with helm's `--set` or `--values` options. Always use `--set` to configure secrets.

| **Parameter**                              | **Description**                                                                                                                                                                                                                                  | **Default**                                                                    |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| `global.rbac`                              | Create Kubernetes RBAC resources                                                                                                                                                                                                                 | `true`                                                                         |
| `global.commonLabels`                      | Common labels to apply to daemonset and deployment resources                                                                                                                                                                                     | `{}`                                                                           |
| `global.imagePullSecrets`                  | Optional array of image pull secrets for Service Account for pulling images from private service registries                                                                                                                                      | \[\]                                                                           |
| `imagePullSecretsCreate.enabled`           | Optional enable creation of the Kubernetes secrets to access private registries.                                                                                                                                                                 | 'false'                                                                        |
| `imagePullSecretsCreate.annotations`       | Annotations for Kubernetes secrets                                                                                                                                                                                                               | '{}'                                                                           |
| `imagePullSecretsCreate.secrets`           | Array of Kubernetes secrets to create with the following structure: `name` - secret name and `data` - base64 encoded Secret value. Example: `{ name: "myregistrykey", data: "SGVsbG8gc2VjcmV0Cg==" }`                                            | '\[\]'                                                                         |
| `image`                                    | Enterprise Gateway image name and tag to use. Ensure the tag is updated to the version of Enterprise Gateway you wish to run.                                                                                                                    | `elyra/enterprise-gateway:VERSION`, where `VERSION` is the release being used  |
| `imagePullPolicy`                          | Enterprise Gateway image pull policy. Use `IfNotPresent` policy so that dev-based systems don't automatically update. This provides more control. Since formal tags will be release-specific this policy should be sufficient for them as well.  | `IfNotPresent`                                                                 |
| `service.type`                             | Kubernetes Service Type - Nodeport,ClusterIP,LoadBalancer                                                                                                                                                                                        | `ClusterIP`                                                                    |
| `service.externalIPs.k8sMasterPublicIP`    | Master public IP on which to expose EG.                                                                                                                                                                                                          | nil                                                                            |
| `service.ports`                            | An array of service ports for Kubernetes Service                                                                                                                                                                                                 | see below                                                                      |
| `service.ports[0].name`                    | The primary port name for Enterprise Gateway is servicing requests.                                                                                                                                                                              | `http`                                                                         |
| `service.ports[0].port`                    | The primary port on which Enterprise Gateway is servicing requests.                                                                                                                                                                              | `8888`                                                                         |
| `service.ports[1].name`                    | The port name on which Enterprise Gateway will receive kernel connection info responses.                                                                                                                                                         | `http-response`                                                                |
| `service.ports[1].port`                    | The port on which Enterprise Gateway will receive kernel connection info responses.                                                                                                                                                              | `8877`                                                                         |
| `deployment.enabled`                       | flag to enable run Enterprise Gateway deployment                                                                                                                                                                                                 | `true`                                                                         |
| `deployment.serviceAccountName`            | Kubernetes Service Account to run Enterprise Gateway                                                                                                                                                                                             | `enterprise-gateway-sa`                                                        |
| `deployment.tolerations`                   | Kubernetes tolerations for Enterprise Gateway pods to ensure that pods are not scheduled onto inappropriate nodes                                                                                                                                | `[]`                                                                           |
| `deployment.affinity`                      | Kubernetes affinity for Enterprise Gateway pods to keep pods scheduled onto appropriate nodes                                                                                                                                                    | `{}`                                                                           |
| `deployment.nodeSelector`                  | Kubernetes nodeselector for Enterprise Gateway pods to keep pods scheduled onto appropriate nodes - simpler alternative to tolerations and affinity                                                                                              | `{}`                                                                           |
| `deployment.terminationGracePeriodSeconds` | Time to wait for Enterprise Gateway to gracefully shutdown.                                                                                                                                                                                      | `30`                                                                           |
| `deployment.resources`                     | set Enterprise Gateway container resources.                                                                                                                                                                                                      | valid Yaml resources, see values file for example                              |
| `deployment.replicas`                      | Update to deploy multiple replicas of EG.                                                                                                                                                                                                        | `1`                                                                            |
| `deployment.extraEnv`                      | Additional environment variables to set for Enterprise Gateway.                                                                                                                                                                                  | `{}`                                                                           |
| `logLevel`                                 | Log output level.                                                                                                                                                                                                                                | `DEBUG`                                                                        |
| `mirrorWorkingDirs`                        | Whether to mirror working directories. NOTE: This requires appropriate volume mounts to make notebook dir accessible.                                                                                                                            | `false`                                                                        |
| `authToken`                                | Optional authorization token passed in all requests (see --EnterpriseGatewayApp.auth_token)                                                                                                                                                      | `nil`                                                                          |
| `kernel.clusterRole`                       | Kernel cluster role created by this chart. Used if no KERNEL_NAMESPACE is provided by client.                                                                                                                                                    | `kernel-controller`                                                            |
| `kernel.shareGatewayNamespace`             | Will start kernels in the same namespace as EG if True.                                                                                                                                                                                          | `false`                                                                        |
| `kernel.launchTimeout`                     | Timeout for kernel launching in seconds.                                                                                                                                                                                                         | `60`                                                                           |
| `kernel.cullIdleTimeout`                   | Idle timeout in seconds. Default is 1 hour.                                                                                                                                                                                                      | `3600`                                                                         |
| `kernel.cullConnected`                     | Whether to cull idle kernels that still have clients connected.                                                                                                                                                                                  | `false`                                                                        |
| `kernel.allowedKernels`                    | List of kernel names that are available for use.                                                                                                                                                                                                 | `{r_kubernetes,...}` (see `values.yaml`)                                       |
| `kernel.defaultKernelName`                 | Default kernel name should be something from the allowedKernels                                                                                                                                                                                  | `python-kubernetes`                                                            |
| `kernelspecs.image`                        | Optional custom data image containing kernelspecs to use. Cannot be used with NFS enabled.                                                                                                                                                       | `nil`                                                                          |
| `kernelspecs.imagePullPolicy`              | Kernelspecs image pull policy.                                                                                                                                                                                                                   | `Always`                                                                       |
| `nfs.enabled`                              | Whether NFS-mounted kernelspecs are enabled. Cannot be used with `kernelspecs.image` set.                                                                                                                                                        | `false`                                                                        |
| `nfs.internalServerIPAddress`              | IP address of NFS server. Required if NFS is enabled.                                                                                                                                                                                            | `nil`                                                                          |
| `nfs.internalServerIPAddress`              | IP address of NFS server. Required if NFS is enabled.                                                                                                                                                                                            | `nil`                                                                          |
| `kernelspecsPvc.enabled`                   | Use a persistent volume claim to store kernelspecs in a persistent volume                                                                                                                                                                        | `false`                                                                        |
| `kernelspecsPvc.name`                      | PVC name. Required if want mount kernelspecs without nfs. PVC should create in the same namespace before EG deployed.                                                                                                                            | `nil`                                                                          |
| `ingress.enabled`                          | Whether to include an EG ingress resource during deployment.                                                                                                                                                                                     | `false`                                                                        |
| `ingress.ingressClassName`                 | Specify a Kubernetes ingress class name for enterprise gateway deployment ingress deployment.                                                                                                                                                    | `""`                                                                           |
| `ingress.hostName`                         | Kubernetes Ingress hostname, required. .                                                                                                                                                                                                         | nil                                                                            |
| `ingress.pathType`                         | Kubernetes Ingress PathType (`ImplementationSpecific`,`Prefix`).                                                                                                                                                                                 | `Prefix`                                                                       |
| `ingress.path`                             | Kubernetes Ingress Path.                                                                                                                                                                                                                         | `/`                                                                            |
| `ingress.annotations`                      | Use annotations to configure ingress. See examples for Traefik and nginx. NOTE: A traefik or nginx controller must be installed and `ingress.enabled` must be set to `true`.                                                                     | see values file for examples                                                   |
| `kip.enabled`                              | Whether the Kernel Image Puller should be used                                                                                                                                                                                                   | `true`                                                                         |
| `kip.podSecurityPolicy.create`             | enable creation of PSP for Image Puller, requires `global.rbac: true` and non-empy KIP service account                                                                                                                                           | `false`                                                                        |
| `kip.podSecurityPolicy.annotatons`         | annotations for Image Puller PSP account                                                                                                                                                                                                         | `{}`                                                                           |
| `kip.tolerations`                          | Kubernetes tolerations for Kernel Image Puller pods to ensure that pods are not scheduled onto inappropriate nodes                                                                                                                               | `[]`                                                                           |
| `kip.affinity`                             | Kubernetes affinity for Kernel Image Puller pods to keep pods scheduled onto appropriate nodes                                                                                                                                                   | `{}`                                                                           |
| `kip.nodeSelector`                         | Kubernetes nodeselector for Kernel Image Puller pods to keep pods scheduled onto appropriate nodes - simpler alternative to tolerations and affinity                                                                                             | `{}`                                                                           |
| `kip.serviceAccountName`                   | Kubernetes Service Account to run Kernel Image Puller Gateway                                                                                                                                                                                    | `kernel-image-puller-sa`                                                       |
| `kip.resources`                            | set Kernel Image Puller container resources.                                                                                                                                                                                                     | valid Yaml resources, see values file for example                              |
| `kip.image`                                | Kernel Image Puller image name and tag to use. Ensure the tag is updated to the version of the Enterprise Gateway release you wish to run.                                                                                                       | `elyra/kernel-image-puller:VERSION`, where `VERSION` is the release being used |
| `kip.imagePullPolicy`                      | Kernel Image Puller image pull policy. Use `IfNotPresent` policy so that dev-based systems don't automatically update. This provides more control. Since formal tags will be release-specific this policy should be sufficient for them as well. | `IfNotPresent`                                                                 |
| `kip.interval`                             | The interval (in seconds) at which the Kernel Image Puller fetches kernelspecs to pull kernel images.                                                                                                                                            | `300`                                                                          |
| `kip.pullPolicy`                           | Determines whether the Kernel Image Puller will pull kernel images it has previously pulled (`Always`) or only those it hasn't yet pulled (`IfNotPresent`)                                                                                       | `IfNotPresent`                                                                 |
| `kip.criSocket`                            | The container runtime interface socket, use `/run/containerd/containerd.sock` for containerd installations                                                                                                                                       | `/var/run/docker.sock`                                                         |
| `kip.defaultContainerRegistry`             | Prefix to use if a registry is not already specified on image name (e.g., elyra/kernel-py:VERSION)                                                                                                                                               | `docker.io`                                                                    |
| `kip.fetcher`                              | fetcher to fetch image names, defaults to KernelSpecsFetcher                                                                                                                                                                                     | `KernelSpecsFetcher`                                                           |
| `kip.images`                               | if StaticListFetcher is used KIP_IMAGES defines the list of images pullers will fetch                                                                                                                                                            | `[]`                                                                           |
| `kip.internalFetcher `                     | if CombinedImagesFetcher is used KIP_INTERNAL_FETCHERS defines the fetchers that get used internally                                                                                                                                             | `KernelSpecsFetcher`                                                           |

## Uninstalling Enterprise Gateway

When using helm, you can uninstall Enterprise Gateway with the following command:

```bash
helm uninstall enterprise-gateway \
  --kube-context [mycluster-context-name] \
   --namespace [namespace-name]
```

## Enterprise Gateway Deployment Details

Enterprise Gateway is deployed as a Kubernetes deployment and exposed by a Kubernetes service. It can be accessed by the service name `enterprise-gateway` within the cluster. In addition, all objects related to Enterprise Gateway, including kernel instances, have the kubernetes label of `app=enterprise-gateway` applied.

The Enterprise Gateway Kubernetes service _type_ can be:

- `NodePort`: allows to access Enterprise Gateway with `http://[worker IP]:[NodePort]` or having a load balancer route traffic to `http://[worker IP's]:[NodePort]`
- `LoadBalancer`: requires appropriate network plugin available
- `ClusterIP`: requires Kubernetes Ingress Controller

Kernels are stateful, therefore service is configured with a `sessionAffinity` of `ClientIP`. As a result, kernel creation requests will be routed to the same pod.

Increase the number of `replicas` of Enterprise Gateway Deployment to improve deployment availability, but because `sessionAffinity` of `ClientIP`, traffic from the same client will be sent to the same pod of the Enterprise Gateway and if that pod goes down, client will get an error and will need to reestablish connection to another pod of the Enterprise Gateway.

### Namespaces

A best practice for Kubernetes applications running in an enterprise is to isolate applications via namespaces. Since Enterprise Gateway also requires isolation at the kernel level, it makes sense to use a namespace for each kernel, by default.

The primary namespace is created prior to the initial Helm deployment (e.g., `enterprise-gateway`). This value is communicated to Enterprise Gateway via the env variable `EG_NAMESPACE`. All Enterprise Gateway components reside in this namespace.

By default, kernel namespaces are created when the respective kernel is launched. At that time, the kernel namespace name is computed from the kernel username (`KERNEL_USERNAME`) and its kernel ID (`KERNEL_ID`) just like the kernel pod name. Upon a kernel's termination, this namespace - provided it was created by Enterprise Gateway - will be deleted.

Installations wishing to pre-create the kernel namespace can do so by conveying the name of the kernel namespace via `KERNEL_NAMESPACE` in the `env` portion of the kernel creation request. (They must also provide the namespace's service account name via `KERNEL_SERVICE_ACCOUNT_NAME` - see next section.) When `KERNEL_NAMESPACE` is set, Enterprise Gateway will not attempt to create a kernel-specific namespace, nor will it attempt its deletion. As a result, kernel namespace lifecycle management is the user's responsibility.

```{tip}
If you need to associate resources to users, one suggestion is to create a namespace per user and set `KERNEL_NAMESPACE = KERNEL_USERNAME` on the client (see [Kernel Environment Variables](../users/kernel-envs.md)).
```

Although **not recommended**, installations requiring everything in the same namespace - Enterprise Gateway and all its kernels - can do so by setting the helm chart value `kernel.shareGatewayNamespace` to `true` - which is then set into the `EG_SHARED_NAMESPACE` env. When set, all kernels will run in the Enterprise Gateway namespace, essentially eliminating all aspects of isolation between kernel instances (and resources).

### Role-Based Access Control (RBAC)

Another best practice of Kubernetes applications is to define the minimally viable set of permissions for the application. Enterprise Gateway does this by defining role-based access control (RBAC) objects for both Enterprise Gateway and kernels.

Because the Enterprise Gateway pod must create kernel namespaces, pods, services (for Spark support) and role bindings, a cluster-scoped role binding is required.

The cluster role binding `enterprise-gateway-controller` also references the subject, `enterprise-gateway-sa`, which is the service account associated with the Enterprise Gateway namespace and also created by [eg-clusterrolebinding.yaml](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/kubernetes/helm/enterprise-gateway/templates/eg-clusterrolebinding.yaml)).

The [`eg-clusterrole.yaml`](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/kubernetes/helm/enterprise-gateway/templates/eg-clusterrole.yaml) defines the minimally viable roles for a kernel pod - most of which are required for Spark support.

Since kernels, by default, reside within their own namespace created upon their launch, a cluster role is used within a namespace-scoped role binding created when the kernel's namespace is created. The name of the kernel cluster role is `kernel-controller` and, when Enterprise Gateway creates the namespace and role binding, is also the name of the role binding instance.

#### Kernel Service Account Name

As noted above, installations wishing to pre-create their own kernel namespaces should provide the name of the service account associated with the namespace via `KERNEL_SERVICE_ACCOUNT_NAME` in the `env` portion of the kernel creation request (along with `KERNEL_NAMESPACE`). If not provided, the built-in namespace service account, `default`, will be referenced. In such circumstances, Enterprise Gateway will **not** create a role binding on the name for the service account, so it is the user's responsibility to ensure that the service account has the capability to perform equivalent operations as defined by the `kernel-controller` role.

#### Example Custom Namespace

Here's an example of the creation of a custom namespace (`kernel-ns`) with its own service account (`kernel-sa`) and role binding (`kernel-controller`) that references the cluster-scoped role (`kernel-controller`) and includes appropriate labels to help with administration and analysis:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: kernel-ns
  labels:
    app: enterprise-gateway
    component: kernel
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: kernel-sa
  namespace: kernel-ns
  labels:
    app: enterprise-gateway
    component: kernel
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: kernel-controller
  namespace: kernel-ns
  labels:
    app: enterprise-gateway
    component: kernel
subjects:
  - kind: ServiceAccount
    name: kernel-sa
    namespace: kernel-ns
roleRef:
  kind: ClusterRole
  name: kernel-controller
  apiGroup: rbac.authorization.k8s.io
```

### Kernel Image Puller

Kernels docker images can be big and their download from a container repository (e.g., docker.io or quay.io), which may cause slow kernel pod startup whenever the kernel image is first accessed on any given node.

To mitigate this issue, Enterprise Gateway deployment includes `kernel-image-puller` or `KIP` Kubernetes DaemonSet. This DaemonSet is responsible for polling Enterprise Gateway for the current set of configured kernelspecs, picking out any configured image name references, and pulling those images to the node on which KIP is running. Because it's a daemon set, this will also address the case when new nodes are added to a configuration (although spinning up new nodes on a kernel start request will likely time out anyway).

#### KIP Configuration

`KIP` is using same kubernetes Service Account as Enterprise Gateway itself, so it will use same credentials to access private docker registry - see helm configuration section for details.

`KIP_INTERVAL` - The Kernel Image Puller can be configured for the interval at which it checks for new kernelspecs

`KIP_NUM_PULLERS`- the number of puller threads it will utilize per node ()

`KIP_NUM_RETRIES` - the number of retries it will attempt for a given image (),

`KIP_PULL_POLICY` - and the pull policy () - which essentially dictates whether it will attempt to pull images that its already encountered (`Always`) vs. only pulling the image if it hasn't seen it yet (`IfNotPresent`).

If the Enterprise Gateway defines an authentication token (`EG_AUTH_TOKEN`) then that same token should be configured here as (`KIP_AUTH_TOKEN`) so that the puller can correctly authenticate its requests.

#### KIP Container Runtime

The Kernel Image Puller also supports multiple container runtimes since Docker is no longer configured by default in Kubernetes. KIP currently supports Docker and Containerd runtimes. If another runtime is encountered, KIP will try to proceed using the Containerd client `crictl` against the configured socket. As a result, it is import that the `criSocket` value be appropriately configured relative to the container runtime. If the runtime is something other than Docker or Containerd and `crictl` isn't able to pull images, it may be necessary to manually pre-seed images or incur kernel start timeouts the first time a given node is asked to start a kernel associated with a non-resident image.

KIP also supports the notion of a _default container registry_ whereby image names that do not specify a registry (e.g., `docker.io` or `quay.io`) KIP will apply the configured default. Ideally, the image name should be fully qualified.

### Kernelspec Modifications

One of the more common areas of customization we see occurs within the kernelspec files located in `/usr/local/share/jupyter/kernels`. To accommodate the ability to customize the kernel definitions, you have two different options: NFS mounts, or custom container images. The two options are mutually exclusive, because they mount kernelspecs into the same location in the Enterprise Gateway pod.

#### Via NFS

The kernels directory can be mounted as an NFS volume into the Enterprise Gateway pod, thereby making the kernelspecs available to all EG pods within the Kubernetes cluster (provided the NFS mounts exist on all applicable nodes).

As an example, we have included the necessary entries for mounting an existing NFS mount point into the Enterprise Gateway pod. By default, these references are commented out as they require the operator to configure the appropriate NFS mounts and server IP. If you are deploying Enterprise Gateway via the helm chart, you can enable NFS directly via helm values.

Here you can see how `deployment.yaml` references use of the volume (ia `volumeMounts`
for the container specification and `volumes` in the pod specification (non-applicable entries have been omitted):

```yaml
spec:
  containers:
    # Uncomment to enable NFS-mounted kernelspecs
    volumeMounts:
      - name: kernelspecs
        mountPath: '/usr/local/share/jupyter/kernels'
  volumes:
    - name: kernelspecs
      nfs:
        server: <internal-ip-of-nfs-server>
        path: '/usr/local/share/jupyter/kernels'
```

```{tip}
Because the kernel pod definition file, [kernel-pod.yaml](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/kernel-launchers/kubernetes/scripts/kernel-pod.yaml.j2), resides in the kernelspecs hierarchy, customizations to the deployments of future kernel instances can now also take place.  In addition, these same entries can be added to the kernel-pod.yaml definitions if access to the same or other NFS mount points are desired within kernel pods. (We'll be looking at ways to make modifications to per-kernel configurations more manageable.)
```

Use of more formal persistent volume types must include the [Persistent Volume](https://kubernetes.io/docs/concepts/storage/persistent-volumes) and corresponding Persistent Volume Claim stanzas.

#### Via Custom Container Image

If you are deploying Enterprise Gateway via the helm chart, then instead of using NFS, you can build your custom kernelspecs into a container image that Enterprise Gateway consumes. Here's an example Dockerfile for such a container:

```
FROM alpine:3.9

COPY kernels /kernels
```

This assumes that your source contains a `kernels/` directory with all the kernelspecs you'd like to end up in the image, e.g. `kernels/python_kubernetes/kernel.json` and any associated files.

Once you build your custom kernelspecs image and push it to a container registry, you can refer to it from your helm deployment. For instance:

```bash
helm upgrade --install --atomic --namespace enterprise-gateway enterprise-gateway etc/kubernetes/helm --set kernelspecs.image=your-custom-image:latest
```

...where `your-custom-image:latest` is the image name and tag of your kernelspecs image. Once deployed, the helm chart copies the data from the `/kernels` directory of your container into the `/usr/local/share/jupyter/kernels` directory of the Enterprise Gateway pod. Note that when this happens, the built-in kernelspecs are no longer available. So include all kernelspecs that you want to be available in your container image.

Also, you should update the helm chart `kernel.allowedKernels` (or usually comprehended as kernel whitelist) value with the name(s) of your custom kernelspecs.

## Kubernetes Kernel Instances

There are essentially two kinds of kernels (independent of language) launched within an Enterprise Gateway Kubernetes cluster - _vanilla_ and _spark-on-kubernetes_ (if available).

When _vanilla_ kernels are launched, Enterprise Gateway is responsible for creating the corresponding pod. On the other hand, _spark-on-kubernetes_ kernels are launched via `spark-submit` with a specific `master` URI - which then creates the corresponding pod(s) (including executor pods). Images can be launched using both forms provided they have the appropriate support for Spark installed.

Here's the yaml configuration used when _vanilla_ kernels are launched. As noted in the `KubernetesProcessProxy` section below, this file ([kernel-pod.yaml.j2](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/kernel-launchers/kubernetes/scripts/kernel-pod.yaml.j2)) serves as a template where each of the tags surrounded with `{{` and `}}` represent variables that are substituted at the time of the kernel's launch. All `{{ kernel_xxx }}` parameters correspond to `KERNEL_XXX` environment variables that can be specified from the client in the kernel creation request's json body.

```yaml+jinja
apiVersion: v1
kind: Pod
metadata:
  name: "{{ kernel_pod_name }}"
  namespace: "{{ kernel_namespace }}"
  labels:
    kernel_id: "{{ kernel_id }}"
    app: enterprise-gateway
    component: kernel
spec:
  restartPolicy: Never
  serviceAccountName: "{{ kernel_service_account_name }}"
  {% if kernel_uid is defined or kernel_gid is defined %}
  securityContext:
    {% if kernel_uid is defined %}
    runAsUser: {{ kernel_uid | int }}
    {% endif %}
    {% if kernel_gid is defined %}
    runAsGroup: {{ kernel_gid | int }}
    {% endif %}
    fsGroup: 100
  {% endif %}
  containers:
  - env:
    - name: EG_RESPONSE_ADDRESS
      value: "{{ eg_response_address }}"
    - name: EG_PUBLIC_KEY
      value: "{{ eg_public_key }}"
    - name: KERNEL_LANGUAGE
      value: "{{ kernel_language }}"
    - name: KERNEL_SPARK_CONTEXT_INIT_MODE
      value: "{{ kernel_spark_context_init_mode }}"
    - name: KERNEL_NAME
      value: "{{ kernel_name }}"
    - name: KERNEL_USERNAME
      value: "{{ kernel_username }}"
    - name: KERNEL_ID
      value: "{{ kernel_id }}"
    - name: KERNEL_NAMESPACE
      value: "{{ kernel_namespace }}"
    image: "{{ kernel_image }}"
    name: "{{ kernel_pod_name }}"
```

There are a number of items worth noting:

1. Kernel pods can be identified in three ways using `kubectl`:

   1. By the global label `app=enterprise-gateway` - useful when needing to identify all related objects (e.g., `kubectl get all -l app=enterprise-gateway`)
   1. By the _kernel_id_ label `kernel_id=<kernel_id>` - useful when only needing specifics about a given kernel. This label is used internally by enterprise-gateway when performing its discovery and lifecycle management operations.
   1. By the _component_ label `component=kernel` - useful when needing to identity only kernels and not other enterprise-gateway components. (Note, the latter can be isolated via `component=enterprise-gateway`.)

   Note that since kernels run in isolated namespaces by default, it's often helpful to include the clause `--all-namespaces` on commands that will span namespaces. To isolate commands to a given namespace, you'll need to add the namespace clause `--namespace <namespace-name>`.

1. Each kernel pod is named by the invoking user (via the `KERNEL_USERNAME` env) and its kernel_id (env `KERNEL_ID`). This identifier also applies to those kernels launched within `spark-on-kubernetes`.

1. Kernel pods use the specified `securityContext`. If env `KERNEL_UID` is not specified in the kernel creation request a default value of `1000` (the jovyan user) will be used. Similarly, for `KERNEL_GID`, whose default is `100` (the users group). In addition, Enterprise Gateway enforces a list of prohibited UID and GID values. By default, this list is initialized to the 0 (root) UID and GID. Administrators can configure the `EG_PROHIBITED_UIDS` and `EG_PROHIBITED_GIDS` environment variables via the `deployment.yaml` file with comma-separated values to alter the set of user and group ids to be prevented.

1. As noted above, if `KERNEL_NAMESPACE` is not provided in the request, Enterprise Gateway will create a namespace using the same naming algorithm for the pod. In addition, the `kernel-controller` cluster role will be bound to a namespace-scoped role binding of the same name using the namespace's default service account as its subject. Users wishing to use their own kernel namespaces must provide **both** `KERNEL_NAMESPACE` and `KERNEL_SERVICE_ACCOUNT_NAME` as these are both used in the `kernel-pod.yaml.j2` as `{{ kernel_namespace }}` and `{{ kernel_service_account_name }}`, respectively.

1. Kernel pods have restart policies of `Never`. This is because the Jupyter framework already has built-in logic for auto-restarting failed kernels and any other restart policy would likely interfere with the built-in behaviors.

1. The parameters to the launcher that is built into the image are communicated via environment variables as noted in the `env:` section above.

## Unconditional Volume Mounts

Unconditional volume mounts can be added in the `kernel-pod.yaml.j2` template. An example of these unconditional volume mounts can be found when extending docker shared memory. For some I/O jobs the pod will need more than the default `64mb` of shared memory on the `/dev/shm` path.

```yaml+jinja
volumeMounts:
# Define any "unconditional" mounts here, followed by "conditional" mounts that vary per client
{% if kernel_volume_mounts %}
  {% for volume_mount in kernel_volume_mounts %}
- {{ volume_mount }}
  {% endfor %}
{% endif %}
volumes:
# Define any "unconditional" volumes here, followed by "conditional" volumes that vary per client
{% if kernel_volumes %}
{% for volume in kernel_volumes %}
- {{ volume }}
{% endfor %}
{% endif %}
```

The conditional volumes are handled by the loops inside the yaml file. Any unconditional volumes can be added before these conditions. In the scenario where the `/dev/shm` will need to be expanded the following mount has to be added.

```yaml+jinja
volumeMounts:
# Define any "unconditional" mounts here, followed by "conditional" mounts that vary per client
- mountPath: /dev/shm
  name: dshm
{% if kernel_volume_mounts %}
  {% for volume_mount in kernel_volume_mounts %}
- {{ volume_mount }}
  {% endfor %}
{% endif %}
volumes:
# Define any "unconditional" volumes here, followed by "conditional" volumes that vary per client
- name: dshm
emptyDir:
  medium: Memory
{% if kernel_volumes %}
{% for volume in kernel_volumes %}
- {{ volume }}
{% endfor %}
{% endif %}
```

## Kubernetes Resource Quotas

When deploying kernels on a Kubernetes cluster a best practice is to define request and limit quotas for CPUs, GPUs, and Memory. These quotas can be defined from the client via KERNEL\_-prefixed environment variables which are passed through to the kernel at startup.

- `KERNEL_CPUS` - CPU Request by Kernel
- `KERNEL_MEMORY` - MEMORY Request by Kernel
- `KERNEL_GPUS` - GPUS Request by Kernel
- `KERNEL_CPUS_LIMIT` - CPU Limit
- `KERNEL_MEMORY_LIMIT` - MEMORY Limit
- `KERNEL_GPUS_LIMIT` - GPUS Limit

Memory and CPU units are based on the [Kubernetes Official Documentation](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) while GPU is using the NVIDIA `nvidia.com/gpu` parameter. The desired units should be included in the variable's value.

When defined, these variables are then substituted into the appropriate location of the corresponding kernel-pod.yaml.j2 template.

```yaml+jinja
{% if kernel_cpus is defined or kernel_memory is defined or kernel_gpus is defined or kernel_cpus_limit is defined or kernel_memory_limit is defined or kernel_gpus_limit is defined %}
  resources:
    {% if kernel_cpus is defined or kernel_memory is defined or kernel_gpus is defined %}
    requests:
      {% if kernel_cpus is defined %}
      cpu: "{{ kernel_cpus }}"
      {% endif %}
      {% if kernel_memory is defined %}
      memory: "{{ kernel_memory }}"
      {% endif %}
      {% if kernel_gpus is defined %}
      nvidia.com/gpu: "{{ kernel_gpus }}"
      {% endif %}
    {% endif %}
    {% if kernel_cpus_limit is defined or kernel_memory_limit is defined or kernel_gpus_limit is defined %}
    limits:
      {% if kernel_cpus_limit is defined %}
      cpu: "{{ kernel_cpus_limit }}"
      {% endif %}
      {% if kernel_memory_limit is defined %}
      memory: "{{ kernel_memory_limit }}"
      {% endif %}
      {% if kernel_gpus_limit is defined %}
      nvidia.com/gpu: "{{ kernel_gpus_limit }}"
      {% endif %}
    {% endif %}
  {% endif %}
```

## KubernetesProcessProxy

To indicate that a given kernel should be launched into a Kubernetes configuration, the kernel.json file's `metadata` stanza must include a `process_proxy` stanza indicating a `class_name:` of `KubernetesProcessProxy`. This ensures the appropriate lifecycle management will take place relative to a Kubernetes environment.

Along with the `class_name:` entry, this process proxy stanza should also include a proxy configuration stanza which specifies the container image to associate with the kernel's pod. If this entry is not provided, the Enterprise Gateway implementation will use a default entry of `elyra/kernel-py:VERSION`. In either case, this value is made available to the rest of the parameters used to launch the kernel by way of an environment variable: `KERNEL_IMAGE`.

_(Please note that the use of `VERSION` in docker image tags is a placeholder for the appropriate version-related image tag. When kernelspecs are built via the Enterprise Gateway Makefile, `VERSION` is replaced with the appropriate version denoting the target release. A full list of available image tags can be found in the dockerhub repository corresponding to each image.)_

```json
{
  "metadata": {
    "process_proxy": {
      "class_name": "enterprise_gateway.services.processproxies.k8s.KubernetesProcessProxy",
      "config": {
        "image_name": "elyra/kernel-py:VERSION"
      }
    }
  }
}
```

As always, kernels are launched by virtue of the `argv:` stanza in their respective kernel.json files. However, when launching _vanilla_ kernels in a kubernetes environment, what gets invoked isn't the kernel's launcher, but, instead, a python script that is responsible for using the [Kubernetes Python API](https://github.com/kubernetes-client/python) to create the corresponding pod instance. The pod is _configured_ by applying the values to each of the substitution parameters into the [kernel-pod.yaml](https://github.com/jupyter-server/enterprise_gateway/blob/main/etc/kernel-launchers/kubernetes/scripts/kernel-pod.yaml.j2) file previously displayed. This file resides in the same `scripts` directory as the kubernetes launch script - `launch_kubernetes.py` - which is referenced by the kernel.json's `argv:` stanza:

```json
{
  "argv": [
    "python",
    "/usr/local/share/jupyter/kernels/python_kubernetes/scripts/launch_kubernetes.py",
    "--RemoteProcessProxy.kernel-id",
    "{kernel_id}",
    "--RemoteProcessProxy.response-address",
    "{response_address}",
    "--RemoteProcessProxy.public-key",
    "{public_key}"
  ]
}
```

By default, _vanilla_ kernels use a value of `none` for the spark context initialization mode so no context will be created automatically.

When the kernel is intended to target _Spark-on-kubernetes_, its launch is very much like kernels launched in YARN _cluster mode_, albeit with a completely different set of parameters. Here's an example `SPARK_OPTS` string value which best conveys the idea:

```
  "SPARK_OPTS": "--master k8s://https://${KUBERNETES_SERVICE_HOST}:${KUBERNETES_SERVICE_PORT} --deploy-mode cluster --name ${KERNEL_USERNAME}-${KERNEL_ID} --conf spark.kubernetes.driver.label.app=enterprise-gateway --conf spark.kubernetes.driver.label.kernel_id=${KERNEL_ID} --conf spark.kubernetes.executor.label.app=enterprise-gateway --conf spark.kubernetes.executor.label.kernel_id=${KERNEL_ID} --conf spark.kubernetes.driver.docker.image=${KERNEL_IMAGE} --conf spark.kubernetes.executor.docker.image=kubespark/spark-executor-py:v2.5.0-kubernetes-0.5.0 --conf spark.kubernetes.submission.waitAppCompletion=false",
```

Note that each of the labels previously discussed are also applied to the _driver_ and _executor_ pods.

For these invocations, the `argv:` is nearly identical to non-kubernetes configurations, invoking a `run.sh` script which essentially holds the `spark-submit` invocation that takes the aforementioned `SPARK_OPTS` as its primary parameter:

```json
{
  "argv": [
    "/usr/local/share/jupyter/kernels/spark_python_kubernetes/bin/run.sh",
    "--RemoteProcessProxy.kernel-id",
    "{kernel_id}",
    "--RemoteProcessProxy.response-address",
    "{response_address}",
    "--RemoteProcessProxy.public-key",
    "{public_key}",
    "--RemoteProcessProxy.spark-context-initialization-mode",
    "lazy"
  ]
}
```

### Confirming deployment and the service port mapping

```bash
kubectl get all --all-namespaces -l app=enterprise-gateway

NAME                        DESIRED   CURRENT   UP-TO-DATE   AVAILABLE   AGE
deploy/enterprise-gateway   1         1         1            1           2h

NAME                               DESIRED   CURRENT   READY     AGE
rs/enterprise-gateway-74c46cb7fc   1         1         1         2h

NAME                                     READY     STATUS    RESTARTS   AGE
po/enterprise-gateway-74c46cb7fc-jrkl7   1/1       Running   0          2h

NAME                     TYPE       CLUSTER-IP       EXTERNAL-IP   PORT(S)          AGE
svc/enterprise-gateway   NodePort   10.110.253.2.3   <none>        8888:32422/TCP   2h
```

Of particular importance is the mapping to port `8888` (e.g.,`32422`). If you are performing this on the same host as where the notebook will run, then you will need to note the cluster-ip entry (e.g.,`10.110.253.2.3`).

(Note: if the number of replicas is > 1, then you will see two pods listed with different five-character suffixes.)

```{tip}
 You can avoid the need to point at a different port each time EG is launched by adding an `externalIPs:` entry to the `spec:` section of the `service.yaml` file.  This entry can be specifed in the `values.yaml` via the `service.externalIPs.k8sMasterPublicIP` entry.
```

The value of the `JUPYTER_GATEWAY_URL` used by the gateway-enabled Notebook server will vary depending on whether you choose to define an external IP or not. If and external IP is defined, you'll set `JUPYTER_GATEWAY_URL=<externalIP>:8888` else you'll set `JUPYTER_GATEWAY_URL=<k8s-master>:32422` **but also need to restart clients each time Enterprise Gateway is started.** As a result, use of the `externalIPs:` value is highly recommended.

## Kubernetes Tips

The following items illustrate some useful commands for navigating Enterprise Gateway within a kubernetes environment.

- All objects created on behalf of Enterprise Gateway can be located using the label `app=enterprise-gateway`. You'll probably see duplicated entries for the deployments(deploy) and replication sets (rs) - we didn't include the duplicates here.

```bash
kubectl get all -l app=enterprise-gateway --all-namespaces

NAME                        DESIRED   CURRENT   UP-TO-DATE   AVAILABLE   AGE
deploy/enterprise-gateway   1         1         1            1           3h

NAME                               DESIRED   CURRENT   READY     AGE
rs/enterprise-gateway-74c46cb7fc   1         1         1         3h

NAME                                             READY     STATUS    RESTARTS   AGE
pod/alice-5e755458-a114-4215-96b7-bcb016fc7b62   1/1       Running   0          8s
pod/enterprise-gateway-74c46cb7fc-jrkl7          1/1       Running   0          3h
```

- All objects related to a given kernel can be located using the label `kernel_id=<kernel_id>`

```bash
kubectl get all -l kernel_id=5e755458-a114-4215-96b7-bcb016fc7b62 --all-namespaces

NAME                                             READY     STATUS    RESTARTS   AGE
pod/alice-5e755458-a114-4215-96b7-bcb016fc7b62   1/1       Running   0          28s
```

Note: because kernels are, by default, isolated to their own namespace, you could also find all objects of a
given kernel using only the `--namespace <kernel-namespace>` clause.

- To enter into a given pod (i.e., container) in order to get a better idea of what might be happening within the container, use the exec command with the pod name

```bash
kubectl exec -it enterprise-gateway-74c46cb7fc-jrkl7 /bin/bash
```

- Logs can be accessed against the pods or deployment (requires the object type prefix (e.g., `pod/`))

```bash
kubectl logs -f pod/alice-5e755458-a114-4215-96b7-bcb016fc7b62
```

Note that if using multiple replicas, commands against each pod are required.

- The Kubernetes dashboard is useful as well. It's located at port `3.2.3` of the master node

```bash
https://elyra-kube1.foo.bar.com:3.2.3/dashboard/#!/overview?namespace=default
```

From there, logs can be accessed by selecting the `Pods` option in the left-hand pane followed by the _lined_ icon on
the far right.

- User "system:serviceaccount:default:default" cannot list pods in the namespace "default"

On a recent deployment, Enterprise Gateway was not able to create or list kernel pods. Found
the following command was necessary. (Kubernetes security relative to Enterprise Gateway is still under construction.)

```bash
kubectl create clusterrolebinding add-on-cluster-admin --clusterrole=cluster-admin  --serviceaccount=default:default
```
