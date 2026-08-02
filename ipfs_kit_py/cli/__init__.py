"""Registry-derived command-line adapter exports."""

from .operation_adapter import (
    CLI_ADAPTER_SCHEMA,
    CLI_TRANSPORT,
    CLIAdapter,
    CLIAdapter_V1,
    CLICommand,
    CLI_COMMAND_SCHEMA,
    CLIInputError,
    DEFAULT_PROGRAM_NAME,
    build_cli_adapter,
)

__all__ = [
    "CLI_ADAPTER_SCHEMA",
    "CLI_TRANSPORT",
    "CLIAdapter",
    "CLIAdapter_V1",
    "CLICommand",
    "CLI_COMMAND_SCHEMA",
    "CLIInputError",
    "DEFAULT_PROGRAM_NAME",
    "build_cli_adapter",
]
