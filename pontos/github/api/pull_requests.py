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

from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional

import httpx

from pontos.github.api.helper import JSON, JSON_OBJECT, FileStatus


class GitHubRESTPullRequestsMixin:
    def pull_request_exists(self, repo: str, pull_request: int) -> bool:
        """
        Check if a single branch in a repository exists

        Args:
            repo: GitHub repository (owner/name) to use
            pull_request: Pull request number to check
        """
        api = f"/repos/{repo}/pulls/{pull_request}"
        response: httpx.Response = self._request(api)
        return response.is_success

    def pull_request_commits(
        self, repo: str, pull_request: int
    ) -> Iterable[JSON_OBJECT]:
        """
        Get all commit information of a pull request

        Hint: At maximum GitHub allows to receive 250 commits of a pull request.

        Args:
            repo: GitHub repository (owner/name) to use
            pull_request: Pull request number

        Returns:
            Information about the commits in the pull request as a dict
        """
        # per default github only shows 35 commits and at max it is only
        # possible to receive 100
        params = {"per_page": "100"}
        api = f"/repos/{repo}/pulls/{pull_request}/commits"
        return list(self._request_all(api, params=params))

    def create_pull_request(
        self,
        repo: str,
        *,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
    ):
        """
        Create a new Pull Request on GitHub

        Args:
            repo: GitHub repository (owner/name) to use
            head_branch: Branch to create a pull request from
            base_branch: Branch as target for the pull request
            title: Title for the pull request
            body: Description for the pull request. Can be formatted in Markdown

        Raises:
            HTTPError if the request was invalid
        """
        api = f"/repos/{repo}/pulls"
        data = {
            "head": head_branch,
            "base": base_branch,
            "title": title,
            "body": body.replace("\\n", "\n"),
        }
        response: httpx.Response = self._request(
            api, data=data, request=httpx.post
        )
        response.raise_for_status()

    def update_pull_request(
        self,
        repo: str,
        pull_request: int,
        *,
        base_branch: Optional[str] = None,
        title: Optional[str] = None,
        body: Optional[str] = None,
    ):
        """
        Update a Pull Request on GitHub

        Args:
            repo: GitHub repository (owner/name) to use
            pull_request: Pull request number
            base_branch: Branch as target for the pull request. Leave empty for
                keeping the current one.
            title: Title for the pull request. Leave empty for keeping the
                current one.
            body: Description for the pull request. Can be formatted in
                Markdown. Leave empty for keeping the current one.
        """
        api = f"/repos/{repo}/pulls/{pull_request}"

        data = {}
        if base_branch:
            data["base"] = base_branch
        if title:
            data["title"] = title
        if body:
            data["body"] = body.replace("\\n", "\n")

        response: httpx.Response = self._request(
            api, data=data, request=httpx.post
        )
        response.raise_for_status()

    def add_pull_request_comment(
        self, repo: str, pull_request: int, comment: str
    ):
        """
        Add a comment to a pull request on GitHub

        Args:
            repo: GitHub repository (owner/name) to use
            pull_request: Pull request number where to add a comment
            comment: The actual comment message. Can be formatted in Markdown.

        Raises:
            HTTPError if the request was invalid
        """
        api = f"/repos/{repo}/issues/{pull_request}/comments"
        data = {"body": comment}
        response: httpx.Response = self._request(
            api, data=data, request=httpx.post
        )
        response.raise_for_status()

    def pull_request_files(
        self, repo: str, pull_request: int, status_list: Iterable[FileStatus]
    ) -> Dict[FileStatus, Iterable[Path]]:
        """
        Get all modified files of a pull request

        Hint: At maximum GitHub allows to receive 3000 files of a commit.

        Args:
            repo: GitHub repository (owner/name) to use
            pull_request: Pull request number
            status_list: Iterable of status change types that should be included

        Returns:
            Information about the commits in the pull request as a dict
        """
        # per default github only shows 35 files per page and at max it is only
        # possible to receive 100
        params = {"per_page": "100"}
        api = f"/repos/{repo}/pulls/{pull_request}/files"
        data: Iterator[JSON] = self._request_all(api, params=params)
        file_dict = defaultdict(list)
        for f in data:
            try:
                status = FileStatus(f["status"])
            except ValueError:
                # unknown status
                continue

            if status in status_list:
                file_dict[status].append(Path(f["filename"]))

        return file_dict
