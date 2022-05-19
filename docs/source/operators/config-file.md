# Configuration file options

Placing configuration options into the configuration file `jupyter_enterprise_gateway_config.py` is recommended because this will enabled the use of the [_dynamic configurables_](config-dynamic.md/#dynamic-configurables) functionality. To generate a template configuration file, run the following:

```bash
jupyter enterprisegateway --generate-config
```

This command will produce a `jupyter_enterprise_gateway_config.py` file, typically located in the invoking user's `$HOME/.jupyter` directory. The file contains python code, including comments, relative to each available configuration option. The actual option itself will also be commented out. To enable that option, set its value and uncomment the code.

```{Note}
Some options may appear duplicated.  For example, the `remote_hosts` trait appears on both `c.EnterpriseGatewayConfigMixin` and `c.EnterpriseGatewayApp`.  This is due to how configurable traits appear in the class hierarchy. Since `EnterpriseGatewayApp` derives from `EnterpriseGatewayConfigMixin` and both are configurable classes, the output contains duplicated values.  If both values are set, the value _closest_ to the derived class will be used (in this case, `EnterpriseGatewayApp`).
```

Here's an example entry. Note that its default value, when defined, is also displayed, along with the corresponding environment variable name:

```python
## Bracketed comma-separated list of hosts on which DistributedProcessProxy
#  kernels will be launched e.g., ['host1','host2'].
#  (EG_REMOTE_HOSTS env var - non-bracketed, just comma-separated)
#  Default: ['localhost']
# c.EnterpriseGatewayConfigMixin.remote_hosts = ['localhost']
```
