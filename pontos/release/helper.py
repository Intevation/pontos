# Copyright (C) 2020-2022 Greenbone Networks GmbH
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional, Tuple

from packaging.version import InvalidVersion, Version

from pontos import version
from pontos.git.git import Git
from pontos.terminal import Terminal
from pontos.version import CMakeVersionCommand, PythonVersionCommand
from pontos.version.helper import VersionError

DEFAULT_TIMEOUT = 1000
DEFAULT_CHUNK_SIZE = 4096


def commit_files(
    filename: str,
    commit_msg: str,
    shell_cmd_runner: Callable,
    *,
    git_signing_key: str = "",
    changelog: bool = False,
):
    """Add files to staged and commit staged files.

    filename: The filename of file to add and commit
    commit_msg: The commit message for the commit
    shell_cmd_runner: The runner for shell commands
    git_signing_key: The signing key to sign this commit

    Arguments:
        to: The version (str) that will be set
        develop: Wether to set version to develop or not (bool)

    Returns:
       executed: True if successfully executed, False else
       filename: The filename of the project definition
    """

    shell_cmd_runner(f"git add {filename}")
    shell_cmd_runner("git add *__version__.py || echo 'ignoring __version__'")
    if changelog:
        shell_cmd_runner("git add CHANGELOG.md")
    if git_signing_key:
        shell_cmd_runner(
            f"git commit -S{git_signing_key} --no-verify -m '{commit_msg}'",
        )
    else:
        shell_cmd_runner(f"git commit --no-verify -m '{commit_msg}'")


def calculate_calendar_version(terminal: Terminal) -> str:
    """find the correct next calendar version by checking latest version and
    the today's date"""

    current_version_str: str = get_current_version(terminal)
    current_version = Version(current_version_str)

    today = datetime.date.today()

    if (
        current_version.major < today.year % 100
        or current_version.minor < today.month
    ):
        release_version = Version(
            f"{str(today.year  % 100)}.{str(today.month)}.0"
        )
        return str(release_version)
    elif (
        current_version.major == today.year % 100
        and current_version.minor == today.month
    ):
        if current_version.dev is None:
            release_version = Version(
                f"{str(today.year  % 100)}.{str(today.month)}."
                f"{str(current_version.micro + 1)}"
            )
        else:
            release_version = Version(
                f"{str(today.year  % 100)}.{str(today.month)}."
                f"{str(current_version.micro)}"
            )
        return str(release_version)
    else:
        terminal.error(
            f"'{str(current_version)}' is higher than "
            f"'{str(today.year  % 100)}.{str(today.month)}'."
        )
        sys.exit(1)


def get_current_version(terminal: Terminal) -> str:
    """Get the current Version from a pyproject.toml or
    a CMakeLists.txt file"""

    available_cmds = [
        ("CMakeLists.txt", CMakeVersionCommand),
        ("pyproject.toml", PythonVersionCommand),
    ]
    for file_name, cmd in available_cmds:
        project_definition_path = Path.cwd() / file_name
        if project_definition_path.exists():
            terminal.ok(f"Found {file_name} project definition file.")
            current_version: str = cmd().get_current_version()
            return current_version

    terminal.error("No project settings file found")
    sys.exit(1)


def get_last_release_version() -> Optional[str]:
    """Get the last released Version from git.

    Returns:
        Last released git-tag if tags were found
        or None
    """

    git_interface = Git()
    tag_list = git_interface.list_tags()
    return tag_list[-1] if tag_list else None


def get_next_patch_version(terminal: Terminal) -> str:
    """find the correct next patch version by checking latest version"""

    current_version_str: str = get_current_version(terminal)
    current_version = Version(current_version_str)

    if current_version.dev is not None:
        release_version = Version(
            f"{str(current_version.major)}."
            f"{str(current_version.minor)}."
            f"{str(current_version.micro)}"
        )
    else:
        release_version = Version(
            f"{str(current_version.major)}."
            f"{str(current_version.minor)}."
            f"{str(current_version.micro + 1)}"
        )

    return str(release_version)


def get_next_dev_version(release_version: str) -> str:
    """Get the next dev Version from a valid version"""
    # will be a dev1 version
    try:
        release_version_obj = Version(release_version)
        next_version_obj = Version(
            f"{str(release_version_obj.major)}."
            f"{str(release_version_obj.minor)}."
            f"{str(release_version_obj.micro + 1)}"
        )
        return str(next_version_obj)
    except InvalidVersion as e:
        raise (VersionError(e)) from None


def get_project_name(
    shell_cmd_runner: Callable,
    *,
    remote: str = "origin",
) -> str:
    """Get the git repository name

    Arguments:
        shell_cmd_runner: The runner for shell commands
        remote: the remote to look up the name (str) default: origin

    Returns:
        project name
    """
    ret = shell_cmd_runner(f"git remote get-url {remote}")
    return ret.stdout.split("/")[-1].replace(".git", "").strip()


def find_signing_key(terminal: Terminal, shell_cmd_runner: Callable) -> str:
    """Find the signing key in the config

    Arguments:
        shell_cmd_runner: The runner for shell commands

    Returns:
        git signing key or empty string
    """

    try:
        proc = shell_cmd_runner("git config user.signingkey")
    except subprocess.CalledProcessError as e:
        # The command `git config user.signingkey` returns
        # return code 1 if no key is set.
        # So we will return empty string ...
        if e.returncode == 1:
            terminal.warning("No signing key found.")
        return ""
    # stdout should return "\n" if no key is available
    # and so git_signing_key should
    # return '' if no key is available ...
    return proc.stdout.strip()


def update_version(
    terminal: Terminal, to: str, *, develop: bool = False
) -> Tuple[bool, str]:
    """Use pontos-version to update the version.

    Arguments:
        to: The version (str) that will be set
        develop: Wether to set version to develop or not (bool)

    Returns:
       executed: True if successfully executed, False else
       filename: The filename of the project definition
    """
    args = ["--quiet"]
    args.append("update")
    args.append(to)
    if develop:
        args.append("--develop")
    executed, filename = version.main(leave=False, args=args)

    if not executed:
        if filename == "":
            terminal.error("No project definition found.")
        else:
            terminal.error(f"Unable to update version {to} in {filename}")

    return executed, filename
