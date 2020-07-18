## Kubernetes

This page describes the approach taken for integrating Enterprise Gateway into an existing Kubernetes cluster.

In this solution, Enterprise Gateway is, itself, provisioned as a Kubernetes _deployment_ and exposed as a Kubernetes _service_.  In this way, Enterprise Gateway can leverage load balancing and high availability functionality provided by Kubernetes (although HA cannot be fully realized until EG supports persistent sessions).

The following sample kernelspecs are currently available on Kubernetes:

+ R_kubernetes
+ python_kubernetes
+ python_tf_gpu_kubernetes
+ python_tf_kubernetes
+ scala_kubernetes
+ spark_R_kubernetes
+ spark_python_kubernetes
+ spark_scala_kubernetes

As with all kubernetes deployments, Enterprise Gateway is built into a docker image.  The base Enterprise Gateway image is [elyra/enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) and can be found in the Enterprise Gateway dockerhub organization [elyra](https://hub.docker.com/r/elyra/), along with other kubernetes-based images.  See [Runtime Images](docker.html#runtime-images) for image details.

When deployed within a [spark-on-kubernetes](https://spark.apache.org/docs/latest/running-on-kubernetes.html) cluster, Enterprise Gateway can easily support cluster-managed kernels distributed across the cluster. Enterprise Gateway will also provide standalone (i.e., _vanilla_) kernel invocation (where spark contexts are not automatically created) which also benefits from their distribution across the cluster.

### Enterprise Gateway Deployment
Enterprise Gateway manifests itself as a Kubernetes deployment, exposed externally by a Kubernetes service.  It is identified by the name `enterprise-gateway` within the cluster. In addition, all objects related to Enterprise Gateway, including kernel instances, have the kubernetes label of `app=enterprise-gateway` applied.

The service is currently configured as type `NodePort` but is intended for type `LoadBalancer` when appropriate network plugins are available.  Because kernels are stateful, the service is also configured with a `sessionAffinity` of `ClientIP`.  As a result, kernel creation requests will be routed to different deployment instances (see deployment) thereby diminishing the need for a `LoadBalancer` type. Here's the service yaml entry from [enterprise-gateway.yaml](https://github.com/jupyter/enterprise_gateway/blob/master/etc/kubernetes/enterprise-gateway.yaml):
```yaml
apiVersion: v1
kind: Service
metadata:
  labels:
    app: enterprise-gateway
  name: enterprise-gateway
  namespace: enterprise-gateway
spec:
  ports:
  - name: http
    port: 8888
    targetPort: 8888
  selector:
    gateway-selector: enterprise-gateway
  sessionAffinity: ClientIP
  type: NodePort
```
The deployment yaml essentially houses the pod description.  By increasing the number of `replicas` a configuration can experience instant benefits of distributing Enterprise Gateway instances across the cluster.  This implies that once session persistence is provided, we should be able to provide highly available (HA) kernels.  Here's the yaml portion from [enterprise-gateway.yaml](https://github.com/jupyter/enterprise_gateway/blob/master/etc/kubernetes/enterprise-gateway.yaml) that defines the Kubernetes deployment and pod (some items may have changed):
```yaml
apiVersion: apps/v1beta2
kind: Deployment
metadata:
  name: enterprise-gateway
  namespace: enterprise-gateway
  labels:
    gateway-selector: enterprise-gateway
    app: enterprise-gateway
    component: enterprise-gateway
spec:
# Uncomment/Update to deploy multiple replicas of EG
#  replicas: 1
  selector:
    matchLabels:
      gateway-selector: enterprise-gateway
  template:
    metadata:
      labels:
        gateway-selector: enterprise-gateway
        app: enterprise-gateway
        component: enterprise-gateway
    spec:
      # Created above.
      serviceAccountName: enterprise-gateway-sa
      containers:
      - env:
          # Created above.
        - name: EG_NAMESPACE
          value: "enterprise-gateway"

          # Created above.  Used if no KERNEL_NAMESPACE is provided by client.
        - name: EG_KERNEL_CLUSTER_ROLE
          value: "kernel-controller"

          # All kernels reside in the EG namespace if True, otherwise KERNEL_NAMESPACE
          # must be provided or one will be created for each kernel.
        - name: EG_SHARED_NAMESPACE
          value: "False"

        - name: EG_TUNNELING_ENABLED
          value: "False"
        - name: EG_CULL_IDLE_TIMEOUT
          value: "600"
        - name: EG_LOG_LEVEL
          value: "DEBUG"
        - name: EG_KERNEL_LAUNCH_TIMEOUT
          value: "60"
        - name: EG_KERNEL_WHITELIST
          value: "['r_kubernetes','python_kubernetes','python_tf_kubernetes','scala_kubernetes','spark_r_kubernetes','spark_python_kubernetes','spark_scala_kubernetes']"
        - name: EG_DEFAULT_KERNEL_NAME
          value: "python_kubernetes"

        # Ensure the following VERSION tag is updated to the version of Enterprise Gateway you wish to run
        image: elyra/enterprise-gateway:VERSION
        # k8s will only pull :latest all the time.  
        # the following line will make sure that :VERSION is always pulled
        # You should remove this if you want to pin EG to a release tag
        imagePullPolicy: Always
        name: enterprise-gateway
        args: ["--gateway"]
        ports:
        - containerPort: 8888
```
#### Namespaces
A best practice for Kubernetes applications running in an enterprise is to isolate applications via namespaces.  Since Enterprise Gateway also requires isolation at the kernel level, it makes sense to use a namespace for each kernel, by default.

The initial namespace is created in the `enterprise-gateway.yaml` file using a default name of `enterprise-gateway`.  This name is communicated to the EG application via the env variable `EG_NAMESPACE`.  All Enterprise Gateway components reside in this namespace.

```yaml
apiVersion: apps/v1beta2
kind: Deployment
metadata:
  name: enterprise-gateway
  namespace: enterprise-gateway

```

By default, kernel namespaces are created when the respective kernel is launched.  At that time, the kernel namespace name is computed from the kernel username (`KERNEL_USERNAME`) and its Id (`KERNEL_ID`) just like the kernel pod name.  Upon a kernel's termination, this namespace - provided it was created by Enterprise Gateway - will be deleted.

Installations wishing to pre-create the kernel namespace can do so by conveying the name of the kernel namespace via `KERNEL_NAMESPACE` in the `env` portion of the kernel creation request.  (They must also provide the namespace's service account name via `KERNEL_SERVICE_ACCOUNT_NAME` - see next section.)  When `KERNEL_NAMESPACE` is set, Enterprise Gateway will not attempt to create a kernel-specific namespace, nor will it attempt its deletion.  As a result, kernel namespace lifecycle management is the user's responsibility.

Although **not recommended**, installations requiring everything in the same namespace - Enterprise Gateway and all its kernels - can do so by setting env `EG_SHARED_NAMESPACE` to `True`. When set, all kernels will run in the enterprise gateway namespace, essentially eliminating all aspects of isolation between kernel instances.

#### Role-Based Access Control (RBAC)
Another best practice of Kubernetes applications is to define the minimally viable set of permissions for the application.  Enterprise Gateway does this by defining role-based access control (RBAC) objects for both Enterprise Gateway and kernels.

Because the Enterprise Gateway pod must create kernel namespaces, pods, services (for Spark support) and rolebindings, a cluster-scoped role binding is required.  The cluster role binding `enterprise-gateway-controller` also references the subject, `enterprise-gateway-sa`, which is the service account associated with the Enterprise Gateway namespace and also created by the yaml file.
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: enterprise-gateway-sa
  namespace: enterprise-gateway
  labels:
    app: enterprise-gateway
    component: enterprise-gateway
---
apiVersion: rbac.authorization.k8s.io/v1beta1
kind: ClusterRole
metadata:
  name: enterprise-gateway-controller
  labels:
    app: enterprise-gateway
    component: enterprise-gateway
rules:
  - apiGroups: [""]
    resources: ["pods", "namespaces", "services", "configmaps", "secrets", "persistentvolumnes", "persistentvolumeclaims"]
    verbs: ["get", "watch", "list", "create", "delete"]
  - apiGroups: ["rbac.authorization.k8s.io"]
    resources: ["rolebindings"]
    verbs: ["get", "list", "create", "delete"]
---
apiVersion: rbac.authorization.k8s.io/v1beta1
kind: ClusterRoleBinding
metadata:
  name: enterprise-gateway-controller
  labels:
    app: enterprise-gateway
    component: enterprise-gateway
subjects:
  - kind: ServiceAccount
    name: enterprise-gateway-sa
    namespace: enterprise-gateway
roleRef:
  kind: ClusterRole
  name: enterprise-gateway-controller
  apiGroup: rbac.authorization.k8s.io
```

The `enterprise-gateway.yaml` file also defines the minimally viable roles for a kernel pod - most of which are required for Spark support.  Since kernels, by default, reside within their own namespace created upon their launch, a cluster role is used within a namespace-scoped role binding created when the kernel's namespace is created. The name of the kernel cluster role is `kernel-controller` and, when Enterprise Gateway creates the namespace and role binding, is also the name of the role binding instance.

```yaml
apiVersion: rbac.authorization.k8s.io/v1beta1
kind: ClusterRole
metadata:
  name: kernel-controller
  labels:
    app: enterprise-gateway
    component: kernel
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "watch", "list", "create", "delete"]
```

As noted above, installations wishing to pre-create their own kernel namespaces should provide the name of the service account associated with the namespace via `KERNEL_SERVICE_ACCOUNT_NAME` in the `env` portion of the kernel creation request (along with `KERNEL_NAMESPACE`).  If not provided, the built-in namespace service account, `default`, will be referenced.  In such circumstances, Enterprise Gateway will **not** create a role binding on the name for the service account, so it is the user's responsibility to ensure that the service account has the capability to perform equivalent operations as defined by the `kernel-controller` role.

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
apiVersion: rbac.authorization.k8s.io/v1beta1
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
#### Kernel Image Puller
Because kernels now reside within containers and its typical for the first reference of a container to trigger its pull from a docker repository, kernel startup requests can easily timeout whenever the kernel image is first accessed on any given node.  To mitigate this issue, Enterprise Gateway deployment includes a DaemonSet object named `kernel-image-puller` or KIP.  This object is responsible for polling Enterprise Gateway for the current set of configured kernelspecs, picking out any configured image name references, and pulling those images to the node on which KIP is running.  Because its a daemon set, this will also address the case when new nodes are added to a configuration.

The Kernel Image Puller can be configured for the interval at which it checks for new kernelspecs (`KIP_INTERVAL`), the number of puller threads it will utilize per node (`KIP_NUM_PULLERS`), the number of retries it will attempt for a given image (`KIP_NUM_RETRIES`), and the pull policy (`KIP_PULL_POLICY`) - which essentially dictates whether it will attempt to pull images that its already encoutnered (`Always`) vs. only pulling the image if it hasn't seen it yet (`IfNotPresent`).

Here's what the Kernel Image Puller looks like in the yaml...
```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: kernel-image-puller
  namespace: enterprise-gateway
spec:
  selector:
    matchLabels:
      name: kernel-image-puller
  template:
    metadata:
      labels:
        name: kernel-image-puller
        app: enterprise-gateway
        component: kernel-image-puller
    spec:
      containers:
      - name: kernel-image-puller
        image: elyra/kernel-image-puller:VERSION
        env:
          - name: KIP_GATEWAY_HOST
            value: "http://enterprise-gateway.enterprise-gateway:8888"
          - name: KIP_INTERVAL
            value: "300"
          - name: KIP_PULL_POLICY
            value: "IfNotPresent"
        volumeMounts:
          - name: dockersock
            mountPath: "/var/run/docker.sock"
      volumes:
      - name: dockersock
        hostPath:
          path: /var/run/docker.sock
```


#### Kernelspec Modifications

One of the more common areas of customization we see occurs within the kernelspec files located in `/usr/local/share/jupyter/kernels`.  To accommodate the ability to customize the kernel definitions, you have two different options: NFS mounts, or custom container images.  The two options are mutually exclusive, because they mount kernelspecs into the same location in the Enterprise Gateway pod.

##### Via NFS

The kernels directory can be mounted as an NFS volume into the Enterprise Gateway pod, thereby making the kernelspecs available to all EG pods within the Kubernetes cluster (provided the NFS mounts exist on all applicable nodes).

As an example, we have included the necessary entries for mounting an existing NFS mount point into the Enterprise Gateway pod.  By default, these references are commented out as they require the system administrator configure the appropriate NFS mounts and server IP.  If you are deploying Enterprise Gateway via the Helm chart (see Deploying Enterprise Gateway, below), you can enable NFS directly via Helm values.

Here you can see how `enterprise-gateway.yaml` references use of the volume (via `volumeMounts`
for the container specification and `volumes` in the pod specification):
```yaml
    spec:
      containers:
      - env:
        - name: EG_NAMESPACE
          value: "enterprise-gateway"
        - name: EG_KERNEL_CLUSTER_ROLE
          value: "kernel-controller"
        - name: EG_SHARED_NAMESPACE
          value: "False"
        - name: EG_TUNNELING_ENABLED
          value: "False"
        - name: EG_CULL_IDLE_TIMEOUT
          value: "600"
        - name: EG_LOG_LEVEL
          value: "DEBUG"
        - name: EG_KERNEL_LAUNCH_TIMEOUT
          value: "60"
        - name: EG_KERNEL_WHITELIST
          value: "['r_kubernetes','python_kubernetes','python_tf_kubernetes','python_tf_gpu_kubernetes','scala_kubernetes','spark_r_kubernetes','spark_python_kubernetes','spark_scala_kubernetes']"
        image: elyra/enterprise-gateway:VERSION
        name: enterprise-gateway
        args: ["--gateway"]
        ports:
        - containerPort: 8888
# Uncomment to enable NFS-mounted kernelspecs
        volumeMounts:
        - name: kernelspecs
          mountPath: "/usr/local/share/jupyter/kernels"
      volumes:
      - name: kernelspecs
        nfs:
          server: <internal-ip-of-nfs-server>
          path: "/usr/local/share/jupyter/kernels"

```
Note that because the kernel pod definition file, [kernel-pod.yaml](https://github.com/jupyter/enterprise_gateway/blob/master/etc/kernel-launchers/kubernetes/scripts/kernel-pod.yaml), resides in the kernelspecs hierarchy, customizations to the deployments of future kernel instances can now also take place.  In addition, these same entries can be added to the kernel-pod.yaml definitions if access to the same or other NFS mount points are desired within kernel pods. (We'll be looking at ways to make modifications to per-kernel configurations more manageable.)

Use of more formal persistent volume types must include the [Persistent Volume](https://kubernetes.io/docs/concepts/storage/persistent-volumes) and corresponding Persistent Volume Claim stanzas.

##### Via Custom Container Image

If you are deploying Enterprise Gateway via the Helm chart (see Deploying Enterprise Gateway, below), then instead of using NFS, you can build your custom kernelspecs into a container image that Enterprise Gateway consumes.  Here's an example Dockerfile for such a container:

```
FROM alpine:3.9

COPY kernels /kernels
```

This assumes that your source contains a `kernels/` directory with all of the kernelspecs you'd like to end up in the image, e.g. `kernels/python_kubernetes/kernel.json` and any associated files.

Once you build your custom kernelspecs image and push it to a container registry, you can refer to it from your Helm deployment.  For instance:

```bash
helm upgrade --install --atomic --namespace enterprise-gateway enterprise-gateway etc/kubernetes/helm --set kernelspecs.image=your-custom-image:latest
```

...where `your-custom-image:latest` is the image name and tag of your kernelspecs image.  Once deployed, the Helm chart copies the data from the `/kernels` directory of your container into the `/usr/local/share/jupyter/kernels` directory of the Enterprise Gateway pod.  Note that when this happens, the built-in kernelspecs are no longer available. So include all kernelspecs that you want to be available in your container image.

Also, you should update the Helm chart `kernel_whitelist` value with the name(s) of your custom kernelspecs.

### Kubernetes Kernel Instances
There are essentially two kinds of kernels (independent of language) launched within an Enterprise Gateway Kubernetes cluster - _vanilla_ and _spark-on-kubernetes_ (if available).

When _vanilla_ kernels are launched, Enterprise Gateway is responsible for creating the corresponding pod. On the other hand, _spark-on-kubernetes_ kernels are launched via `spark-submit` with a specific `master` URI - which then creates the corresponding pod(s) (including executor pods).  Images can be launched using both forms provided they have the appropriate support for Spark installed.

Here's the yaml configuration used when _vanilla_ kernels are launched. As noted in the `KubernetesProcessProxy` section below, this file ([kernel-pod.yaml](https://github.com/jupyter/enterprise_gateway/blob/master/etc/kernel-launchers/kubernetes/scripts/kernel-pod.yaml)) serves as a template where each of the tags surrounded with `${}` represent variables that are substituted at the time of the kernel's launch.  All `${kernel_xxx}` parameters correspond to `KERNEL_XXX` environment variables that can be specified from the client in the kernel creation request's json body.
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: ${kernel_username}-${kernel_id}
  namespace: ${kernel_namespace}
  labels:
    kernel_id: ${kernel_id}
    app: enterprise-gateway
    component: kernel
spec:
  restartPolicy: Never
  serviceAccountName: ${kernel_service_account_name}
  securityContext:
    runAsUser: ${kernel_uid}
    runAsGroup: ${kernel_gid}
  containers:
  - env:
    - name: EG_RESPONSE_ADDRESS
      value: ${eg_response_address}
    - name: KERNEL_LANGUAGE
      value: ${kernel_language}
    - name: KERNEL_SPARK_CONTEXT_INIT_MODE
      value: ${kernel_spark_context_init_mode}
    - name: KERNEL_NAME
      value: ${kernel_name}
    - name: KERNEL_USERNAME
      value: ${kernel_username}
    - name: KERNEL_ID
      value: ${kernel_id}
    - name: KERNEL_NAMESPACE
      value: ${kernel_namespace}
    image: ${kernel_image}
    name: ${kernel_username}-${kernel_id}
```
There are a number of items worth noting:
1. Kernel pods can be identified in three ways using `kubectl`:
    1. By the global label `app=enterprise-gateway` - useful when needing to identify all related objects (e.g., `kubectl get all -l app=enterprise-gateway`)
    1. By the *kernel_id* label `kernel_id=<kernel_id>` - useful when only needing specifics about a given kernel.  This label is used internally by enterprise-gateway when performing its discovery and lifecycle management operations.
    1. By the *component* label `component=kernel` - useful when needing to identity only kernels and not other enterprise-gateway components.  (Note, the latter can be isolated via `component=enterprise-gateway`.)

    Note that since kernels run in isolated namespaces by default, it's often helpful to include the clause `--all-namespaces` on commands that will span namespaces.  To isolate commands to a given namespace, you'll need to add the namespace clause `--namespace <namespace-name>`.
1. Each kernel pod is named by the invoking user (via the `KERNEL_USERNAME` env) and its kernel_id (env `KERNEL_ID`).  This identifier also applies to those kernels launched within `spark-on-kubernetes`.
1. Kernel pods use the specified `securityContext`.  If env `KERNEL_UID` is not specified in the kernel creation request a default value of `1000` (the jovyan user) will be used.  Similarly for `KERNEL_GID`, whose default is `100` (the users group).  In addition, Enterprise Gateway enforces a blacklist for each of the UID and GID values.  By default, this list is initialized to the 0 (root) UID and GID.  Administrators can configure the `EG_UID_BLACKLIST` and `EG_GID_BLACKLIST` environment variables via the enterprise-gateway.yaml file with comma-separated values to alter the set of user and group ids to be prevented.
1. As noted above, if `KERNEL_NAMESPACE` is not provided in the request, Enterprise Gateway will create a namespace using the same naming algorithm for the pod.  In addition, the `kernel-controller` cluster role will be bound to a namespace-scoped role binding of the same name using the namespace's default service account as its subject.  Users wishing to use their own kernel namespaces must provide **both** `KERNEL_NAMESPACE` and `KERNEL_SERVICE_ACCOUNT_NAME` as these are both used in the `kernel-pod.yaml` as `${kernel_namespace}` and `${kernel_service_account_name}`, respectively.
1. Kernel pods have restart policies of `Never`.  This is because the Jupyter framework already has built-in logic for auto-restarting failed kernels and any other restart policy would likely interfere with the built-in behaviors.
1. The parameters to the launcher that is built into the image are communicated via environment variables as noted in the `env:` section above.

### Unconditional Volume Mounts
Unconditional volume mounts can be added in the `kernel-pod.yaml.j2` template. An example of these unconditional volume mounts can be found when extending docker shared memory. For some I/O jobs the pod will need more than the default `64mb` of shared memory on the `/dev/shm` path.

```
volumeMounts:
# Define any "unconditional" mounts here, followed by "conditional" mounts that vary per client
{% if kernel_volume_mounts is defined %}
  {% for volume_mount in kernel_volume_mounts %}
- {{ volume_mount }}
  {% endfor %}
{% endif %}
volumes:
# Define any "unconditional" volumes here, followed by "conditional" volumes that vary per client
{% if kernel_volumes is defined %}
{% for volume in kernel_volumes %}
- {{ volume }}
{% endfor %}
{% endif %}
```  

The conditional volumes are handled by the loops inside of the yaml file. Any unconditional volumes can be added before these conditions. In the scenario where the `/dev/shm` will need to be expanded the following mount has to be added.

```
volumeMounts:
# Define any "unconditional" mounts here, followed by "conditional" mounts that vary per client
- mountPath: /dev/shm
  name: dshm
{% if kernel_volume_mounts is defined %}
  {% for volume_mount in kernel_volume_mounts %}
- {{ volume_mount }}
  {% endfor %}
{% endif %}
volumes:
# Define any "unconditional" volumes here, followed by "conditional" volumes that vary per client
- name: dshm
emptyDir:
  medium: Memory
{% if kernel_volumes is defined %}
{% for volume in kernel_volumes %}
- {{ volume }}
{% endfor %}
{% endif %}
```

### KubernetesProcessProxy
To indicate that a given kernel should be launched into a Kubernetes configuration, the kernel.json file's `metadata` stanza must include a `process_proxy` stanza indicating a `class_name:` of `KubernetesProcessProxy`. This ensures the appropriate lifecycle management will take place relative to a Kubernetes environment.

Along with the `class_name:` entry, this process proxy stanza should also include a proxy configuration stanza  which specifies the docker image to associate with the kernel's pod.  If this entry is not provided, the Enterprise Gateway implementation will use a default entry of `elyra/kernel-py:VERSION`.  In either case, this value is made available to the rest of the parameters used to launch the kernel by way of an environment variable: `KERNEL_IMAGE`.

_(Please note that the use of `VERSION` in docker image tags is a placeholder for the appropriate version-related image tag.  When kernelspecs are built via the Enterprise Gateway Makefile, `VERSION` is replaced with the appropriate version denoting the target release.  A full list of available image tags can be found in the dockerhub repository corresponding to each image.)_
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
As always, kernels are launched by virtue of the `argv:` stanza in their respective kernel.json files.  However, when launching _vanilla_ kernels in a kubernetes environment, what gets invoked isn't the kernel's launcher, but, instead, a python script that is responsible for using the [Kubernetes Python API](https://github.com/kubernetes-client/python) to create the corresponding pod instance.  The pod is _configured_ by applying the values to each of the substitution parameters into the [kernel-pod.yaml](https://github.com/jupyter/enterprise_gateway/blob/master/etc/kernel-launchers/kubernetes/scripts/kernel-pod.yaml) file previously displayed. This file resides in the same `scripts` directory as the kubernetes launch script - `launch_kubernetes.py` - which is referenced by the kernel.json's `argv:` stanza:
```json
{
  "argv": [
    "python",
    "/usr/local/share/jupyter/kernels/python_kubernetes/scripts/launch_kubernetes.py",
     "--RemoteProcessProxy.kernel-id",
    "{kernel_id}",
    "--RemoteProcessProxy.response-address",
    "{response_address}",
    "--RemoteProcessProxy.spark-context-initialization-mode",
    "none"
  ]
}
```
By default, _vanilla_ kernels use a value of `none` for the spark context initialization mode so no context will be created automatically.

When the kernel is intended to target _Spark-on-kubernetes_, its launch is very much like kernels launched in YARN _cluster mode_, albeit with a completely different set of parameters.  Here's an example `SPARK_OPTS` string value which best conveys the idea:
```
  "SPARK_OPTS": "--master k8s://https://${KUBERNETES_SERVICE_HOST}:${KUBERNETES_SERVICE_PORT} --deploy-mode cluster --name ${KERNEL_USERNAME}-${KERNEL_ID} --conf spark.kubernetes.driver.label.app=enterprise-gateway --conf spark.kubernetes.driver.label.kernel_id=${KERNEL_ID} --conf spark.kubernetes.executor.label.app=enterprise-gateway --conf spark.kubernetes.executor.label.kernel_id=${KERNEL_ID} --conf spark.kubernetes.driver.docker.image=${KERNEL_IMAGE} --conf spark.kubernetes.executor.docker.image=kubespark/spark-executor-py:v2.2.0-kubernetes-0.5.0 --conf spark.kubernetes.submission.waitAppCompletion=false",
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
    "--RemoteProcessProxy.spark-context-initialization-mode",
    "lazy"
  ]
}
```

### Deploying Enterprise Gateway on Kubernetes
Once the Kubernetes cluster is configured and `kubectl` is demonstrated to be working on the master node, it is time to deploy Enterprise Gateway. There a couple of different deployment options - kubectl or helm.

#### Option 1: Deploying with kubectl

Choose this deployment option if you want to deploy directly from Kubernetes template files with kubectl, rather than using a package manager like Helm.

##### Create the Enterprise Gateway kubernetes service and deployment
From the master node, create the service and deployment using the yaml file from a source release or the git repository:

```
kubectl apply -f etc/kubernetes/enterprise-gateway.yaml

service "enterprise-gateway" created
deployment "enterprise-gateway" created
```

##### Uninstalling Enterprise Gateway

To shutdown Enterprise Gateway issue a delete command using the previously mentioned global label `app=enterprise-gateway`
```
kubectl delete all -l app=enterprise-gateway
```
or simply delete the namespace
```
kubectl delete ns enterprise-gateway
```

A kernel's objects can be similarly deleted using the kernel's namespace...
```
kubectl delete ns <kernel-namespace>
```
Note that this should not imply that kernels be "shutdown" using a the `kernel_id=` label.  This will likely trigger Jupyter's auto-restart logic - so its best to properly shutdown kernels prior to kubernetes object deletions.

Also note that deleting the Enterprise Gateway namespace will not delete cluster-scoped resources like the cluster roles `enterprise-gateway-controller` and `kernel-controller` or the cluster role binding `enterprise-gateway-controller`. The following commands can be used to delete these:
```
kubectl delete clusterrole -l app=enterprise-gateway
kubectl delete clusterrolebinding -l app=enterprise-gateway
```

#### Option 2: Deploying with Helm

Choose this option if you want to deploy via a [Helm](https://helm.sh/) chart.
If Ingress is desired see [this section](#setting-up-a-kubernetes-ingress-for-use-with-enterprise-gateway) before deploying
with helm.

##### Create the Enterprise Gateway kubernetes service and deployment

From anywhere with Helm cluster access, create the service and deployment by running Helm from a source release or the git repository:

```bash
helm upgrade --install --atomic --namespace enterprise-gateway enterprise-gateway etc/kubernetes/helm/enterprise-gateway
```
the helm chart tarball is also accessible as an asset on our [release](https://github.com/jupyter/enterprise_gateway/releases/tag/v2.2.0rc2) page:
```bash
helm install --name enterprise-gateway --atomic --namespace enterprise-gateway https://github.com/jupyter/enterprise_gateway/releases/download/v2.2.0rc2/jupyter_enterprise_gateway_helm-2.2.0rc2.tgz
```
##### Configuration

Here are all of the values that you can set when deploying the Helm chart. You
can override them with Helm's `--set` or `--values` options.

| **Parameter** | **Description** | **Default** |
| ------------- | --------------- | ----------- |
| `image` | Enterprise Gateway image name and tag to use. Ensure the tag is updated to the version of Enterprise Gateway you wish to run. | `elyra/enterprise-gateway:VERSION`, where `VERSION` is the release being used |
| `imagePullPolicy` | Enterprise Gateway image pull policy. Use `IfNotPresent` policy so that dev-based systems don't automatically update. This provides more control.  Since formal tags will be release-specific this policy should be sufficient for them as well. | `IfNotPresent` |
| `port` | The primary port on which Enterprise Gateway is servicing requests. | `8888` |
| `replicas` | Update to deploy multiple replicas of EG. | `1` |
| `logLevel` | Log output level. | `DEBUG` |
| `mirrorWorkingDirs` | Whether to mirror working directories. NOTE: This requires appropriate volume mounts to make notebook dir accessible. | `false` |
| `k8sMasterPublicIP` | Master public IP on which to expose EG. | `nil` |
| `kernel.clusterRole` | Kernel cluster role created by this chart. Used if no KERNEL_NAMESPACE is provided by client. | `kernel-controller` |
| `kernel.sharedNamespace` | All kernels reside in the EG namespace if true, otherwise KERNEL_NAMESPACE must be provided or one will be created for each kernel. | `false` |
| `kernel.cullIdleTimeout` | Idle timeout in seconds. Default is 1 hour. | `3600` |
| `kernel.launchTimeout` | Timeout for kernel launching in seconds. | `60` |
| `kernel.whitelist` | List of kernel names that are available for use. | `{r_kubernetes,...}` (see `values.yaml`) |
| `kernelspecs.image` | Optional custom data image containing kernelspecs to use. Cannot be used with NFS enabled. | `nil` |
| `kernelspecs.imagePullPolicy` | Kernelspecs image pull policy. | `Always` |
| `nfs.enabled` | Whether NFS-mounted kernelspecs are enabled. Cannot be used with `kernelspecs.image` set. | `false` |
| `nfs.internalServerIPAddress` | IP address of NFS server. Required if NFS is enabled. | `nil` |
| `ingress.enabled` | Whether to include an EG ingress resource during deployment.| `false` |
| `ingress.traefik.enabled` | Configure the ingress using Traefik as the controller. NOTE: A traefik controller must be installed and `ingress.enabled` must be `true`. | `true` |
| `ingress.traefik.annotations` | Traefik-relative ingress annotations to be included when `ingress.traefik.enabled` is `true`. | `(traefik-ingress annotations)` |
| `ingress.traefik.path` | URL context to be used in addition to the hostname to access Enterprise Gateway when `ingress.traefik.enabled` is `true`. | `/gateway` |
| `ingress.nginx.enabled` | Configure the ingress using Nginx as the controller. NOTE: A nginx controller must be installed and `ingress.enabled` must be `true`. | `false` |
| `ingress.nginx.annotations` | Nginx-relative ingress annotations to be included when `ingress.nginx.enabled` is `true`. | `(nginx-ingress annotations)` |
| `ingress.nginx.path` | URL context to be used in addition to the hostname to access Enterprise Gateway when `ingress.nginx.enabled` is `true`. | `/gateway/?(.*)` |
| `ingress.hostName` | Ingress resource host  | `nil` |
| `ingress.port` | The port where enterprise gateway service is running | `8888` |
| `kip.image` | Kernel Image Puller image name and tag to use. Ensure the tag is updated to the version of the Enterprise Gateway release you wish to run. | `elyra/kernel-image-puller:VERSION`, where `VERSION` is the release being used |
| `kip.imagePullPolicy` | Kernel Image Puller image pull policy. Use `IfNotPresent` policy so that dev-based systems don't automatically update. This provides more control.  Since formal tags will be release-specific this policy should be sufficient for them as well. | `IfNotPresent` |
| `kip.interval` | The interval (in seconds) at which the Kernel Image Puller fetches kernelspecs to pull kernel images. | `300` |
| `kip.pullPolicy` | Determines whether the Kernel Image Puller will pull kernel images it has previously pulled (`Always`) or only those it hasn't yet pulled (`IfNotPresent`) | `IfNotPresent` |


##### Uninstalling Enterprise Gateway

When using Helm, you can uninstall Enterprise Gateway with the following command:

```
helm delete --purge enterprise-gateway
```

#### Confirm deployment and note the service port mapping
```
kubectl get all --all-namespaces -l app=enterprise-gateway

NAME                        DESIRED   CURRENT   UP-TO-DATE   AVAILABLE   AGE
deploy/enterprise-gateway   1         1         1            1           2h

NAME                               DESIRED   CURRENT   READY     AGE
rs/enterprise-gateway-74c46cb7fc   1         1         1         2h

NAME                                     READY     STATUS    RESTARTS   AGE
po/enterprise-gateway-74c46cb7fc-jrkl7   1/1       Running   0          2h

NAME                     TYPE       CLUSTER-IP       EXTERNAL-IP   PORT(S)          AGE
svc/enterprise-gateway   NodePort   10.110.253.220   <none>        8888:32422/TCP   2h
```
Of particular importance is the mapping to port `8888` (e.g.,`32422`).  If you are performing this on the same host as where the notebook will run, then you will need to note the cluster-ip entry (e.g.,`10.110.253.220`).

(Note: if the number of replicas is > 1, then you will see two pods listed with different five-character suffixes.)

**Tip:** You can avoid the need to point at a different port each time EG is launched by adding an `externalIPs:` entry to the `spec:` section of the `enterprise-gateway.yaml` file.  The file is delivered with this entry commented out.  Of course, you'll need to change the IP address to that of your kubernetes master node once the comments characters have been removed.
```text
# Uncomment in order to use <k8s-master>:8888
#  externalIPs:
#  - 9.30.118.200
```

However, if using Helm, see the section above about how to set the `k8sMasterPublicIP`.

The value of the `KG_URL` used by `NB2KG` will vary depending on whether you choose to define an external IP or not.  If and external IP is defined, you'll set `KG_URL=<externalIP>:8888` else you'll set `KG_URL=<k8s-master>:32422` **but also need to restart clients each time Enterprise Gateway is started.**  As a result, use of the `externalIPs:` value is highly recommended.

### Setting up a Kubernetes Ingress for use with Enterprise Gateway

To setup an ingress with Enterprise Gateway, you'll need an ingress controller deployed on your kubernetes cluster. We
recommend either NGINX or Traefik. Installation and configuration instructions can be found at the following :

- [NGINX-Ingress-Controller](https://kubernetes.github.io/ingress-nginx)
- [Traefik](https://docs.traefik.io/user-guide/kubernetes/)

Example - Here the NGINX Ingress Controller is deployed as a `LoadBalancer` with `NodePort` 32121 and 30884 open for http and https traffic respectively.

```bash
$ kubectl get services --all-namespaces
NAMESPACE            NAME                                             TYPE           CLUSTER-IP       EXTERNAL-IP   PORT(S)                      AGE
default              service/kubernetes                               ClusterIP      10.96.0.1        <none>        443/TCP                      23h
default              service/my-nginx-nginx-ingress-controller        LoadBalancer   10.105.234.155   <pending>     80:32121/TCP,443:30884/TCP   22h
default              service/my-nginx-nginx-ingress-default-backend   ClusterIP      10.107.13.85     <none>        80/TCP                       22h
enterprise-gateway   service/enterprise-gateway                       NodePort       10.97.127.52     <none>        8888:30767/TCP               27m
kube-system          service/kube-dns                                 ClusterIP      10.96.0.10       <none>        53/UDP,53/TCP,9153/TCP       23h
kube-system          service/tiller-deploy                            ClusterIP      10.101.96.215    <none>        44134/TCP                    23h
```

Once you have a Ingress controller installed, you can use the `Ingress` resource in kubernetes to direct traffic to your
Enterprise Gateway service. The EG helm chart is configured with an ingress template, which
can be found at [here](https://github.com/jupyter/enterprise_gateway/tree/master/etc/kubernetes/helm/templates/ingress.yaml)
for Enterprise Gateway.

Example - Enable ingress and edit etc/kubernetes/helm/values.yaml to the desired configurations and install EG as normal via Helm.
```bash
ingress:
  enabled: true             # Ingress is disabled by default
  annotations:              # Annotations to be used, changes depend on which ingress controller you have deployed # default is nginx
    kubernetes.io/ingress.class: "nginx"
    nginx.ingress.kubernetes.io/rewrite-target: /$1
    nginx.ingress.kubernetes.io/ssl-redirect: "false"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "false"
  hostName: ""              # whether to expose by setting a host-based ingress rule, default is *
  path: /gateway/?(.*)      # URL context used to expose EG
```

A quick look at our ingress resource after deploying EG with Helm :
```bash
$ kubectl describe ingress enterprise-gateway-ingress -n enterprise-gateway
Name:             enterprise-gateway-ingress
Namespace:        enterprise-gateway
Address:
Default backend:  default-http-backend:80 (<none>)
Rules:
  Host  Path  Backends
  ----  ----  --------
  *
        /gateway/?(.*)   enterprise-gateway:8888 (<none>)
Annotations:
  kubectl.kubernetes.io/last-applied-configuration:  {"apiVersion":"extensions/v1beta1","kind":"Ingress","metadata":  
  {"annotations":{"kubernetes.io/ingress.class":"nginx","nginx.ingress.kubernetes.io/force-ssl-redirect":"false",  
  "nginx.ingress.kubernetes.io/rewrite-target":"/$1","nginx.ingress.kubernetes.io/ssl-redirect":"false"},  
  "name":"enterprise-gateway-ingress","namespace":"enterprise-gateway"},"spec":{"rules":[{"http":{"paths":[{  
  "backend":{"serviceName":"enterprise-gateway","servicePort":8888},"path":"/gateway/?(.*)"}]}}]}}

  kubernetes.io/ingress.class:                     nginx
  nginx.ingress.kubernetes.io/force-ssl-redirect:  false
  nginx.ingress.kubernetes.io/rewrite-target:      /$1
  nginx.ingress.kubernetes.io/ssl-redirect:        false
Events:                                            <none>
```

This will expose the Enterprise Gateway service at
```bash
http://KUBERNETES_HOSTNAME:PORT/gateway
```   
where `PORT` is the ingress controller's http `NodePort` we referenced earlier.     
**NOTE:** `PORT` may be optional depending on how your environment/infrastructure is configured.  


### Kubernetes Tips
The following items illustrate some useful commands for navigating Enterprise Gateway within a kubernetes environment.

- All objects created on behalf of Enterprise Gateway can be located using the label `app=enterprise-gateway`.  You'll probably see duplicated entries for the deployments(deploy) and replication sets (rs) - I didn't include the duplicates here.
```
kubectl get all -l app=enterprise-gateway --all-namespaces

NAME                        DESIRED   CURRENT   UP-TO-DATE   AVAILABLE   AGE
deploy/enterprise-gateway   1         1         1            1           3h

NAME                               DESIRED   CURRENT   READY     AGE
rs/enterprise-gateway-74c46cb7fc   1         1         1         3h

NAME                                            READY     STATUS    RESTARTS   AGE
po/alice-5e755458-a114-4215-96b7-bcb016fc7b62   1/1       Running   0          8s
po/enterprise-gateway-74c46cb7fc-jrkl7          1/1       Running   0          3h

```
- All objects related to a given kernel can be located using the label `kernel_id=<kernel_id>`
```
kubectl get all -l kernel_id=5e755458-a114-4215-96b7-bcb016fc7b62 --all-namespaces

NAME                                            READY     STATUS    RESTARTS   AGE
po/alice-5e755458-a114-4215-96b7-bcb016fc7b62   1/1       Running   0          28s
```
Note: because kernels are, by default, isolated to their own namespace, you could also find all objects of a
given kernel using only the `--namespace <kernel-namespace>` clause.

- To enter into a given pod (i.e., container) in order to get a better idea of what might be happening within the container, use the exec command with the pod name
```
kubectl exec -it enterprise-gateway-74c46cb7fc-jrkl7 /bin/bash
```

- Logs can be accessed against the pods or deployment (requires the object type prefix (e.g., `po/`))
```
kubectl logs -f po/alice-5e755458-a114-4215-96b7-bcb016fc7b62
```
Note that if using multiple replicas, commands against each pod are required.

- The Kubernetes dashboard is useful as well.  Its located at port `30000` of the master node
```
https://elyra-kube1.foo.bar.com:30000/dashboard/#!/overview?namespace=default
```
From there, logs can be accessed by selecting the `Pods` option in the left-hand pane followed by the _lined_ icon on
the far right.

- User \"system:serviceaccount:default:default\" cannot list pods in the namespace \"default\"

On a recent deployment, Enterprise Gateway was not able to create or list kernel pods.  Found
the following command was necessary.  (Kubernetes security relative to Enterprise Gateway is still under construction.)
```bash
kubectl create clusterrolebinding add-on-cluster-admin --clusterrole=cluster-admin  --serviceaccount=default:default
```
