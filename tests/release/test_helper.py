# -*- coding: utf-8 -*-
# Copyright (C) 2021-2022 Greenbone Networks GmbH
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

import contextlib
import datetime
import subprocess
import unittest
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

from pontos.git.git import Git, exec_git
from pontos.release.helper import (
    calculate_calendar_version,
    find_signing_key,
    get_last_release_version,
    get_next_dev_version,
    get_next_patch_version,
    get_project_name,
    update_version,
)
from pontos.testing import temp_directory, temp_git_repository


@contextlib.contextmanager
def init_test_git_repo() -> Generator[Path, None, None]:
    with temp_git_repository() as repo_path:
        exec_git("remote", "add", "foo", "https://foo.bar/bla.git")
        exec_git("remote", "add", "origin", "https://foo.bar/testrepo.git")
        yield repo_path


class TestHelperFunctions(unittest.TestCase):
    def setUp(self):
        self.shell_cmd_runner = lambda x, cwd=None: subprocess.run(
            x,
            shell=True,
            check=True,
            errors="utf-8",  # use utf-8 encoding for error output
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
        )

    def test_get_project_name(self):
        with init_test_git_repo():
            project = get_project_name(
                shell_cmd_runner=self.shell_cmd_runner, remote="foo"
            )
            self.assertEqual(project, "bla")

            project = get_project_name(shell_cmd_runner=self.shell_cmd_runner)
            self.assertEqual(project, "testrepo")

    def test_find_signing_key(self):
        terminal = MagicMock()

        with temp_git_repository():
            self.shell_cmd_runner(
                "git config user.signingkey "
                "1234567890ABCEDEF1234567890ABCEDEF123456"
            )

            signing_key = find_signing_key(
                terminal, shell_cmd_runner=self.shell_cmd_runner
            )
            self.assertEqual(
                signing_key, "1234567890ABCEDEF1234567890ABCEDEF123456"
            )

    def test_find_no_signing_key(self):
        terminal = MagicMock()
        saved_key = None

        try:
            # save possibly set git signing key from user temporarily
            try:
                saved_key = self.shell_cmd_runner(
                    "git config --global user.signingkey",
                    cwd=Path.home(),
                ).stdout.strip()
            except subprocess.CalledProcessError:
                saved_key = None

            try:
                self.shell_cmd_runner(
                    "git config --global --unset user.signingkey",
                    cwd=Path.home(),
                )
            except subprocess.CalledProcessError as e:
                self.assertEqual(e.returncode, 5)

            with temp_git_repository():
                signing_key = find_signing_key(
                    terminal, shell_cmd_runner=self.shell_cmd_runner
                )
                self.assertEqual(signing_key, "")

        finally:
            # reset the previously saved signing key ...
            if saved_key is not None:
                self.shell_cmd_runner(
                    f'git config --global user.signingkey "{saved_key}"',
                    cwd=Path.home(),
                )

    def test_update_version_not_found(self):
        terminal = MagicMock()

        with temp_directory(change_into=True):
            executed, filename = update_version(
                terminal, to="21.4.4", develop=True
            )

        self.assertFalse(executed)
        self.assertEqual(filename, "")

    def test_update_version_no_version_file(self):
        terminal = MagicMock()

        with temp_directory(change_into=True, add_to_sys_path=True) as tmp_dir:
            module_path = tmp_dir / "testrepo"
            module_path.mkdir(parents=True, exist_ok=True)

            init_file = module_path / "__init__.py"
            init_file.touch()

            version_file = module_path / "__version__.py"

            toml = tmp_dir / "pyproject.toml"
            toml.write_text(
                "[tool.poetry]\n"
                'name = "testrepo"\n'
                'version = "21.6.2.dev1"\n\n'
                "[tool.pontos.version]\n"
                'version-module-file = "testrepo/__version__.py"\n',
                encoding="utf-8",
            )

            executed, filename = update_version(
                terminal, to="21.4.4", develop=False
            )

            toml_text = toml.read_text(encoding="utf-8")

            self.assertEqual(filename, "pyproject.toml")
            self.assertTrue(executed)
            self.assertEqual(
                toml_text,
                "[tool.poetry]\n"
                'name = "testrepo"\n'
                'version = "21.4.4"\n\n'
                "[tool.pontos.version]\n"
                'version-module-file = "testrepo/__version__.py"\n',
            )
            self.assertTrue(version_file.exists())
            version_text = version_file.read_text(encoding="utf-8")
            self.assertEqual(
                version_text,
                "# pylint: disable=invalid-name\n\n"
                "# THIS IS AN AUTOGENERATED FILE. DO NOT TOUCH!\n\n"
                '__version__ = "21.4.4"\n',
            )

    @patch("pontos.release.helper.Git", spec=Git)
    def test_get_last_release_version_git(self, _git_interface_mock):
        git_interface = _git_interface_mock.return_value
        git_interface.list_tags.return_value = ["1", "2", "3.55"]
        self.assertEqual(get_last_release_version(), "3.55")

    @patch("pontos.release.helper.Git", spec=Git)
    def test_get_no_release_version_git(self, _git_interface_mock):
        git_interface = _git_interface_mock.return_value
        git_interface.list_tags.return_value = []
        self.assertIsNone(get_last_release_version())


