## Enabling Kubernetes Support
This page describes the approach taken for integrating Enterprise Gateway into an existing
Kubernetes cluster.

In this solution, Enterprise Gateway is, itself, provisioned as a Kubernetes _deployment_ 
and exposed as a Kubernetes _service_.  In this way, Enterprise Gateway can leverage load 
balancing and high availability functionality provided by Kubernetes (although HA cannot be
fully realized until EG supports persistent sessions).

As with all kubernetes deployments, Enterprise Gateway is built into a docker image.  The
base Enterprise Gateway image is [elyra/enterprise-gateway](https://hub.docker.com/r/elyra/enterprise-gateway/) 
and can be found in the Enterprise Gateway dockerhub organization [elyra](https://hub.docker.com/r/elyra/), along with
other kubernetes-based images.  See [Kubernetes Images](docker.html#kubernetes-images) for image details.

When deployed within a [spark-on-kubernetes](https://github.com/apache-spark-on-k8s/spark) 
cluster, Enterprise Gateway can easily support cluster-managed kernels distributed across 
the cluster. Enterprise Gateway will also provide standalone (i.e., _vanilla_) kernel 
invocation (where spark contexts are not automatically created) which also benefits from 
their distribution across the cluster.

### Enterprise Gateway Deployment
Enterprise Gateway manifests itself as a Kubernetes deployment, exposed externally by a 
Kubernetes service.  It is identified by the name `enterprise-gateway` within the cluster. 
In addition, all objects related to Enterprise Gateway, including kernel instances, have 
the kubernetes label of `app=enterprise-gateway` applied.

The service is currently configured as type `NodePort` but is intended for type 
`LoadBalancer` when appropriate network plugins are available.  Because kernels
are stateful, the service is also configured with a `sessionAffinity` of `ClientIP`.  As
a result, kernel creation requests will be routed to different deployment instances (see 
deployment) thereby diminishing the need for a `LoadBalancer` type. Here's the service 
yaml entry from [enterprise-gateway.yaml](https://github.com/jupyter-incubator/enterprise_gateway/blob/master/etc/kubernetes/enterprise-gateway.yaml):
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
The deployment yaml essentially houses the pod description.  By increasing the number of `replicas`
a configuration can experience instant benefits of distributing Enterprise Gateway instances across 
the cluster.  This implies that once session persistence is provided, we should be able to provide 
highly available (HA) kernels.  Here's the yaml portion from [enterprise-gateway.yaml](https://github.com/jupyter-incubator/enterprise_gateway/blob/master/etc/kubernetes/enterprise-gateway.yaml)
that defines the Kubernetes deployment and pod (some items may have changed):
```yaml
apiVersion: apps/v1beta2
kind: Deployment
metadata:
  name: enterprise-gateway
  labels:
    gateway-selector: enterprise-gateway
    app: enterprise-gateway
spec:
  replicas: 2
  selector:
    matchLabels:
      gateway-selector: enterprise-gateway
  template:
    metadata:
      labels:
        gateway-selector: enterprise-gateway
        app: enterprise-gateway
    spec:
      serviceAccountName: enterprise-gateway-sa
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
          value: "['r_kubernetes','python_kubernetes','python_tf_kubernetes','scala_kubernetes','spark_r_kubernetes','spark_python_kubernetes','spark_scala_kubernetes']"
        image: elyra/enterprise-gateway:dev
        name: enterprise-gateway
        args: ["--elyra"]
        ports:
        - containerPort: 8888
```
#### Namespaces
A best practice for Kubernetes applications running in an enterprise is to isolate applications via namespaces.  Since 
Enterprise Gateway also requires isolation at the kernel level, it makes sense to use a namespace for each kernel, by default.

The initial namespace is created in the `enterprise-gateway.yaml` file using a default name of `enterprise-gateway`.  This
name is communicated to the EG application via the env variable `EG_NAMESPACE`.  All Enterprise Gateway components
reside in this namespace. 

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: enterprise-gateway
  labels:
    app: enterprise-gateway
```

By default, kernel namespaces are created when the respective kernel is launched.  At that time, the kernel namespace name
is computed from the kernel username (`KERNEL_USERNAME`) and its Id (`KERNEL_ID`) just like the kernel pod name.  Upon a
kernel's termination, this namespace - provided it was created by Enterprise Gateway - will be deleted.

Installations wishing to pre-create the kernel namespace can do so by conveying the name of the kernel namespace via
`KERNEL_NAMESPACE` in the `env` portion of the kernel creation request.  (They must also provide the namespace's 
service account name via `KERNEL_SERVICE_ACCOUNT_NAME` - see next section.)  When `KERNEL_NAMESPACE` is set, 
Enterprise Gateway will not attempt to create a kernel-specific namespace, nor will it attempt its deletion.  As a 
result, kernel namespace lifecycle management is the user's responsibility.

Although **not recommended**, installations requiring everything in the same namespace - Enterprise Gateway and all its 
kernels - can do so by setting env `EG_SHARED_NAMESPACE` to `True`. When set, all kernels will run in the enterprise
gateway namespace, essentially eliminating all aspects of isolation between kernel instances.

#### Role-Based Access Control (RBAC)
Another best practice of Kubernetes applications is to define the minimally viable set of permissions
for the application.  Enterprise Gateway does this by defining role-based access control (RBAC) objects for
both Enterprise Gateway and kernels.

Because the Enterprise Gateway pod must create kernel namespaces, pods, services (for Spark support) and rolebindings, 
a cluster-scoped role binding is required.  The cluster role binding `enterprise-gateway-controller` also references the
subject, `enterprise-gateway-sa`, which is the service account associated with the Enterprise Gateway namespace and
also created by the yaml file.
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
    resources: ["pods", "namespaces", "services"]
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

The `enterprise-gateway.yaml` file also defines the minimally viable roles for a kernel pod - most of which
are required for Spark support.  Since kernels, by default, reside within their own namespace created upon their
launch, a cluster role is used within a namespace-scoped role binding created when the kernel's namespace is created.
The name of the kernel cluster role is `kernel-controller` and, when Enterprise Gateway creates the namespace and
role binding, is also the name of the role binding instance.

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

As noted above, installations wishing to pre-create their own kernel namespaces should provide the name of 
the service account associated with the namespace via `KERNEL_SERVICE_ACCOUNT_NAME` in the `env` portion of the kernel
creation request (along with `KERNEL_NAMESPACE`).  If not provided, the built-in namespace service account, `default`, 
will be referenced.  In such circumstances, Enterprise Gateway will **not** create a role binding on the name for the 
service account, so it is the user's responsibility to ensure that the service account has the capability to perform 
equivalent operations as defined by the `kernel-controller` role.

Here's an example of the creation of a custom namespace (`kernel-ns`) with its own service account (`kernel-sa`)
and role binding (`kernel-controller`) that references the cluster-scoped role (`kernel-controller`) and includes
appropriate labels to help with administration and analysis:
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

##### Kernelspec Modifications
One of the more common areas of customization we see occur within the kernelspec files located
in /usr/local/share/jupyter/kernels.  To accommodate the ability to customize the kernel definitions,
the kernels directory can be exposed as a 
_[Persistent Volume](https://kubernetes.io/docs/concepts/storage/persistent-volumes)_ thereby making 
it available to all pods within the Kubernetes cluster.

As an example, we have included a stanza for creating a Persistent Volume (PV) and Persistent Volume 
Claim (PVC), along with appropriate references to the PVC within each pod definition within [enterprise-gateway.yaml](https://github.com/jupyter-incubator/enterprise_gateway/blob/master/etc/kubernetes/enterprise-gateway.yaml).
 By default, these references are commented out as they require
the system administrator configure the appropriate PV type (e.g., nfs) and server IP.

```yaml
kind: PersistentVolume
apiVersion: v1
metadata:
  name: kernelspecs-pv
  labels:
    app: enterprise-gateway
spec:
  capacity:
    storage: 10Mi
  accessModes:
    - ReadOnlyMany
  nfs:
    server: <IPv4>
    path: /usr/local/share/jupyter/kernels
---
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: kernelspecs-pvc
  labels:
    app: enterprise-gateway
spec:
  accessModes:
    - ReadOnlyMany
  resources:
    requests:
      storage: 10Mi
  selector:
    matchLabels:
      app: enterprise-gateway
```
Once a Persistent Volume and Persistent Volume Claim have been created, pods that desire mounting
the volume can simply refer to it by its PVC name.

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
          value: "['r_kubernetes','python_kubernetes','python_tf_kubernetes','scala_kubernetes','spark_r_kubernetes','spark_python_kubernetes','spark_scala_kubernetes']"
        image: elyra/enterprise-gateway:dev
        name: enterprise-gateway
        args: ["--elyra"]
        ports:
        - containerPort: 8888
# Uncomment to enable PV for kernelspecs
        volumeMounts:
        - mountPath: /usr/local/share/jupyter/kernels
          name: kernelspecs
      volumes:
      - name: kernelspecs
        persistentVolumeClaim:
          claimName: kernelspecs-pvc
```
Note that because the kernel pod definition file, [kernel-pod.yaml](https://github.com/jupyter-incubator/enterprise_gateway/blob/master/etc/kernel-launchers/kubernetes/scripts/kernel-pod.yaml), 
resides in the kernelspecs hierarchy, updates or modifications to kubernetes kernel instances can now 
also take place.  (We'll be looking at ways to make modifications to per-kernel configurations more manageable.)

### Kubernetes Kernel Instances
There are essentially two kinds of kernels (independent of language) launched within an 
Enterprise Gateway Kubernetes cluster - _vanilla_ and _spark-on-kubernetes_ (if available).

When _vanilla_ kernels are launched, Enterprise Gateway is responsible for creating the 
corresponding pod. On the other hand, _spark-on-kubernetes_ kernels are launched via 
`spark-submit` with a specific `master` URI - which then creates the corresponding
pod(s) (including executor pods).  Today, both launch mechanisms, however, use the same underlying 
docker image for the pod (although that will likely change).

Here's the yaml configuration used when _vanilla_ kernels are launched. As noted in the 
`KubernetesProcessProxy` section below, this file ([kernel-pod.yaml](https://github.com/jupyter-incubator/enterprise_gateway/blob/master/etc/kernel-launchers/kubernetes/scripts/kernel-pod.yaml))
serves as a template where each of the tags prefixed with `$` represent variables that are substituted at the 
time of the kernel's launch.
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: $kernel_username-$kernel_id
  namespace: $namespace
  labels:
    kernel_id: $kernel_id
    app: enterprise-gateway
spec:
  restartPolicy: Never
  serviceAccountName: $service_account
  containers:
  - env:
    - name: EG_RESPONSE_ADDRESS
      value: $response_address
    - name: KERNEL_CONNECTION_FILENAME
      value: $connection_filename
    - name: KERNEL_LANGUAGE
      value: $language
    - name: SPARK_CONTEXT_INITIALIZATION_MODE
      value: $spark_context_initialization_mode
    image: $docker_image
    name: $kernel_username-$kernel_id
    command: ["/etc/bootstrap-kernel.sh"]
```
There are a number of items worth noting:
1. Kernel pods can be identified in three ways using `kubectl`: 
    1. By the global label `app=enterprise-gateway` - useful when needing to identify all related objects (e.g., `kubectl get
all -l app=enterprise-gateway`) 
    1. By the kernel_id label `kernel_id=<kernel_id>` - useful when only needing specifics about a given 
    kernel.  This label is used internally by enterprise-gateway when performing its discovery and lifecycle management 
    operations.
    1. By the *component* label `component=kernel` - useful when needing to identity only kernels and not other enterprise-gateway
    components.  (Note, the latter can be isolated via `component=enterprise-gateway`.)
    
    Note that since kernels run in isolated namespaces by default, it's often helpful to include the 
    clause `--all-namespaces` on commands that will span namespaces.  To isolate commands to a given
    namespace, you'll need to add the namespace clause `--namespace <namespace-name>`.
1. Each kernel pod is named by the invoking user (via the `KERNEL_USERNAME` env) and its 
kernel_id (env `KERNEL_ID`).  This identifier also applies to those kernels launched 
within `spark-on-kubernetes`.
1. As noted above, if `KERNEL_NAMESPACE` is not provided in the request, Enterprise Gateway will create a namespace using the
same naming algorithm for the pod.  In addition, the `kernel-controller` cluster role will be bound to a 
namespace-scoped role binding of the same name using the namespace's default service account as its subject.  Users
wishing to use their own kernel namespaces must provide **both** `KERNEL_NAMESPACE` and `KERNEL_SERVICE_ACCOUNT_NAME`
as these are both used in the `kernel-pod.yaml` as `$namespace` and `$service_account`, respectively.
1. Kernel pods have restart policies of `Never`.  This is because the Jupyter framework already
has built-in logic for auto-restarting failed kernels and any other restart policy would likely
interfere with the built-in behaviors.
1. The parameters to the launcher that is built into the image are communicated via environment
variables as noted in the `env:` section above.

### KubernetesProcessProxy
To indicate that a given kernel should be launched into a Kubernetes configuration, the
kernel.json file must include a `process_proxy` stanza indicating a `class_name:`  of 
`KubernetesProcessProxy`. This ensures the appropriate lifecycle management will take place relative
to a Kubernetes environment.

Along with the `class_name:` entry, this process proxy stanza should also include a proxy 
configuration stanza  which specifies the docker image to associate with the kernel's
pod.  If this entry is not provided, the Enterprise Gateway implementation will use a default 
entry of `elyra/kernel-py:dev`.  In either case, this value is made available to the 
rest of the parameters used to launch the kernel by way of an environment variable: 
`EG_KUBERNETES_KERNEL_IMAGE`.

```json
{
  "process_proxy": {
    "class_name": "enterprise_gateway.services.processproxies.k8s.KubernetesProcessProxy",
    "config": {
      "image_name": "elyra/kernel-py:dev"
    }
  }
}
```
As always, kernels are launched by virtue of the `argv:` stanza in their respective kernel.json
files.  However, when launching _vanilla_ kernels in a kubernetes environment, what gets
invoked isn't the kernel's launcher, but, instead, a python script that is responsible
for using the [Kubernetes Python API](https://github.com/kubernetes-client/python) to 
create the corresponding pod instance.  The pod is _configured_ by applying the values 
to each of the substitution parameters into the [kernel-pod.yaml](https://github.com/jupyter-incubator/enterprise_gateway/blob/master/etc/kernel-launchers/kubernetes/scripts/kernel-pod.yaml) file previously displayed. 
This file resides in the same `scripts` directory as the kubernetes launch script - 
`launch_kubernetes.py` - which is referenced by the kernel.json's `argv:` stanza:
```json
{
  "argv": [
    "python",
    "/usr/local/share/jupyter/kernels/python_kubernetes/scripts/launch_kubernetes.py",
    "{connection_file}",
    "--RemoteProcessProxy.response-address",
    "{response_address}",
    "--RemoteProcessProxy.spark-context-initialization-mode",
    "none"
  ]
}
```
By default, _vanilla_ kernels use a value of `none` for the spark context initialization mode so
no context will be created automatically.

When the kernel is intended to target _Spark-on-kubernetes_, its launch is
very much like kernels launched in YARN _cluster mode_, albeit with a completely different
set of parameters.  Here's an example `SPARK_OPTS` string value which best conveys the idea:
```
    "SPARK_OPTS": "--master k8s://https://${KUBERNETES_SERVICE_HOST}:${KUBERNETES_SERVICE_PORT} --deploy-mode cluster --name ${KERNEL_USERNAME}-${KERNEL_ID} --conf spark.kubernetes.driver.label.app=enterprise-gateway --conf spark.kubernetes.driver.label.kernel_id=${KERNEL_ID} --conf spark.kubernetes.executor.label.app=enterprise-gateway --conf spark.kubernetes.executor.label.kernel_id=${KERNEL_ID} --conf spark.kubernetes.driver.docker.image=${EG_KUBERNETES_KERNEL_IMAGE} --conf spark.kubernetes.executor.docker.image=kubespark/spark-executor-py:v2.2.0-kubernetes-0.5.0 --conf spark.kubernetes.submission.waitAppCompletion=false",
```
Note that each of the labels previously discussed are also applied to the _driver_ and _executor_ pods.

For these invocations, the `argv:` is nearly identical to non-kubernetes configurations, invoking
a `run.sh` script which essentially holds the `spark-submit` invocation that takes the aforementioned
`SPARK_OPTS` as its primary parameter:
```json
{
  "argv": [
    "/usr/local/share/jupyter/kernels/spark_python_kubernetes/bin/run.sh",
    "{connection_file}",
    "--RemoteProcessProxy.response-address",
    "{response_address}",
    "--RemoteProcessProxy.spark-context-initialization-mode",
    "lazy"
  ]
}
```

### Deploying Enterprise Gateway on Kubernetes
Once the Kubernetes cluster is configured and `kubectl` is demonstrated to be working
on the master node, pull the Enterprise Gateway and Kernel images on each worker node:

```
docker pull elyra/enterprise-gateway:dev
docker pull elyra/kernel-py:dev
```

**Note:** It is important to pre-seed the worker nodes with **all** kernel images, otherwise the automatic download 
time will count against the kernel's launch timeout.  Although this will likely only impact the first launch of a given 
kernel on a given worker node, when multiplied against the number of kernels and worker nodes, it will prove to be a 
frustrating user experience. 

If it is not possible to pre-seed the nodes, you will likely need to adjust the `EG_KERNEL_LAUNCH_TIMEOUT` value 
in the `enterprise-gateway.yaml` file as well as the `KG_REQUEST_TIMEOUT` parameter that issue the kernel 
start requests from the `NB2KG` extension of the Notebook client.

##### Create the Enterprise Gateway kubernetes service and deployment
From the master node, create the service and deployment using the yaml file from the git
repository:

```
kubectl apply -f etc/kubernetes/enterprise-gateway.yaml

service "enterprise-gateway" created
deployment "enterprise-gateway" created
```
##### Confirm deployment and note the service port mapping
```
kubectl get all -l app=enterprise-gateway

NAME                        DESIRED   CURRENT   UP-TO-DATE   AVAILABLE   AGE
deploy/enterprise-gateway   1         1         1            1           2h

NAME                               DESIRED   CURRENT   READY     AGE
rs/enterprise-gateway-74c46cb7fc   1         1         1         2h

NAME                                     READY     STATUS    RESTARTS   AGE
po/enterprise-gateway-74c46cb7fc-jrkl7   1/1       Running   0          2h

NAME                     TYPE       CLUSTER-IP       EXTERNAL-IP   PORT(S)          AGE
svc/enterprise-gateway   NodePort   10.110.253.220   <none>        8888:32422/TCP   2h
```
Of particular importance is the mapping to port `8888` (e.g.,`32422`).  If you are
performing this on the same host as where the notebook will run, then you will need to note
the cluster-ip entry (e.g.,`10.110.253.220`).

(Note: if the number of replicas is > 1, then you will see two pods listed with different
five-character suffixes.)

**Tip:** You can avoid the need to point at a different port each time EG is launched by adding an
`externalIPs:` entry to the `spec:` section of the `enterprise-gateway.yaml` file.  The
file is delivered with this entry commented out.  Of course, you'll need to change the IP address
to that of your kubernetes master node once the comments characters have been removed.
```text
# Uncomment in order to use <k8s-master>:8888
#  externalIPs:
#  - 9.30.118.200
```

The value of the `KG_URL` used by `NB2KG` will vary depending on whether you choose to define an external IP
or not.  If and external IP is defined, you'll set `KG_URL=<externalIP>:8888` else you'll set `KG_URL=<k8s-master>:32422`
**but also need to restart clients each time Enterprise Gateway is started.**  As a result, use of the `externalIPs:` value
is highly recommended.


### Kubernetes Tips
The following items illustrate some useful commands for navigating Enterprise Gateway within a kubernetes envrionment.

- All objects created on behalf of Enterprise Gateway can be located using the label `app=enterprise-gateway`.  You'll
probably see duplicated entries for the deployments(deploy) and replication sets (rs) - I didn't include the
duplicates here.
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

- To shutdown Enterprise Gateway issue a delete command using the previously mentioned global label `app=enterprise-gateway`
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
Note that this should not imply that kernels be "shutdown" using a the `kernel_id=` label.  This will likely trigger
Jupyter's auto-restart logic - so its best to properly shutdown kernels prior to kubernetes object
deletions.

Also note that deleting the Enterprise Gateway namespace will not delete cluster-scoped resources like the cluster 
roles `enterprise-gateway-controller` and `kernel-controller` or the cluster role binding `enterprise-gateway-controller`.
The following commands can be used to delete these:
```
kubectl delete clusterrole -l app=enterprise-gateway 
kubectl delete clusterrolebinding -l app=enterprise-gateway
```

- To enter into a given pod (i.e., container) in order to get a better idea of what might be happening within the
container, use the exec command with the pod name
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
