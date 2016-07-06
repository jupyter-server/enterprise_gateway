## Developing New Modes

The `KernelGatewayApp.api` can be set to the name of any module in the Python path supplying a personality. This allows for alternate kernel communications mechanisms.

The module must contain a ``create_personality`` function whose ``parent`` argument will be the kernel gateway application, and which must return a *personality* object. That object will take part in the kernel gateway's lifecycle and act as a delegate for certain responsibilities. An example module, subclassing ``LoggingConfigurable`` as recommended, is shown here:

```
from traitlets.config.configurable import LoggingConfigurable

class TemplatePersonality(LoggingConfigurable):
    def init_configurables(self):
        """This function will be called when the kernel gateway has completed its own 
        `init_configurables`, typically after its traitlets have been evaluated."""
        pass 

    def shutdown(self):
        """During a proper shutdown of the kernel gateway, this will be called so that
        any held resources may be properly released."""
        pass 

    def create_request_handlers(self):
        """Returns a list of zero or more tuples of handler path, Tornado handler class
        name, and handler arguments, that should be registered in the kernel gateway's 
        web application. Paths are used as given and should respect the kernel gateway's 
        `base_url` traitlet value."""
        pass 

    def should_seed_cell(self, code):
        """Determines whether the kernel gateway will include the given notebook code 
        cell when seeding a new kernel. Will only be called if a seed notebook has 
        been specified."""
        pass

def create_personality(self, parent):
    """Put docstring here."""
    return TemplatePersonality(parent=parent)
```

Provided personalities include
  [kernel_gateway.jupyter_websocket](_modules/kernel_gateway/jupyter_websocket.html) and   [kernel_gateway.notebook_http](_modules/kernel_gateway/notebook_http.html).
