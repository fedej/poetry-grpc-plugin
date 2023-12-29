# Poetry gRPC plugin

A [**Poetry**](https://python-poetry.org/) plugin to run the Protocol Buffers compiler with gRPC support.

### Installing the plugin

Requires Poetry version `1.2.0` or above

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
      --proto_path[=PROTO_PATH]             Base path for protobuf resources. [default: "<module_name>"]
      --python_out[=PYTHON_OUT]             Output path for generated protobuf wrappers. [default: "."]
      --grpc_python_out[=GRPC_PYTHON_OUT]   Output path for generated gRPC wrappers. Defaults to same path as python_out.
      --mypy_out[=MYPY_OUT]                 Output path for mypy type information for generated protobuf wrappers. Defaults to same path as python_out.
      --mypy_grpc_out[=MYPY_GRPC_OUT]       Output path for mypy type information for generated gRPC wrappers. Defaults to same path as grpc_python_out.
      --venv_proto_paths[=VENV_PROTO_PATHS] Additional protobuf resources paths, from the plugin's venv. Defaults to None.
      ...
```

Run on `poetry update`

```toml
[tool.poetry-grpc-plugin]
```

Additional config

```toml
[tool.poetry-grpc-plugin]
proto_path = "protos"               # Defaults to module name
python_out = "."                    # Defaults to .
venv_proto_paths = ["google/type"]  # Defaults to None
```
Settings in `pyproject.toml` will be used as defaults for manual execution with `poetry protoc`.

Using `venv_proto_paths`, one can import additional protos from packages installed in the same virtual environment as this plugin. For example:
```bash
pipx inject poetry googleapis-common-protos
```
```toml
[tool.poetry-grpc-plugin]
...
venv_proto_paths = ["google/type"]  # Defaults to None
```
Then in your proto file you can do: 
```protobuf
import "latlng.proto";
```