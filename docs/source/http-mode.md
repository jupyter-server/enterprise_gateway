## `notebook-http` Mode

The `KernelGatewayApp.api` command line argument can be set to `kernel_gateway.notebook_http`. This mode, or *personality*, has the kernel gateway expose annotated cells in the `KernelGatewayApp.seed_uri` notebook as HTTP resources.

To turn a notebook cell into a HTTP handler, you must prefix it with a single line comment. The comment describes the HTTP method and resource, as in the following Python example:

```python
# GET /hello/world
print("hello world")
```

The annotation above declares the cell contents as the code to execute when the kernel gateway receives a HTTP GET request for the path `/hello/world`. For other languages, the comment prefix may change, but the rest of the annotation remains the same.

Multiple cells may share the same annotation. Their content is concatenated to form a single code segment at runtime. This facilitates typical, iterative development in notebooks with lots of short, separate cells: The notebook author does not need to merge all of the cells into one, or refactor to use functions.

```python
# GET /hello/world
print("I'm cell #1")

# GET /hello/world
print("I'm cell #2")
```

### Getting the Request Data

Before the gateway invokes an annotated cell, it sets the value of a global notebook variable named `REQUEST` to a JSON string containing information about the request. You may parse this string to access the request properties.

For example, in Python:

```python
# GET /hello/world
req = json.loads(REQUEST)
# do something with req
```

You may specify path parameters when registering an endpoint by prepending a `:` to a path segment. For example, a path with parameters `firstName` and `lastName` would be defined as the following in a Python comment:

```python
# GET /hello/:firstName/:lastName
```

The `REQUEST` object currently contains the following properties:

* `body` - The value of the body, see the [Body And Content Type](#Request Content-Type and Request Body Processing) section below
* `args` - An object with keys representing query parameter names and their associated values. A query parameter name may be specified multiple times in a valid URL, and so each value is a sequence (e.g., list, array) of strings from the original URL.
* `path` - An object of key-value pairs representing path parameters and their values.
* `headers` - An object of key-value pairs where a key is a HTTP header name and a value is the HTTP header value. If there are multiple values are specified for a  header, the value will be an array.

#### Request Content-Type and Request Body Processing

If the HTTP request to the kernel gateway has a `Content-Type` header the value of `REQUEST.body` may change. Below is the list of outcomes for various mime-types:

* `application/json` -  The `REQUEST.body` will be an object of key-value pairs representing the request body
* `multipart/form-data` and `application/x-www-form-urlencoded` -  The `REQUEST.body` will be an object of key-value pairs representing the parameters and their values. Files are currently not supported for `multipart/form-data`
* `text/plain` -  The `REQUEST.body` will be the string value of the body
* All other types will be sent as strings

### Setting the Response Body

The response from an annotated cell may be set in one of two ways:

1. Writing to stdout in a notebook cell
2. Emitting output in a notebook cell

The first method is preferred because it is explicit: a cell writes to stdout using the appropriate language statement or function (e.g. Python `print`, Scala `println`, R `print`, etc.). The kernel gateway collects all bytes from kernel stdout and returns the entire byte string verbatim as the response body.

The second approach is used if nothing appears on stdout. This method is dependent upon language semantics, kernel implementation, and library usage. The response body will be the `content.data` structure in the Jupyter [`execute_result`](https://jupyter-client.readthedocs.io/en/latest/messaging.html#id4) message.

In both cases, the response defaults to status `200 OK` and `Content-Type: text/plain` if cell execution completes without error. If an error occurs, the status is `500 Internal Server Error`. If the HTTP request method is not one supported at the given path, the status is `405 Not Supported`. If you wish to return custom status or headers, see the next section.

See the [api_intro.ipynb](https://github.com/jupyter/kernel_gateway/blob/master/etc/api_examples/api_intro.ipynb) notebook for basic request and response examples.

### Setting the Response Status and Headers

Annotated cells may have an optional metadata companion cell that sets the HTTP response status and headers. Consider this Python cell that creates a person entry in a database table and returns the new row ID in a JSON object:

```python
# POST /person
req = json.loads(REQUEST)
row_id = person_table.insert(req['body'])
res = {'id' : row_id}
print(json.dumps(res))
```

Now consider this companion cell which runs after the cell above and sets a custom response header and status:

```python
# ResponseInfo POST /person
print(json.dumps({
    "headers" : {
        "Content-Type" : "application/json"
    },
    "status" : 201
}))
```

Currently, `headers` and `status` are the only fields supported. `headers` should be an object of key-value pairs mapping header names to header values. `status` should be an integer value. Both should be printed to stdout as JSON.

Given the two cells above, a `POST` request to `/person` produces a HTTP response like the following from the kernel gateway, assuming no errors occur:

```
HTTP/1.1 200 OK
Content-Type: application/json

{"id": 123}
```

See the [setting_response_metadata.ipynb](https://github.com/jupyter/kernel_gateway/blob/master/etc/api_examples/setting_response_metadata.ipynb) notebook for examples of setting response metadata.

### Swagger Spec

The resource `/_api/spec/swagger.json` is automatically generated from the notebook used to define the HTTP API. The response is a simple Swagger spec which can be used with the [Swagger editor](http://editor.swagger.io/#), a [Swagger ui](https://github.com/swagger-api/swagger-ui), or with any other Swagger-aware tool.

Currently, every response is listed as having a status of `200 OK`.

### Running

The minimum number of arguments needed to run in HTTP mode are `--KernelGatewayApp.api=kernel_gateway.notebook_http` and `--KernelGatewayApp.seed_uri=some/notebook/file.ipynb`.

The notebook-http mode will honor the `prespawn_count` command line argument. This will start the specified number of kernels and execute the `seed_uri` notebook on each one. Requests will be distributed across the pool of prespawned kernels, providing a minimal layer of scalability. An example which starts a pool of 5 kernels follows:

```bash
jupyter kernelgateway \
    --KernelGatewayApp.api='kernel_gateway.notebook_http' \
    --KernelGatewayApp.seed_uri='/srv/kernel_gateway/etc/api_examples/api_intro.ipynb' \
    --KernelGatewayApp.prespawn_count=5
```

Refer to the [scotch recommendation API demo](https://github.com/jupyter/kernel_gateway_demos/tree/master/scotch_demo) for more detail.

If you have a development setup, you can run the kernel gateway in `notebook-http` mode using the Makefile in this repository:

```bash
make dev ARGS="--KernelGatewayApp.api='kernel_gateway.notebook_http' \
--KernelGatewayApp.seed_uri=/srv/kernel_gateway/etc/api_examples/api_intro.ipynb"
```

With the above Make command, all of the notebooks in `etc/api_examples` are
mounted into `/srv/kernel_gateway/etc/api_examples/` and can be run in HTTP mode.
