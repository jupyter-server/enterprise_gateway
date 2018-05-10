Here are instructions I've found helpful in setting up and troubleshooting kubernetes...

### Setup

- Provision a fyre cluster (e.g., `elyra-kube{1,2,3}.fyre.ibm.com`). I would try to keep the 
nodes limited to two or three.

- Install Spark-on-Kubernetes.  Follow the first three steps from the 
[kube-setup](https://github.ibm.com/stc-east/kube-setup) repo, 
taking the `spark-on-kubernetes` option on step 3.

- If you don't have `elyra/kubernetes-enterprise-gateway:dev` or `elyra/kubernetes-kernel:dev` images, they
can be pulled from [docker hub](https://hub.docker.com/u/elyra/dashboard/) or build via 
`make clean bdist kernelspecs docker-images-kubernetes`.  (Note: you'll need to manually build the 
`elyra/anaconda:dev` image since its not baked into the Makefile at the moment.)

- On the worker nodes of your kubernetes fyre cluster (e.g., nodes 2 and 3) pull the two images from docker hub.
```
docker pull elyra/kubernetes-enterprise-gateway:dev
docker pull elyra/kubernetes-kernel:dev
```

- Either copy the `etc/docker/kubernetes-enterprise-gateway/kubernetes-enterprise-gateway.yaml`
to a local directory or clone the repo `git clone git@github.com:SparkTC/enterprise_gateway.git`.

### Helpful commands
Here are commands I found I used often, and typically in this order...

- Create the Enterprise Gateway kubernetes service and deployment
```
kubectl create -f etc/docker/kubernetes-enterprise-gateway/kubernetes-enterprise-gateway.yaml

service "enterprise-gateway" created
deployment "enterprise-gateway" created
```
- Confirm deployment and note service port mapping
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
(Of particular instance is the mapping to port `8888`.  In this case, `32422`.)

- Confirm proper startup of enterprise gateway via k8s logs
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

- On client, startup Notebook with NB2KG.  I use a script named `docker_jnb`.  Make sure the port for the gateway host
is the same port number referenced in the service port mapping (e.g., `32422`).
```
docker_jnb -u alice -l 9001 -n ~/notebooks/elyra --name alice-kube elyra-kube1.fyre.ibm.com:32422 > ~/logs/9001.out 2>&1 &
```

- Capture the token from the log (9001.out).  This also shows the complete `docker run` command.
```
docker run -t --rm -e LOG_LEVEL=INFO -e KERNEL_USERNAME=alice -e KG_HTTP_USER=alice -e KG_HTTP_PASS=guest-password  -e KG_URL=http://elyra-kube1.fyre.ibm.com:32422 --name alice-kube -p 9001:8888 -v /Users/kbates/notebooks/elyra:/tmp/notebooks -w /tmp/notebooks elyra/nb2kg:dev 
Starting nb2kg against gateway:  http://elyra-kube1.fyre.ibm.com:32422
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

- Once the token is entered into browser, you should see a list of kernels reflected in the enterprise gateway log
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

Kernels of type `python_kubernetes` should start and be usable.  Kernels of type `spark_python_kubernetes` do not 
complete startup at this time.

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

NAME                                         READY     STATUS    RESTARTS   AGE
po/eg-5e755458-a114-4215-96b7-bcb016fc7b62   1/1       Running   0          8s
po/enterprise-gateway-74c46cb7fc-jrkl7       1/1       Running   0          3h

```
- All objects related to kernels can be located using the label `kernel_id=<kernel_id>`
```
kubectl get all -l kernel_id=5e755458-a114-4215-96b7-bcb016fc7b62

NAME                                         READY     STATUS    RESTARTS   AGE
po/eg-5e755458-a114-4215-96b7-bcb016fc7b62   1/1       Running   0          28s
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
kubectl logs -f po/eg-5e755458-a114-4215-96b7-bcb016fc7b62
```

- The Kubernetes dashboard is useful as well.  Its located at port `30000` of the master node
```
https://elyra-kube1.fyre.ibm.com:30000/dashboard/#!/overview?namespace=default
```
From there, logs can be accessed by selecting the `Pods` option in the left-hand pane followed by the _lined_ icon on
the far right.