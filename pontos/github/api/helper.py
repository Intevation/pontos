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

from enum import Enum
from typing import Dict, List, Optional, Union

import httpx

DEFAULT_GITHUB_API_URL = "https://api.github.com"
DEFAULT_TIMEOUT_CONFIG = httpx.Timeout(180.0)  # three minutes
JSON_OBJECT = Dict[str, Union[str, bool, int]]  # pylint: disable=invalid-name
JSON = Union[List[JSON_OBJECT], JSON_OBJECT]


class FileStatus(Enum):
    ADDED = "added"
    DELETED = "deleted"
    MODIFIED = "modified"
    RENAMED = "renamed"


class RepositoryType(Enum):
    ALL = "all"
    PUBLIC = "public"
    PRIVATE = "private"
    FORKS = "forks"
    SOURCES = "sources"
    MEMBER = "member"
    INTERNAL = "internal"


class WorkflowRunStatus(Enum):
    ACTION_REQUIRED = "action_required"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILURE = "failure"
    IN_PROGRESS = "in_progress"
    NEUTRAL = "neutral"
    QUEUED = "queued"
    REQUESTED = "requested"
    SKIPPED = "skipped"
    STALE = "stale"
    SUCCESS = "success"
    TIMED_OUT = "timed_out"
    WAITING = "waiting"


def _get_next_url(response: httpx.Response) -> Optional[str]:
    if response and response.links:
        try:
            return response.links["next"]["url"]
        except KeyError:
            pass

    return None
