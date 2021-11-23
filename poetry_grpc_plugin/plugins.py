import importlib.resources
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from cleo.events.console_command_event import ConsoleCommandEvent
from cleo.events.console_events import COMMAND
from cleo.events.event_dispatcher import EventDispatcher
from cleo.helpers import option
from grpc_tools import protoc
from poetry.console.application import Application
from poetry.console.commands.command import Command
from poetry.console.commands.update import UpdateCommand
from poetry.plugins import ApplicationPlugin
from poetry.utils.helpers import module_name


def well_known_protos_path():
    if sys.version_info >= (3, 9):

        with importlib.resources.as_file(
            importlib.resources.files("grpc_tools") / "_proto"
        ) as path:
            return str(path)
    else:
        import pkg_resources

        return pkg_resources.resource_filename("grpc_tools", "_proto")


def run_protoc(proto_path: str = ".", python_out: str = ".", **kwargs: str) -> int:
    # mypy-protobuf plugin is installed inside Poetry's virtualenv, needs to be in PATH
    if sys.executable:
        venv_dir = str(Path(sys.executable).parent.absolute())
        path = os.getenv("PATH", "")
        if path and venv_dir not in path:
            os.environ["PATH"] = f"{path}:{venv_dir}"

    inclusion_root = Path(proto_path).resolve(strict=True)
    proto_files = [str(f.resolve()) for f in inclusion_root.rglob("*.proto")]

    config = kwargs.copy()
    config["proto_path"] = str(inclusion_root)
    config["grpc_out"] = kwargs.get("grpc_out", python_out)
    config["mypy_out"] = kwargs.get("mypy_out", python_out)
    config["mypy_grpc_out"] = kwargs.get("mypy_grpc_out", config["grpc_out"])

    args = [f"--{key}={value}" for key, value in config.items()]

    command = (
        ["grpc_tools.protoc", f"--proto_path={well_known_protos_path()}"]
        + args
        + proto_files
    )
    return protoc.main(command)


class ProtocCommand(Command):
    name = "protoc"

    options = [
        option(arg, default=".", value_required=False, flag=False)
        for arg in [
            "proto_path",
            "python_out",
            "grpc_python_out",
            "mypy_out",
            "mypy_grpc_out",
        ]
    ]

    def handle(self) -> int:
        return run_protoc(**{o.name: self.option(o.name) for o in self.options})


class GrpcApplicationPlugin(ApplicationPlugin):
    _poetry_protoc_config: Optional[Dict[str, str]] = None

    @property
    def poetry_protoc_config(self) -> Optional[Dict[str, str]]:
        return self._poetry_protoc_config

    @poetry_protoc_config.setter
    def poetry_protoc_config(self, value: Dict[str, str]) -> None:
        self._poetry_protoc_config = value

    def activate(self, application: Application) -> None:
        poetry = application.poetry
        tool_data: Dict[str, Any] = poetry.pyproject.data.get("tool", {})

        if "poetry-grpc-plugin" in tool_data:
            application.event_dispatcher.add_listener(COMMAND, self.run_protoc)

        config = tool_data.get("poetry-grpc-plugin", {})
        if "python_out" not in config:
            config["python_out"] = module_name(poetry.package.name)
        self.poetry_protoc_config = config

        application.command_loader.register_factory(
            ProtocCommand.name, lambda: ProtocCommand()
        )

    def run_protoc(
        self, event: ConsoleCommandEvent, event_name: str, dispatcher: EventDispatcher
    ) -> None:

        if (
            not isinstance(event.command, UpdateCommand)
            or not self.poetry_protoc_config
        ):
            return

        if run_protoc(**self.poetry_protoc_config) != 0:
            raise Exception("Error: {} failed".format(event.command))
