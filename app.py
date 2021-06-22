#!/usr/bin/env python3
# pulp-repository-sync-job
# Copyright(C) 2021 Fridolin Pokorny <fridolin@redhat.com>
#
# This program is free software: you can redistribute it and / or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""This is the main script of the template project."""

import click
import logging
from urllib.parse import urlunparse
from typing import Generator

import requests
from thoth.common import init_logging
from thoth.storages import GraphDatabase
from thoth.storages import __version__ as __storages__version__
from thoth.common import __version__ as __common__version__

_PULP_PYTHON_DISTRIBUTION_PATH = "/pulp/api/v3/distributions/python/pypi/"

_LOGGER = logging.getLogger("thoth.pulp_repository_sync")
init_logging()

__version__ = "0.0.1"
__component_version__ = f"{__version__}+storages.{__storages__version__}" f".common.{__common__version__}"


def _list_pulp_python_repositories(instance_host: str, *, username: str, password: str) -> Generator[str, None, None]:
    """List available pulp-python repositories available on the given Pulp instance."""
    pulp_session = requests.Session()
    pulp_session.auth = (username, password)

    response = pulp_session.get(urlunparse(("https", instance_host, _PULP_PYTHON_DISTRIBUTION_PATH, "", "", "")))
    response.raise_for_status()

    for result in response.json()["results"]:
        simple_repository = (
            f"{result['base_url']}simple" if result["base_url"].endswith("/") else f"{result['base_url']}/simple"
        )
        yield urlunparse(("https", instance_host, simple_repository, "", "", ""))


@click.command()
@click.option(
    "--pulp-instance",
    help="A pulp instance host to be checked for new Python package indexes.",
    type=str,
    required=True,
    envvar="THOTH_PULP_REPOSITORIES_SYNC_PULP_INSTANCES",
    metavar="HOST",
)
@click.option(
    "--pulp-username",
    help="Username used for listing Python package indexes available in pulp-python.",
    type=str,
    required=True,
    envvar="THOTH_PULP_REPOSITORIES_SYNC_PULP_USERNAME",
    metavar="USERNAME",
)
@click.option(
    "--pulp-password",
    help="Password used for listing Python package indexes available in pulp-python.",
    type=str,
    required=True,
    envvar="THOTH_PULP_REPOSITORIES_SYNC_PULP_PASSWORD",
    metavar="PASSWORD",
)
@click.option(
    "--disable-index/--enable-index",
    help="Register the given Python package index in Thoth but keep it disabled by default.",
    type=bool,
    required=False,
    show_default=True,
    envvar="THOTH_PULP_REPOSITORIES_SYNC_DISABLE_INDEX",
)
def cli(
    pulp_instance: str,
    pulp_username: str,
    pulp_password: str,
    disable_index: bool = False,
) -> None:
    """Monitor new pulp-python Python package indexes."""
    _LOGGER.info("Starting pulp-repository-sync-job in version %r", __component_version__)

    graph = GraphDatabase()
    graph.connect()

    known_indexes = {i["url"] for i in graph.get_python_package_index_all()}
    _LOGGER.debug("Known indexes: %r", known_indexes)

    _LOGGER.info("Checking available pulp-python repositories at %r", pulp_instance)
    for repository_url in _list_pulp_python_repositories(
        pulp_instance,
        username=pulp_username,
        password=pulp_password,
    ):
        if repository_url not in known_indexes:
            _LOGGER.info("Registering new pulp-python repository available at %r", repository_url)
            graph.register_python_package_index(
                url=repository_url, warehouse_api_url=None, verify_ssl=True, enabled=not disable_index
            )
        else:
            _LOGGER.info("pulp-python repository available at %r is already known to Thoth", repository_url)


__name__ == "__main__" and cli()
