open -a Docker

minikube -p ray stop                              # this keep updating the existing cluster
# minikube -p ray stop && minikube -p ray delete  # this always create a new cluster

# Launch Minikube
minikube start -p ray --driver=docker --kubernetes-version=v1.31 --memory=12000
minikube profile ray

# Ray operator helm
helm repo add kuberay https://ray-project.github.io/kuberay-helm/
helm repo update

helm install kuberay-operator kuberay/kuberay-operator --version 1.5.0 --create-namespace --wait

helm upgrade --install enterprise-gateway ../../../dist/jupyter_enterprise_gateway_helm-*.tar.gz --namespace enterprise-gateway --values enterprise-gateway-minikube-helm.yaml --create-namespace --wait
kubectl apply -f enterprise-gateway-network.yaml
# minikube service --url enterprise-gateway -n enterprise-gateway

# Install JupyterHub
helm repo add jupyterhub https://jupyterhub.github.io/helm-chart/
helm repo update

helm upgrade --install hub jupyterhub/jupyterhub --namespace hub --version 4.3.1 --values jupyterhub-config.yaml --create-namespace --timeout 10m --wait
minikube service --url proxy-public -n hub