class CalculateHelperVersionTestCase(unittest.TestCase):
    def test_calculate_calendar_versions(self):
        terminal = MagicMock()
        today = datetime.datetime.today()

        filenames = ["pyproject.toml", "CMakeLists.txt"]
        mocks = [
            "pontos.release.helper.PythonVersionCommand",
            "pontos.release.helper.CMakeVersionCommand",
        ]
        current_versions = [
            "21.4.1.dev3",
            f"19.{str(today.month)}.1.dev3",
            f"{str(today.year % 100)}.{str(today.month)}.1.dev3",
            f"{str(today.year % 100)}.{str(today.month)}.1",
        ]
        assert_versions = [
            f"{str(today.year % 100)}.{str(today.month)}.0",
            f"{str(today.year % 100)}.{str(today.month)}.0",
            f"{str(today.year % 100)}.{str(today.month)}.1",
            f"{str(today.year % 100)}.{str(today.month)}.2",
        ]

        with temp_directory(change_into=True) as tmp_path:
            for filename, mock in zip(filenames, mocks):
                for current_version, assert_version in zip(
                    current_versions, assert_versions
                ):
                    proj_file = tmp_path / filename
                    proj_file.touch()
                    with patch(mock) as cmd_mock:
                        # pylint: disable=line-too-long
                        cmd_mock.return_value.get_current_version.return_value = (
                            current_version
                        )

                        release_version = calculate_calendar_version(terminal)
                        self.assertEqual(release_version, assert_version)

                    proj_file.unlink()

    def test_get_next_dev_version(self):
        current_versions = [
            "20.4.1",
            "20.4.1",
            "19.1.2",
            "1.1.1",
            "20.6.1",
        ]
        assert_versions = [
            "20.4.2",
            "20.4.2",
            "19.1.3",
            "1.1.2",
            "20.6.2",
        ]

        for current_version, assert_version in zip(
            current_versions, assert_versions
        ):
            next_version = get_next_dev_version(current_version)

            self.assertEqual(assert_version, next_version)

    def test_get_next_patch_version(self):
        terminal = MagicMock()
        today = datetime.datetime.today()

        filenames = ["pyproject.toml", "CMakeLists.txt"]
        mocks = [
            "pontos.release.helper.PythonVersionCommand",
            "pontos.release.helper.CMakeVersionCommand",
        ]
        current_versions = [
            "20.4.1.dev3",
            f"{str(today.year % 100)}.4.1.dev3",
            f"19.{str(today.month)}.1.dev3",
            f"{str(today.year % 100)}.{str(today.month)}.1",
            "20.6.1",
        ]
        assert_versions = [
            "20.4.1",
            f"{str(today.year % 100)}.4.1",
            f"19.{str(today.month)}.1",
            f"{str(today.year % 100)}.{str(today.month)}.2",
            "20.6.2",
        ]

        with temp_directory(change_into=True) as tmp_path:
            for filename, mock in zip(filenames, mocks):
                for current_version, assert_version in zip(
                    current_versions, assert_versions
                ):
                    proj_file = tmp_path / filename
                    proj_file.touch()
                    with patch(mock) as cmd_mock:
                        # pylint: disable=line-too-long
                        cmd_mock.return_value.get_current_version.return_value = (
                            current_version
                        )

                        release_version = get_next_patch_version(terminal)

                        self.assertEqual(release_version, assert_version)

                    proj_file.unlink()
