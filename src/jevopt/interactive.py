from __future__ import annotations

import ctypes
import errno
import io
import json
import math
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Callable, Sequence

_ELEMENT_TYPES: dict[str, type[ctypes._SimpleCData]] = {
    "float": ctypes.c_float,
    "double": ctypes.c_double,
    "int8_t": ctypes.c_int8,
    "uint8_t": ctypes.c_uint8,
    "int16_t": ctypes.c_int16,
    "uint16_t": ctypes.c_uint16,
    "int32_t": ctypes.c_int32,
    "uint32_t": ctypes.c_uint32,
    "int64_t": ctypes.c_int64,
    "uint64_t": ctypes.c_uint64,
}


@dataclass(frozen=True)
class TensorSpec:
    name: str
    shape: tuple[int, ...]
    element_type: type[ctypes._SimpleCData]

    @classmethod
    def from_json(cls, value: dict[str, object]) -> TensorSpec:
        type_name = str(value["type"])
        return cls(
            name=str(value["name"]),
            shape=tuple(int(item) for item in value["shape"]),  # type: ignore[union-attr]
            element_type=_ELEMENT_TYPES[type_name],
        )


def _read_tensor(stream: IO[bytes], spec: TensorSpec) -> list[int | float]:
    count = math.prod(spec.shape)
    size = count * ctypes.sizeof(spec.element_type)
    data = stream.read(size)
    if len(data) != size:
        raise EOFError(f"short tensor {spec.name}: expected {size}, got {len(data)}")
    array_type = spec.element_type * count
    return list(array_type.from_buffer_copy(data))


def _write_scalar(stream: IO[bytes], value: float, spec: TensorSpec) -> None:
    if math.prod(spec.shape) != 1:
        raise ValueError(f"expected scalar advice, got shape {spec.shape}")
    encoded = bytes(spec.element_type(value))
    stream.write(encoded)
    stream.flush()


def run_interactive(
    channel_base: Path,
    compiler_command: Sequence[str],
    should_inline: Callable[[dict[str, object]], bool],
) -> list[dict[str, object]]:
    """Compile while answering LLVM's discretionary inline decisions."""
    to_compiler = Path(f"{channel_base}.in")
    from_compiler = Path(f"{channel_base}.out")
    os.mkfifo(to_compiler, 0o600)
    os.mkfifo(from_compiler, 0o600)
    process: subprocess.Popen[bytes] | None = None
    observations: list[dict[str, object]] = []
    try:
        process = subprocess.Popen(
            compiler_command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        with (
            io.BufferedWriter(io.FileIO(to_compiler, "wb")) as incoming,
            io.BufferedReader(io.FileIO(from_compiler, "rb")) as outgoing,
        ):
            header = json.loads(outgoing.readline())
            feature_specs = [TensorSpec.from_json(item) for item in header["features"]]
            advice_spec = TensorSpec.from_json(header["advice"])
            context: str | None = None
            while True:
                event_line = outgoing.readline()
                if not event_line:
                    break
                event = json.loads(event_line)
                while "context" in event:
                    context = event["context"]
                    event_line = outgoing.readline()
                    if not event_line:
                        break
                    event = json.loads(event_line)
                if not event_line:
                    break
                values = {
                    spec.name: _read_tensor(outgoing, spec) for spec in feature_specs
                }
                if outgoing.readline() != b"\n":
                    raise ValueError("LLVM observation lacked its newline terminator")
                default = int(values["inlining_default"][0])
                observation: dict[str, object] = {
                    "context": context,
                    "id": int(event["observation"]),
                    "features": values,
                    "default": default,
                }
                inline = should_inline(observation)
                if not isinstance(inline, bool):
                    raise TypeError("inline decision must be bool")
                observation["decision"] = inline
                observations.append(observation)
                _write_scalar(incoming, int(inline), advice_spec)

        _, stderr = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(
                f"interactive compiler failed ({process.returncode}):\n"
                f"{stderr.decode('utf-8', errors='replace')}"
            )
        return observations
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        to_compiler.unlink(missing_ok=True)
        from_compiler.unlink(missing_ok=True)


def run_json_interactive(
    channel_base: Path,
    compiler_command: Sequence[str],
    should_inline: Callable[[dict[str, object]], bool],
) -> list[dict[str, object]]:
    """Compile while exchanging JSON observations with an advisor plugin."""
    to_compiler = Path(f"{channel_base}.in")
    from_compiler = Path(f"{channel_base}.out")
    os.mkfifo(to_compiler, 0o600)
    os.mkfifo(from_compiler, 0o600)
    process: subprocess.Popen[bytes] | None = None
    observations: list[dict[str, object]] = []
    try:
        process = subprocess.Popen(
            compiler_command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env={**os.environ, "JEVOPT_INLINE_CHANNEL_BASE": str(channel_base)},
        )
        while True:
            try:
                incoming_fd = os.open(to_compiler, os.O_WRONLY | os.O_NONBLOCK)
                break
            except OSError as error:
                if error.errno != errno.ENXIO:
                    raise
                if process.poll() is not None:
                    _, stderr = process.communicate()
                    if process.returncode != 0:
                        raise RuntimeError(
                            f"interactive compiler failed ({process.returncode}):\n"
                            f"{stderr.decode('utf-8', errors='replace')}"
                        )
                    return observations
                time.sleep(0.01)
        outgoing_fd = os.open(from_compiler, os.O_RDONLY)
        os.set_blocking(incoming_fd, True)
        with (
            io.BufferedWriter(io.FileIO(incoming_fd, "wb")) as incoming,
            io.BufferedReader(io.FileIO(outgoing_fd, "rb")) as outgoing,
        ):
            for line in outgoing:
                observation = json.loads(line)
                inline = should_inline(observation)
                if not isinstance(inline, bool):
                    raise TypeError("inline decision must be bool")
                observation["decision"] = inline
                observations.append(observation)
                incoming.write(b"1\n" if inline else b"0\n")
                incoming.flush()

        _, stderr = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(
                f"interactive compiler failed ({process.returncode}):\n"
                f"{stderr.decode('utf-8', errors='replace')}"
            )
        return observations
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        to_compiler.unlink(missing_ok=True)
        from_compiler.unlink(missing_ok=True)
