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
#

from argparse import Namespace
from pathlib import Path

import httpx

from pontos.github.api import GitHubRESTApi
from pontos.helper import shell_cmd_runner
from pontos.terminal import Terminal

from .helper import get_current_version, get_project_name


def sign(
    terminal: Terminal,
    args: Namespace,
    *,
    token: str,
    **_kwargs,
) -> bool:
    if not token and not args.dry_run:
        # dry run doesn't upload assets. therefore a token MAY NOT be required
        # for public repositories.
        terminal.error(
            "Token is missing. The GitHub token is required to upload "
            "signature files."
        )
        return False

    project: str = (
        args.project
        if args.project is not None
        else get_project_name(shell_cmd_runner)
    )
    space: str = args.space
    git_tag_prefix: str = args.git_tag_prefix
    release_version: str = (
        args.release_version
        if args.release_version is not None
        else get_current_version(terminal)
    )
    signing_key: str = args.signing_key

    git_version: str = f"{git_tag_prefix}{release_version}"
    repo = f"{space}/{project}"

    github = GitHubRESTApi(token=token)

    if not github.release_exists(repo, git_version):
        terminal.error(f"Release version {git_version} does not exist.")
        return False

    zip_destination = Path(f"{project}-{release_version}.zip")
    with github.download_release_zip(
        repo, git_version, zip_destination
    ) as zip_progress:
        terminal.download_progress(zip_progress)

    tarball_destination = Path(f"{project}-{release_version}.tar.gz")
    with github.download_release_tarball(
        repo, git_version, tarball_destination
    ) as tar_progress:
        terminal.download_progress(tar_progress)

    file_paths = [zip_destination, tarball_destination]

    for progress in github.download_release_assets(repo, git_version):
        file_paths.append(progress.destination)
        terminal.download_progress(progress)

    for file_path in file_paths:
        terminal.info(f"Signing {file_path}")

        if args.passphrase:
            process = shell_cmd_runner(
                f"gpg --pinentry-mode loopback --default-key {signing_key}"
                f" --yes --detach-sign --passphrase {args.passphrase}"
                f" --armor {file_path}"
            )
        else:
            process = shell_cmd_runner(
                f"gpg --default-key {signing_key} --yes --detach-sign "
                f"--armor {file_path}"
            )

        process.check_returncode()

    if args.dry_run:
        return True

    upload_files = [
        (Path(f"{str(p)}.asc"), "application/pgp-signature") for p in file_paths
    ]
    terminal.info(f"Uploading assets: {[str(p[0]) for p in upload_files]}")

    try:
        for uploaded_file in github.upload_release_assets(
            repo, git_version, upload_files
        ):
            terminal.ok(f"Uploaded: {uploaded_file}")
    except httpx.HTTPError as e:
        terminal.error(f"Failed uploading asset {e}")
        return False

    return True
