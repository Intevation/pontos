# Copyright (C) 2022 Greenbone Networks GmbH
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

""" Argument parser for pontos-github """

from argparse import ArgumentParser, Namespace
import os
from typing import List


def from_env(name: str) -> str:
    if name in os.environ:
        return os.environ[name]
    else:
        return name


def parse_args(
    args: List[str] = None,
) -> Namespace:
    """Parsing args for nasl-lint

    Arguments:
    args        The programm arguments passed by exec
    term        The terminal to print"""

    parser = ArgumentParser(
        description="Greenbone GitHub API.",
    )

    subparsers = parser.add_subparsers(
        title='subcommands',
        description='valid subcommands',
        help='additional help',
        dest='command',
    )

    # create a PR from command line
    pr_parser = subparsers.add_parser(
        'pull-request', aliases=['pr', 'PR', 'pullrequest']
    )

    pr_parser.add_argument(
        "repo", help=("GitHub repository (owner/name) to use")
    )

    pr_parser.add_argument(
        "head",
        help=("Branch to create a pull request from"),
    )

    pr_parser.add_argument(
        "target",
        default="main",
        help=("Branch as as target for the pull"),
    )

    pr_parser.add_argument(
        "title",
        help=("Title for the pull request"),
    )

    pr_parser.add_argument(
        "-b",
        "--body",
        default="#empty body",
        help=(
            "Description for the pull request. Can be formatted in Markdown."
        ),
    )

    pr_parser.add_argument(
        "-t",
        "--token",
        default="GITHUB_TOKEN",
        type=from_env,
        help=(
            "GitHub Token to access the repository. "
            "Default looks for environment variable 'GITHUB_TOKEN'"
        ),
    )

    return parser.parse_args(args)
