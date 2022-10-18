---
layout: page
title: Jupyter Enterprise Gateway and Kubernetes
---

Recently, we have experienced various advances in AI, in particular around Deep Learning. This have
increased the popularity of Deep Learning use cases and also the proliferation of several development
frameworks that have different runtime and deployment requirements. Containers provides a very flexible
way to build such heterogenous environments and Kubernetes provides an easy way to deploy and manage such
deployments with the benefit of elasticity and other quality of services.

Jupyter Enterprise Gateway extends the Jupyter Notebook platform and enables Jupyter Notebook
kernels to run as independent pods in a Kubernetes cluster, providing the necessary environment
isolation to support the development and training of Deep Learning models.

Using the Kubernetes support in Jupyter Enterprise Gateway, the container image where the kernel will be
launched becomes a choice, where you can easily start a Python kernel on a TensorFlow community image
to enable working on TensorFlow models, or you can have a Python kernel on a PyTorch community image.

Kubernetes also gives the ability to associate/share specialized hardwares such as GPUs and TPUs
to the kernel pod, providing necessary power for training Deep Learning models.

<br/>

<div align="center">
  <img src="./img/platform-kubernetes.png" height="50%" width="50%">
</div>

<br/>

### Deployment

<br/>

Jupyter Enterprise Gateway can easily be deployed into your Kubernetes cluster:

<div>
<pre><code>kubectl apply -f https://raw.githubusercontent.com/jupyter/enterprise_gateway/main/etc/kubernetes/enterprise-gateway.yaml</code></pre>
</div>

#### Deployment Scripts

<br/>

The Jupyter Enterprise Gateway development team uses some Ansible scripts for provisioning
test environments, these scripts might be useful for users trying to get started with the gateway
on a Kubernetes environment.

- Ansible Deployment scripts : <a href="https://github.com/lresende/ansible-spark-cluster">ansible-kubernetes-cluster</a>
