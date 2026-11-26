
#!/usr/bin/env python3

import json
import os
import subprocess
import sys
from pathlib import Path


WORKSPACE = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
SDK_WORKSPACE = Path("/tmp/ncs")
PRESET_NAME = "release"

PRESETS_FILE = WORKSPACE / "CMakePresets.json"


def export_build_dir(build_dir: Path):
    """Make the selected build directory available to later GitHub steps."""
    github_env = os.environ.get("GITHUB_ENV")

    if github_env:
        with open(github_env, "a") as f:
            f.write(f"BUILD_DIR={build_dir}\n")


def build_with_preset():
    print(f"Found {PRESETS_FILE}")

    with PRESETS_FILE.open() as f:
        presets = json.load(f)

    preset = next(
        (
            p for p in presets.get("configurePresets", [])
            if p.get("name") == PRESET_NAME
        ),
        None,
    )

    if preset is None:
        raise RuntimeError(
            f"CMake configure preset '{PRESET_NAME}' was not found"
        )

    binary_dir = preset.get("binaryDir")

    if not binary_dir:
        raise RuntimeError(
            f"Preset '{PRESET_NAME}' does not define binaryDir"
        )

    # Resolve the common CMake preset variables.
    binary_dir = binary_dir.replace(
        "${sourceDir}", str(WORKSPACE)
    )
    binary_dir = binary_dir.replace(
        "${sourceDirName}", WORKSPACE.name
    )

    build_dir = Path(binary_dir)

    if not build_dir.is_absolute():
        build_dir = WORKSPACE / build_dir

    build_dir = build_dir.resolve()

    cache_variables = preset.get("cacheVariables", {})

    board = cache_variables.get("BOARD")

    if isinstance(board, dict):
        board = board.get("value")

    if not board:
        raise RuntimeError(
            f"Preset '{PRESET_NAME}' does not define BOARD"
        )

    cmake_args = []

    for name, value in cache_variables.items():

        # CMake supports typed cache variable objects.
        if isinstance(value, dict):
            value = value.get("value")

        if isinstance(value, bool):
            value = "ON" if value else "OFF"

        # BOARD is passed through west's -b option.
        if name == "BOARD":
            continue

        cmake_args.append(f"-D{name}={value}")

    command = [
        "west",
        "build",
        "-p",
        "always",
        "-b",
        str(board),
        "-s",
        str(WORKSPACE),
        "-d",
        str(build_dir),
        "--",
        *cmake_args,
    ]

    print(f"Using CMake preset: {PRESET_NAME}")
    print(f"Board: {board}")
    print(f"Build directory: {build_dir}")
    print("Command:", " ".join(command))

    export_build_dir(build_dir)

    subprocess.run(
        command,
        cwd=SDK_WORKSPACE,
        check=True,
    )


def build_without_preset():
    """Fallback to the original NCS build configuration."""

    build_dir = WORKSPACE / "build"

    command = [
        "west",
        "build",
        "-p",
        "always",
        "-b",
        os.environ["BOARD"],
        "-s",
        str(WORKSPACE),
        "-d",
        str(build_dir),
        "--",
        "-DNCS_TOOLCHAIN_VERSION=NONE",
        "-DDEBUG_THREAD_INFO=On",
        "-DCONFIG_DEBUG_THREAD_INFO=y",
        "-Dnrf52840-ci_DEBUG_THREAD_INFO=On",
    ]

    print("CMakePresets.json not found.")
    print("Using the default west build configuration.")
    print(f"Build directory: {build_dir}")

    export_build_dir(build_dir)

    subprocess.run(
        command,
        cwd=SDK_WORKSPACE,
        check=True,
    )


if __name__ == "__main__":

    if PRESETS_FILE.is_file():
        build_with_preset()
    else:
        build_without_preset()
