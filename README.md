# Poetry gRPC plugin

A [**Poetry**](https://python-poetry.org/) plugin to run the Protocol Buffers compiler with gRPC support.

### Installing the plugin

Requires Poetry version `1.2.0rc2` or above

```shell
poetry self add poetry-grpc-plugin
```

### Usage

To run it manually:

```console
poetry help protoc

Usage:
  protoc [options]

Options:
      --proto_path[=PROTO_PATH]             [default: "."]
      --python_out[=PYTHON_OUT]             [default: "."]
      --grpc_python_out[=GRPC_PYTHON_OUT]   [default: "."]
...
```

Run on `poetry update`

```toml
[tool.poetry-grpc-plugin]
```

Additional config

```toml
[tool.poetry-grpc-plugin]
proto_path = "dir/protos"
python_out = "generated/"
grpc_python_out = "generated/"
```
