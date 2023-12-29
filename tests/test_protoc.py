import os
import sys
import tempfile
from pathlib import Path
from shutil import copy
from typing import cast

from cleo.io.buffered_io import BufferedIO
from cleo.io.inputs.string_input import StringInput
from cleo.io.outputs.buffered_output import BufferedOutput
from cleo.io.outputs.output import Verbosity
from poetry.console.application import Application
from poetry.console.commands.env_command import EnvCommand
from poetry.factory import Factory
from poetry.utils.env import EnvManager

from poetry_grpc_plugin.plugins import GrpcApplicationPlugin

pyproject = b"""
[tool.poetry]
name = "project"
version = "0.1.0"
description = ""
authors = ["noone"]
readme = "README.md"

[tool.poetry.dependencies]
python = "^3.8"

[tool.poetry-grpc-plugin]
proto_path = "protos"
python_out = "src"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
"""


def test_update() -> None:
    cwd = Path.cwd()
    with tempfile.TemporaryDirectory(
        ignore_cleanup_errors=True, prefix=f"test_update{sys.version_info.minor}"
    ) as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        os.mkdir(temp_dir / "protos")
        copy(cwd / "tests" / "demo.proto", temp_dir / "protos" / "demo.proto")
        os.chdir(temp_dir)
        with Path(temp_dir, "pyproject.toml").open("w+b") as temp_pyproject:
            temp_pyproject.writelines([line + b"\n" for line in pyproject.split(b"\n")])
            temp_pyproject.flush()
        application = Application()
        application.auto_exits(False)
        output = BufferedOutput()
        result = application.run(StringInput("update"), output)
        assert result == 0, output.fetch()
        assert Path(temp_dir, "src", "demo_pb2_grpc.py").exists()
        assert Path(temp_dir, "src", "demo_pb2_grpc.pyi").exists()
        assert Path(temp_dir, "src", "demo_pb2.py").exists()
        assert Path(temp_dir, "src", "demo_pb2.pyi").exists()
        os.chdir(cwd)


def test_protoc() -> None:
    cwd = Path.cwd()
    with tempfile.TemporaryDirectory(
        ignore_cleanup_errors=True, prefix=f"test_protoc{sys.version_info.minor}"
    ) as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        with Path(temp_dir, "pyproject.toml").open("w+b") as temp_pyproject:
            temp_pyproject.writelines([line + b"\n" for line in pyproject.split(b"\n")])
            temp_pyproject.flush()
        os.mkdir(temp_dir / "protos")
        copy(cwd / "tests" / "demo.proto", temp_dir / "protos" / "demo.proto")
        os.chdir(temp_dir)
        poetry = Factory().create_poetry(temp_dir)
        plugin = GrpcApplicationPlugin()
        plugin.activate(Application())
        assert plugin.application
        command = cast(EnvCommand, plugin.application.command_loader.get("protoc"))
        command.set_env(EnvManager(poetry).create_venv("unit-test"))
        io = BufferedIO()
        io.set_verbosity(Verbosity.DEBUG)
        io.input.bind(command.definition)
        io.input.set_option("proto_path", "protos")
        io.input.set_option("python_out", "src")
        result = command.execute(io)
        assert result == 0, io.fetch_output()
        assert Path(temp_dir, "src", "demo_pb2_grpc.py").exists()
        assert Path(temp_dir, "src", "demo_pb2_grpc.pyi").exists()
        assert Path(temp_dir, "src", "demo_pb2.py").exists()
        assert Path(temp_dir, "src", "demo_pb2.pyi").exists()
        os.chdir(cwd)
