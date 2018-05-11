# Kubernetes Integration
This page describes the approach taken for integrating Enterprise Gateway into an existing
Kubernetes cluster.

In this solution, Enterprise Gateway is, itself, provisioned as a Kubernetes _deployment_ 
and exposed as a Kubernetes _service_.  In this way, Enterprise Gateway can leverage load 
balancing and high availability functionality provided by Kubernetes (although HA cannot be
fully realized until EG supports persistent sessions).

When residing in a [spark-on-kubernetes](https://github.com/apache-spark-on-k8s/spark) 
cluster, Enterprise Gateway can easily support cluster-managed kernels distributed across 
the cluster. Enterprise Gateway will also provide standalone (i.e., _vanilla_) kernel 
invocation (where spark contexts are not automatically created) which also benefits from 
their distribution across the cluster.

### Enterprise Gateway Deployment
Enterprise Gateway manifests itself as a Kubernetes deployment, exposed externally by a 
Kubernetes service.  It is identified by the name `enterprise-gateway` within the cluster. 
In addition, all objects related to Enterprise Gateway have the kubernetes label of 
`app=enterprise-gateway` applied.

The service is currently configured as type `NodePort` but is intended for type 
`LoadBalancer` when appropriate network plugins are available.  Because kernels
are stateful, the service is also configured with a `sessionAffinity` of `ClientIP`.  As
a result, kernel creation requests will be routed to different deployment instances (see 
deployment) thereby diminishing the need for a `LoadBalancer` type. Here's the service 
yaml entry from `kubernetes-enterprise-gateway.yaml`:
```yaml
apiVersion: v1
kind: Service
metadata:
  labels:
    app: enterprise-gateway
  name: enterprise-gateway
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
a configuration can experience instant benefits of distributing enterprise-gateway instances across 
the cluster.  This implies that once session persistence is provided, we should be able to provide 
highly available (HA) kernels.  Here's the yaml portion from `kubernetes-enterprise-gateway.yaml` 
that defines the Kubernetes deployment (and pod):
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
      containers:
      - env:
        - name: EG_KUBERNETES_NAMESPACE
          value: "default"
        - name: EG_TUNNELING_ENABLED
          value: "False"
        - name: EG_CULL_IDLE_TIMEOUT
          value: "600"
        - name: EG_LOG_LEVEL
          value: "DEBUG"
        image: elyra/kubernetes-enterprise-gateway:dev
        name: enterprise-gateway
        args: ["--elyra"]
        ports:
        - containerPort: 8888
```

### Kubernetes Kernel Instances
There are essentially two kinds of kernels (independent of language) launched within an 
Enterprise Gateway Kubernetes cluster - _vanilla_ and _spark-on-kubernetes_ (if available).

When _vanilla_ kernels are launched, Enterprise Gateway is responsible for creating the 
corresponding pod. On the other hand, _spark-on-kubernetes_ kernels are launched via 
`spark-submit` with a specific `master` URI - which then creates the corresponding
pod(s) (including executor pods).  Both launch mechanisms, however, use the same underlying 
docker image for the pod.

Here's the yaml configuration used when _vanilla_ kernels are launched. As noted in the 
`KubernetesProcessProxy` section below, this file (`kernel-pod.yaml`) serves as a template
where each of the tags prefixed with `$` represent variables that are substituted at the 
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
  containers:
  - env:
    - name: EG_RESPONSE_ADDRESS
      value: $response_address
    - name: KERNEL_CONNECTION_FILENAME
      value: $connection_filename
    - name: KERNEL_LANGUAGE
      value: $language
    - name: NO_SPARK_CONTEXT
      value: $no_spark_context
    image: $docker_image
    name: $kernel_username-$kernel_id
    command: ["/usr/local/share/jupyter/kernels/bootstrap-kernel.sh"]
```
There are a number of items worth noting:
1. Each kernel pod can be identified in two ways using `kubectl`: 1) by the global label
`app=enterprise-gateway` - useful when needing to identify all related objects (e.g., `kubectl get
all -l app=enterprise-gateway`) and 2) by the kernel_id label `kernel_id=<kernel_id>` - useful
when only needing specifics about a given kernel.  This label is used internally by enterprise-gateway 
when performing its discovery and lifecycle management operations.
2. Each kernel pod is named by the invoking user (via the `KERNEL_USERNAME` env) and its 
kernel_id (env `KERNEL_ID`).  This identifier also applies to those kernels launched 
within `spark-on-kubernetes`.
3. Kernel pods have restart policies of `Never`.  This is because the Jupyter framework already
has built-in logic for auto-restarting failed kernels and any other restart policy would likely
interfere with the built-in behaviors.
4. The parameters to the launcher that is built into the image are communicated via environment
variables as noted in the `env:` section above.

### KubernetesProcessProxy
To indicate that a given kernel should be launched into a Kubernetes configuration, the
kernel.json file must include a `process_proxy` stanza indicating a `class_name:`  of 
`KubernetesProcessProxy`. This ensures the appropriate lifecycle management will take place.

Along with the `class_name:` entry, this process proxy stanza should also include a proxy 
configuration stanza  which specifies the docker image to associate with the kernel's
pod.  If this entry is not provided, the Enterprise Gateway implementation will use a default 
entry of `elyra/kubernetes-kernel:dev`.  In either case, this value is made available to the 
rest of the parameters used to launch the kernel by way of an environment variable: 
`EG_KUBERNETES_KERNEL_IMAGE`.

```json
  "process_proxy": {
    "class_name": "enterprise_gateway.services.processproxies.k8s.KubernetesProcessProxy",
    "config": {
      "image_name": "elyra/kubernetes-kernel:dev"
    }
```
As always, kernels are launched by virtue of the `argv:` stanza in their respective kernel.json
files.  However, when launching _vanilla_ kernels in a kubernetes environment, what gets
invoked isn't the kernel's launcher, but, instead, a python script that is responsible
for using the [Kubernetes Python API](https://github.com/kubernetes-client/python) to 
create the corresponding pod instance.  The pod is _configured_ by applying the values 
to each of the substitution parameters into the `kernel-pod.yaml` file previously displayed. 
This file resides in the same `scripts` directory as the kubernetes launch script - 
`launch_kubernetes.py` - which is referenced by the kernel.json's `argv:` stanza:
```json
  "argv": [
    "python",
    "/usr/local/share/jupyter/kernels/python_kubernetes/scripts/launch_kubernetes.py",
    "{connection_file}",
    "--RemoteProcessProxy.response-address",
    "{response_address}",
    "--RemoteProcessProxy.no-spark-context"
  ]
```
By default, _vanilla_ kernels use a flag to indicate no spark context will automatically be 
created (`--RemoteProcessProxy.no-spark-context`).

When the kernel is intended to target _Spark-on-kubernetes_, its launch is
very much like kernels launched in YARN _cluster mode_, albeit with a completely different
set of parameters.  Here's an example `SPARK_OPTS` string value which best conveys the idea:
```json
    "SPARK_OPTS": "--master k8s://https://${KUBERNETES_SERVICE_HOST}:${KUBERNETES_SERVICE_PORT} --deploy-mode cluster --name ${KERNEL_USERNAME}-${KERNEL_ID} --conf spark.kubernetes.driver.label.app=enterprise-gateway --conf spark.kubernetes.driver.label.kernel_id=${KERNEL_ID} --conf spark.kubernetes.executor.label.app=enterprise-gateway --conf spark.kubernetes.executor.label.kernel_id=${KERNEL_ID} --conf spark.kubernetes.driver.docker.image=${EG_KUBERNETES_KERNEL_IMAGE} --conf spark.kubernetes.executor.docker.image=kubespark/spark-executor-py:v2.2.0-kubernetes-0.5.0 --conf spark.kubernetes.submission.waitAppCompletion=false",
```
Note that each of the labels previously discussed are also applied to the _driver_ and _executor_ pods.

For these invocations, the `argv:` is nearly identical to non-kubernetes configurations, invoking
a `run.sh` script which essentially holds the `spark-submit` invocation which takes the aforementioned
`SPARK_OPTS` as its primary parameter:
```json
  "argv": [
    "/usr/local/share/jupyter/kernels/spark_python_kubernetes/bin/run.sh",
    "{connection_file}",
    "--RemoteProcessProxy.response-address",
    "{response_address}"
  ]
```

### Deploying Enterprise Gateway on Kubernetes
Once the Kubernetes cluster is configured and `kubectl` is demonstrated to be working
on the master node, pull the Enterprise Gateway and Kernel images on each worker node:

```
docker pull elyra/kubernetes-enterprise-gateway:dev
docker pull elyra/kubernetes-kernel:dev
```
##### Create the Enterprise Gateway kubernetes service and deployment
From the master node, create the service and deployment using the yaml file from the git
repository:

```
kubectl create -f etc/docker/kubernetes-enterprise-gateway/kubernetes-enterprise-gateway.yaml

service "enterprise-gateway" created
deployment "enterprise-gateway" created
```
##### Confirm deployment and note service port mapping
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

##### Confirm proper startup of enterprise gateway via k8s logs
```
kubectl logs -f deploy/enterprise-gateway

Starting Jupyter Enterprise Gateway...
[D 2018-01-30 19:26:20.588 EnterpriseGatewayApp] Searching [u'/usr/local/share/jupyter', '/root/.jupyter', '/usr/etc/jupyter', '/usr/local/etc/jupyter', '/etc/jupyter'] for config files
[D 2018-01-30 19:26:20.588 EnterpriseGatewayApp] Looking for jupyter_config in /etc/jupyter
[D 2018-01-30 19:26:20.588 EnterpriseGatewayApp] Looking for jupyter_config in /usr/local/etc/jupyter
[D 2018-01-30 19:26:20.589 EnterpriseGatewayApp] Looking for jupyter_config in /usr/etc/jupyter
[D 2018-01-30 19:26:20.589 EnterpriseGatewayApp] Looking for jupyter_config in /root/.jupyter
[D 2018-01-30 19:26:20.589 EnterpriseGatewayApp] Looking for jupyter_config in /usr/local/share/jupyter
[D 2018-01-30 19:26:20.590 EnterpriseGatewayApp] Looking for jupyter_enterprise_gateway_config in /etc/jupyter
[D 2018-01-30 19:26:20.590 EnterpriseGatewayApp] Looking for jupyter_enterprise_gateway_config in /usr/local/etc/jupyter
[D 2018-01-30 19:26:20.590 EnterpriseGatewayApp] Looking for jupyter_enterprise_gateway_config in /usr/etc/jupyter
[D 2018-01-30 19:26:20.590 EnterpriseGatewayApp] Looking for jupyter_enterprise_gateway_config in /root/.jupyter
[D 2018-01-30 19:26:20.591 EnterpriseGatewayApp] Looking for jupyter_enterprise_gateway_config in /usr/local/share/jupyter
[I 2018-01-30 19:26:20.602 EnterpriseGatewayApp] Jupyter Enterprise Gateway at http://0.0.0.0:8888
```
(Note, if the number of replicas is > 1, then you will see an indication in the first line of 
output as to which pod this logs command is tailing.  Specific pods can be logged using:
`kubectl logs -f po/<pod>` (e.g., `kubectl logs -f po/enterprise-gateway-74c46cb7fc-jrkl7`)).

##### On the client, startup Notebook with NB2KG.  
I use a script named `docker_jnb` which essentially invokes `docker run`.  Make sure the port 
for the gateway host is the same port number referenced in the service port mapping 
(e.g., `32422`), or, if on the same host, use the cluster-ip and port `8888` (e.g., 
`10.110.253.220:8888`) instead of the DNS name.
```
docker_jnb -u alice -l 9001 -n ~/notebooks/elyra --name alice-kube elyra-kube1.foo.bar.com:32422 > ~/logs/9001.out 2>&1 &
```

Capture the token from the log (9001.out).  This also shows the complete `docker run` command.
```
docker run -t --rm -e LOG_LEVEL=INFO -e KERNEL_USERNAME=alice -e KG_HTTP_USER=alice -e KG_HTTP_PASS=guest-password  -e KG_URL=http://elyra-kube1.foo.bar.com:32422 --name alice-kube -p 9001:8888 -v /Users/kbates/notebooks/elyra:/tmp/notebooks -w /tmp/notebooks elyra/nb2kg:dev 
Starting nb2kg against gateway:  http://elyra-kube1.foo.bar.com:32422
Nootbook port:  8888
Kernel user:  alice
[I 19:27:23.045 NotebookApp] Writing notebook server cookie secret to /home/jovyan/.local/share/jupyter/runtime/notebook_cookie_secret
[I 19:27:23.343 NotebookApp] JupyterLab alpha preview extension loaded from /opt/conda/lib/python3.6/site-packages/jupyterlab
[I 19:27:23.345 NotebookApp] Loaded nb2kg extension
[I 19:27:23.345 NotebookApp] Overriding handler URLSpec('/api/kernelspecs/(?P<kernel_name>[\\w\\.\\-%]+)$', <class 'nb2kg.handlers.KernelSpecHandler'>, kwargs=None, name=None)
[I 19:27:23.345 NotebookApp] Overriding handler URLSpec('/api/kernelspecs$', <class 'nb2kg.handlers.MainKernelSpecHandler'>, kwargs=None, name=None)
[I 19:27:23.345 NotebookApp] Overriding handler URLSpec('/api/kernels/(?P<kernel_id>\\w+-\\w+-\\w+-\\w+-\\w+)/channels$', <class 'nb2kg.handlers.WebSocketChannelsHandler'>, kwargs=None, name=None)
[I 19:27:23.346 NotebookApp] Overriding handler URLSpec('/api/kernels/(?P<kernel_id>\\w+-\\w+-\\w+-\\w+-\\w+)/(?P<action>restart|interrupt)$', <class 'nb2kg.handlers.KernelActionHandler'>, kwargs=None, name=None)
[I 19:27:23.346 NotebookApp] Overriding handler URLSpec('/api/kernels/(?P<kernel_id>\\w+-\\w+-\\w+-\\w+-\\w+)$', <class 'nb2kg.handlers.KernelHandler'>, kwargs=None, name=None)
[I 19:27:23.346 NotebookApp] Overriding handler URLSpec('/api/kernels$', <class 'nb2kg.handlers.MainKernelHandler'>, kwargs=None, name=None)
[I 19:27:23.349 NotebookApp] Serving notebooks from local directory: /tmp/notebooks
[I 19:27:23.349 NotebookApp] 0 active kernels
[I 19:27:23.349 NotebookApp] The Jupyter Notebook is running at:
[I 19:27:23.349 NotebookApp] http://0.0.0.0:8888/?token=bbc11af31786bd9b313ae1c330d53c9b944f596c4b6f3e95
[I 19:27:23.349 NotebookApp] Use Control-C to stop this server and shut down all kernels (twice to skip confirmation).
[C 19:27:23.349 NotebookApp] 
    
    Copy/paste this URL into your browser when you connect for the first time,
    to login with a token:
        http://0.0.0.0:8888/?token=bbc11af31786bd9b313ae1c330d53c9b944f596c4b6f3e95
```

Once the token is entered into the browser prompt, you should see a list of kernels reflected 
in the enterprise gateway log.  If using more than one replica and you don't see this additional
output, check the log of the othe replica pod.
```
[D 2018-01-30 19:27:37.852 EnterpriseGatewayApp] Found kernel python_kubernetes in /usr/local/share/jupyter/kernels
[D 2018-01-30 19:27:37.852 EnterpriseGatewayApp] Found kernel spark_python_kubernetes in /usr/local/share/jupyter/kernels
[D 2018-01-30 19:27:37.852 EnterpriseGatewayApp] Found kernel spark_r_yarn_client in /usr/local/share/jupyter/kernels
[D 2018-01-30 19:27:37.852 EnterpriseGatewayApp] Found kernel spark_python_yarn_cluster in /usr/local/share/jupyter/kernels
[D 2018-01-30 19:27:37.852 EnterpriseGatewayApp] Found kernel spark_python_yarn_client in /usr/local/share/jupyter/kernels
[D 2018-01-30 19:27:37.852 EnterpriseGatewayApp] Found kernel spark_r_yarn_cluster in /usr/local/share/jupyter/kernels
[D 2018-01-30 19:27:37.852 EnterpriseGatewayApp] Found kernel spark_scala_yarn_cluster in /usr/local/share/jupyter/kernels
[D 2018-01-30 19:27:37.852 EnterpriseGatewayApp] Found kernel spark_scala_yarn_client in /usr/local/share/jupyter/kernels
[D 2018-01-30 19:27:37.852 EnterpriseGatewayApp] Found kernel python2 in /usr/share/jupyter/kernels
```
Open or create notebooks with either `python_kubernetes` or `spark_python_kubernetes` - both should be usable.

### Troubleshooting Tips

- All objects created on behalf of enterprise gateway can be located using the label `app=enterprise-gateway`.  You'll
probably see duplicated entries for the deployments(deploy) and replication sets (rs) - I didn't include the
duplicates here.
```
kubectl get all -l app=enterprise-gateway

NAME                        DESIRED   CURRENT   UP-TO-DATE   AVAILABLE   AGE
deploy/enterprise-gateway   1         1         1            1           3h

NAME                               DESIRED   CURRENT   READY     AGE
rs/enterprise-gateway-74c46cb7fc   1         1         1         3h

NAME                                            READY     STATUS    RESTARTS   AGE
po/alice-5e755458-a114-4215-96b7-bcb016fc7b62   1/1       Running   0          8s
po/enterprise-gateway-74c46cb7fc-jrkl7          1/1       Running   0          3h

```
- All objects related to kernels can be located using the label `kernel_id=<kernel_id>`
```
kubectl get all -l kernel_id=5e755458-a114-4215-96b7-bcb016fc7b62

NAME                                            READY     STATUS    RESTARTS   AGE
po/alice-5e755458-a114-4215-96b7-bcb016fc7b62   1/1       Running   0          28s
```

- To terminate all enterprise-gateway objects, use the same label `app=enterprise-gateway`
```
kubectl delete all -l app=enterprise-gateway
```

- To enter into a given pod (i.e., container), use the exec command with the pod name
```
kubectl exec -it enterprise-gateway-74c46cb7fc-jrkl7 /bin/bash
```

- Logs can be accessed against the pods or deployment (requires the object type prefix (e.g., `po/`))
```
kubectl logs -f po/alice-5e755458-a114-4215-96b7-bcb016fc7b62
```

- The Kubernetes dashboard is useful as well.  Its located at port `30000` of the master node
```
https://elyra-kube1.foo.bar.com:30000/dashboard/#!/overview?namespace=default
```
From there, logs can be accessed by selecting the `Pods` option in the left-hand pane followed by the _lined_ icon on
the far right.


### Spark-on-Kubernetes Setup (internal)
Here are some instructions for setting up Kubernetes on a Fyre cluster.  It leverages scripts
provided by STC-East and should be considered internal information.

- Provision a fyre cluster (e.g., `elyra-kube{1,2,3}.fyre.ibm.com`). I would try to keep the 
nodes limited to two or three.

- Install Spark-on-Kubernetes.  Follow the first three steps from the 
[kube-setup](https://github.ibm.com/stc-east/kube-setup) repo, 
taking the `spark-on-kubernetes` option on step 3.

- If you don't have `elyra/kubernetes-enterprise-gateway:dev` or `elyra/kubernetes-kernel:dev` images, they
can be pulled from [docker hub](https://hub.docker.com/u/elyra/dashboard/) or build via 
`make clean bdist kernelspecs docker-images-kubernetes`. 

- Either copy the `etc/docker/kubernetes-enterprise-gateway/kubernetes-enterprise-gateway.yaml`
to a local directory or clone the repo `git clone git@github.com:SparkTC/enterprise_gateway.git`.
