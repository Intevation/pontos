# Copyright (C) 2020-2021 Greenbone Networks GmbH
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

import importlib

from pathlib import Path
from typing import Union

import tomlkit

from .helper import (
    safe_version,
    check_develop,
    is_version_pep440_compliant,
    VersionError,
    initialize_default_parser,
)


def strip_version(version: str) -> str:
    """
    Strips a leading 'v' from a version string

    E.g. v1.2.3 will be converted to 1.2.3
    """
    if version and version[0] == 'v':
        return version[1:]

    return version


def get_version_from_pyproject_toml(pyproject_toml_path: Path = None) -> str:
    """
    Return the version information from the [tool.poetry] section of the
    pyproject.toml file. The version may be in non standardized form.
    """
    if not pyproject_toml_path:
        path = Path(__file__)
        pyproject_toml_path = path.parent.parent / 'pyproject.toml'

    if not pyproject_toml_path.exists():
        raise VersionError(f'{str(pyproject_toml_path)} file not found.')

    pyproject_toml = tomlkit.parse(
        pyproject_toml_path.read_text(encoding='utf-8')
    )
    if (
        'tool' in pyproject_toml
        and 'poetry' in pyproject_toml['tool']
        and 'version' in pyproject_toml['tool']['poetry']
    ):
        return pyproject_toml['tool']['poetry']['version']

    raise VersionError(
        f'Version information not found in {str(pyproject_toml_path)} file.'
    )


def versions_equal(new_version: str, old_version: str) -> bool:
    """
    Checks if new_version and old_version are equal
    """
    return safe_version(old_version) == safe_version(new_version)


class VersionCommand:
    TEMPLATE = """# pylint: disable=invalid-name

# THIS IS AN AUTOGENERATED FILE. DO NOT TOUCH!

__version__ = "{}"\n"""

    __quiet = False

    def __init__(
        self,
        *,
        version_file_path: Path = None,
        pyproject_toml_path: Path = None
    ):
        self.version_file_path = version_file_path

        self.pyproject_toml_path = pyproject_toml_path

        self._configure_parser()

    def _configure_parser(self):
        self.parser = initialize_default_parser()

    def _print(self, *args) -> None:
        if not self.__quiet:
            print(*args)

    def get_current_version(self) -> str:
        version_module_name = self.version_file_path.stem
        module_parts = list(self.version_file_path.parts[:-1]) + [
            version_module_name
        ]
        module_name = '.'.join(module_parts)
        try:
            version_module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            raise VersionError(
                f'Could not load version from {module_name}. Import failed.'
            ) from None

        return version_module.__version__

    def _update_version_file(self, new_version: str) -> None:
        """
        Update the version file with the new version
        """
        new_version = safe_version(new_version)
        self.version_file_path.write_text(
            self.TEMPLATE.format(new_version), encoding='utf-8'
        )

    def _update_pyproject_version(
        self,
        new_version: str,
    ) -> None:
        """
        Update the version in the pyproject.toml file
        """

        new_version = safe_version(new_version)
        pyproject_toml = tomlkit.parse(
            self.pyproject_toml_path.read_text(encoding='utf-8')
        )

        if 'tool' not in pyproject_toml:
            tool_table = tomlkit.table()
            pyproject_toml['tool'] = tool_table

        if 'poetry' not in pyproject_toml['tool']:
            poetry_table = tomlkit.table()
            pyproject_toml['tool'].add('poetry', poetry_table)

        pyproject_toml['tool']['poetry']['version'] = new_version

        self.pyproject_toml_path.write_text(
            tomlkit.dumps(pyproject_toml), encoding='utf-8'
        )

    def update_version(
        self, new_version: str, *, develop: bool = False, force: bool = False
    ) -> None:

        new_version = safe_version(new_version)
        if check_develop(new_version) and develop:
            develop = False
        if develop:
            new_version = f'{new_version}.dev1'

        pyproject_version = get_version_from_pyproject_toml(
            pyproject_toml_path=self.pyproject_toml_path
        )

        if not self.version_file_path.exists():
            self.version_file_path.touch()

        elif not force and versions_equal(
            new_version, self.get_current_version()
        ):
            self._print('Version is already up-to-date.')
            return

        self._update_pyproject_version(new_version=new_version)

        self._update_version_file(new_version=new_version)

        self._print(
            f'Updated version from {pyproject_version} to {new_version}'
        )

    def verify_version(self, version: str) -> None:
        current_version = self.get_current_version()
        if not is_version_pep440_compliant(current_version):
            raise VersionError(
                f"The version {current_version} in "
                f"{str(self.version_file_path)} is not PEP 440 compliant."
            )

        pyproject_version = get_version_from_pyproject_toml(
            pyproject_toml_path=self.pyproject_toml_path
        )

        if pyproject_version != current_version:
            raise VersionError(
                f"The version {pyproject_version} in "
                f"{str(self.pyproject_toml_path)} doesn't match the current "
                f"version {current_version}."
            )

        if version != 'current':
            provided_version = strip_version(version)
            if provided_version != current_version:
                raise VersionError(
                    f"Provided version {provided_version} does not match the "
                    f"current version {current_version}."
                )

        self._print('OK')

    def print_current_version(self) -> None:
        self._print(self.get_current_version())

    def run(self, args=None) -> Union[int, str]:
        args = self.parser.parse_args(args)

        if not getattr(args, 'command', None):
            self.parser.print_usage()
            return 0

        self.__quiet = args.quiet

        if not self.pyproject_toml_path.exists():
            raise VersionError(
                f'Could not find {str(self.pyproject_toml_path)} file.'
            )

        try:
            if args.command == 'update':
                self.update_version(
                    args.version, force=args.force, develop=args.develop
                )
            elif args.command == 'show':
                self.print_current_version()
            elif args.command == 'verify':
                self.verify_version(args.version)
        except VersionError as e:
            return str(e)

        return 0


class PontosVersionCommand(VersionCommand):
    def __init__(self, *, pyproject_toml_path=None):
        if not pyproject_toml_path:
            pyproject_toml_path = Path.cwd() / 'pyproject.toml'

        if not pyproject_toml_path.exists():
            raise VersionError(f'{str(pyproject_toml_path)} file not found.')

        pyproject_toml = tomlkit.parse(
            pyproject_toml_path.read_text(encoding='utf-8')
        )

        if (
            'tool' not in pyproject_toml
            or 'pontos' not in pyproject_toml['tool']
            or 'version' not in pyproject_toml['tool']['pontos']
        ):
            raise VersionError(
                '[tool.pontos.version] section missing '
                f'in {str(pyproject_toml_path)}.'
            )

        pontos_version_settings = pyproject_toml['tool']['pontos']['version']

        try:
            version_file_path = Path(
                pontos_version_settings['version-module-file']
            )
        except tomlkit.exceptions.NonExistentKey:
            raise VersionError(
                'version-module-file key not set in [tool.pontos.version] '
                f'section of {str(pyproject_toml_path)}.'
            ) from None

        super().__init__(
            version_file_path=version_file_path,
            pyproject_toml_path=pyproject_toml_path,
        )
