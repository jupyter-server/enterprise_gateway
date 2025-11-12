# Sequence Diagrams

The following consists of various sequence diagrams you might find helpful. We plan to add
diagrams based on demand and contributions.

## Kernel launch: Jupyter Lab to Enterprise Gateway

This diagram depicts the interactions between components when a kernel start request
is submitted from Jupyter Lab running against [Jupyter Server configured to use
Enterprise Gateway](../users/connecting-to-eg.md). The diagram also includes the
retrieval of kernel specifications (kernelspecs) prior to the kernel's initialization.

```{mermaid}
    sequenceDiagram
        participant JupyterLab
        participant JupyterServer
        participant EnterpriseGateway
        participant ProcessProxy
        participant Kernel
        participant ResourceManager
        Note left of JupyterLab: fetch kernelspecs
        JupyterLab->>JupyterServer: https GET api/kernelspecs
        JupyterServer->>EnterpriseGateway: https GET api/kernelspecs
        EnterpriseGateway-->>JupyterServer: api/kernelspecs response
        JupyterServer-->>JupyterLab: api/kernelspecs response

        Note left of JupyterLab: kernel initialization
        JupyterLab->>JupyterServer: https POST api/sessions
        JupyterServer->>EnterpriseGateway: https POST api/kernels
        EnterpriseGateway->>ProcessProxy: launch_process()
        ProcessProxy->>Kernel: launch kernel
        ProcessProxy->>ResourceManager: confirm startup
        Kernel-->>ProcessProxy: connection info
        ResourceManager-->>ProcessProxy: state & host info
        ProcessProxy-->>EnterpriseGateway: complete connection info
        EnterpriseGateway->>Kernel: TCP socket requests
        Kernel-->>EnterpriseGateway: TCP socket handshakes
        EnterpriseGateway-->>JupyterServer: api/kernels response
        JupyterServer-->>JupyterLab: api/sessions response

        JupyterLab->>JupyterServer: ws GET api/kernels
        JupyterServer->>EnterpriseGateway: ws GET api/kernels
        EnterpriseGateway->>Kernel: kernel_info_request message
        Kernel-->>EnterpriseGateway: kernel_info_reply message
        EnterpriseGateway-->>JupyterServer: websocket upgrade response
        JupyterServer-->>JupyterLab: websocket upgrade response
```
