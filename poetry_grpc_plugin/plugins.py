import importlib.resources
import logging
import os
import sys
import sysconfig
from pathlib import Path
from typing import Any, Dict, List, Optional

from cleo.events.console_command_event import ConsoleCommandEvent
from cleo.events.console_events import COMMAND
from cleo.events.event import Event
from cleo.events.event_dispatcher import EventDispatcher
from cleo.helpers import option
from cleo.io.io import IO
from cleo.io.outputs.output import Verbosity
from grpc_tools import protoc
from poetry.console.application import Application
from poetry.console.commands.env_command import EnvCommand
from poetry.console.commands.update import UpdateCommand
from poetry.core.utils.helpers import module_name
from poetry.plugins.application_plugin import ApplicationPlugin

logger = logging.getLogger(__name__)


def well_known_protos_path() -> str:
    if sys.version_info >= (3, 9):
        with importlib.resources.as_file(
            importlib.resources.files("grpc_tools") / "_proto"
        ) as path:
            return str(path)
    else:
        import pkg_resources

        return pkg_resources.resource_filename("grpc_tools", "_proto")


def run_protoc(
    io: IO,
    venv_path: Path,
    proto_path: str,
    python_out: str,
    grpc_python_out: Optional[str] = None,
    mypy_out: Optional[str] = None,
    mypy_grpc_out: Optional[str] = None,
    venv_proto_paths: Optional[List[str]] = None,
) -> int:
    # mypy-protobuf plugin is installed inside Poetry's virtualenv, needs to be in PATH
    venv_bin_dir = sysconfig.get_path("scripts")
    io.write_line(
        f"<debug>Adding virtual environment bin dir '{venv_bin_dir}' to PATH</>",
        Verbosity.DEBUG,
    )
    path = os.getenv("PATH", "")
    if path and venv_bin_dir not in path:
        os.environ["PATH"] = f"{path}:{venv_bin_dir}"
    io.write_line(
        f"<debug>Modified PATH='{os.environ['PATH']}'</>",
        Verbosity.DEBUG,
    )

    inclusion_root = Path(proto_path).resolve(strict=True)
    io.write_line(f"<info>Locating protobuf files under: {inclusion_root}</>")
    proto_files = [str(f.resolve()) for f in inclusion_root.rglob("*.proto")]

    # Prune files found under .venv
    proto_files = [p for p in proto_files if not p.startswith(str(venv_path))]

    # Default paths
    grpc_python_out = grpc_python_out if grpc_python_out else python_out
    mypy_out = mypy_out if mypy_out else python_out
    mypy_grpc_out = mypy_grpc_out if mypy_grpc_out else grpc_python_out

    # Ensure output dirs exist
    for out_dir in set(
        Path(p).resolve()
        for p in (python_out, grpc_python_out, mypy_out, mypy_grpc_out)
    ):
        out_dir.mkdir(exist_ok=True, parents=True)

    args = [
        f"--{key}={value}"
        for key, value in [
            ("proto_path", str(inclusion_root)),
            ("python_out", python_out),
            ("grpc_python_out", grpc_python_out),
            ("mypy_out", f"quiet:{mypy_out}"),
            ("mypy_grpc_out", f"quiet:{mypy_grpc_out}"),
        ]
    ]

    if os.name == "nt":
        # Explicitly set the mypy plugin path in Windows
        args.append(f"--plugin=protoc-gen-mypy={venv_bin_dir}/protoc-gen-mypy.exe")
        args.append(
            f"--plugin=protoc-gen-mypy_grpc={venv_bin_dir}/protoc-gen-mypy_grpc.exe"
        )

    if venv_proto_paths and isinstance(venv_proto_paths, list):
        for venv_proto_path_str in venv_proto_paths:
            venv_proto_path = Path(sysconfig.get_path("purelib"), venv_proto_path_str)
            args.append(
                f"--proto_path={Path(sysconfig.get_path('purelib'), venv_proto_path)}"
            )

    command = (
        ["grpc_tools.protoc", f"--proto_path={well_known_protos_path()}"]
        + args
        + proto_files
    )
    io.write_line(f"<debug>Invoking protoc as: {command}</>", Verbosity.DEBUG)
    protoc_result = protoc.main(command)
    if protoc_result == 0:
        io.write_line(
            f"<info>Successfully generated python files in '{python_out}' and gRPC files in '{grpc_python_out}'</>"
        )
    return protoc_result


class ProtocCommand(EnvCommand):
    name = "protoc"

    options = [
        option(
            "proto_path",
            description="Base path for protobuf resources.",
            value_required=False,
            flag=False,
        ),
        option(
            "venv_proto_paths",
            description="Additional protobuf resources base paths, from the virtual environment.",
            value_required=False,
            flag=False,
            multiple=True,
            default=None,
        ),
        option(
            "python_out",
            description="Output path for generated protobuf wrappers.",
            value_required=False,
            flag=False,
        ),
        option(
            "grpc_python_out",
            description="Output path for generated gRPC wrappers. Defaults to same path as python_out",
            value_required=False,
            flag=False,
        ),
        option(
            "mypy_out",
            description="Output path for mypy type information for generated protobuf wrappers. Defaults to same path as python_out.",
            value_required=False,
            flag=False,
        ),
        option(
            "mypy_grpc_out",
            description="Output path for mypy type information for generated gRPC wrappers. Defaults to same path as grpc_python_out.",
            value_required=False,
            flag=False,
        ),
    ]

    def __init__(self, config: Dict[str, str]) -> None:
        super().__init__()
        self.config = config
        for o in self.options:
            if o.name in config:
                o.set_default(config[o.name])

    def handle(self) -> int:
        args = {o.name: self.option(o.name) for o in self.options}
        args = {name: value for name, value in args.items() if value is not None}
        return run_protoc(self.io, self.env.path, **args)


class GrpcApplicationPlugin(ApplicationPlugin):
    _application: Application

    @property
    def application(self) -> Optional[Application]:
        return self._application

    @application.setter
    def application(self, value: Application) -> None:
        self._application = value

    def activate(self, application: Application) -> None:
        self.application = application
        application.command_loader.register_factory(
            ProtocCommand.name, lambda: ProtocCommand(self.load_config() or {})
        )
        if application.event_dispatcher:
            application.event_dispatcher.add_listener(COMMAND, self.run_protoc)
            logger.debug("Added protoc 'update' listener")
        else:
            logger.warning(
                "Not adding 'update' listener, application.event_dispatched is missing"
            )

    def load_config(self) -> Optional[Dict[str, str]]:
        poetry = self._application.poetry
        tool_data: Dict[str, Any] = poetry.pyproject.data.get("tool", {})

        config = tool_data.get("poetry-grpc-plugin")
        if config is None:
            return None
        if "python_out" not in config:
            config["python_out"] = module_name(poetry.package.name)
        if "proto_path" not in config:
            config["proto_path"] = "."
        return config

    def run_protoc(
        self, event: Event, event_name: str, dispatcher: EventDispatcher
    ) -> None:
        if (
            not isinstance(event, ConsoleCommandEvent)
            or not isinstance(event.command, UpdateCommand)
            or not self.application
        ):
            return
        config = self.load_config()

        if config is None:
            event.io.write_line(
                "<debug>Skipped update, [tool.poetry-grpc-plugin] or pyproject.toml missing.</>",
                Verbosity.DEBUG,
            )
            return
        if run_protoc(event.io, event.command.env.path, **config) != 0:
            raise Exception("Error: {} failed".format(event.command))
