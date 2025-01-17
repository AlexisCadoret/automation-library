"""Tests related to http client."""
from typing import Any

import pytest
from aioresponses import aioresponses
from faker import Faker

from client.http_client import CheckpointHttpClient
from client.token_refresher import CheckpointToken


@pytest.fixture
def http_client(session_faker: Faker) -> CheckpointHttpClient:
    """
    Get CheckpointHttpClient instance.

    Args:
        session_faker: Faker

    Returns:
        CheckpointHttpClient:
    """
    return CheckpointHttpClient(
        client_id=session_faker.pystr(),
        secret_key=session_faker.pystr(),
        auth_url=session_faker.url(),
        base_url=session_faker.url(),
    )


@pytest.mark.asyncio
async def test_checkpoint_http_client_get_harmony_mobile_alerts_empty(
    session_faker: Faker, http_client: CheckpointHttpClient, http_token: tuple[CheckpointToken, dict[str, Any]]
):
    """
    Test `get_harmony_mobile_alerts` method.

    Args:
        session_faker: Faker
        http_client: CheckpointHttpClient
        http_token: tuple[CheckpointToken, dict[str, Any]]
    """
    _, token_data = http_token
    with aioresponses() as mocked:
        time_events_from = session_faker.date_time()
        limit = session_faker.pyint(min_value=100, max_value=1000)
        get_events_url = "{0}/app/SBM/external_api/v3/alert/?backend_last_updated__gte={1}&limit={2}".format(
            http_client.base_url,
            time_events_from.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            limit,
        )

        events_data = {
            "meta": {
                "limit": limit,
                "next": session_faker.word(),
                "previous": session_faker.word(),
                "offset": 0,
                "total_count": 0,
            },
            "objects": [],
        }

        mocked.post(http_client.auth_url, status=200, payload=token_data)
        mocked.get(get_events_url, status=200, payload=events_data)

        result = await http_client.get_harmony_mobile_alerts(time_events_from, limit)

        assert result == events_data["objects"]


@pytest.mark.asyncio
async def test_checkpoint_http_client_get_harmony_mobile_alerts_success(
    session_faker: Faker, http_client: CheckpointHttpClient, http_token: tuple[CheckpointToken, dict[str, Any]]
):
    """
    Test `get_harmony_mobile_alerts` method.

    Args:
        session_faker: Faker
        http_client: CheckpointHttpClient
        http_token: tuple[CheckpointToken, dict[str, Any]]
    """
    _, token_data = http_token
    with aioresponses() as mocked:
        time_events_from = session_faker.date_time()
        limit = session_faker.pyint(min_value=100, max_value=1000)
        get_events_url = "{0}/app/SBM/external_api/v3/alert/?backend_last_updated__gte={1}&limit={2}".format(
            http_client.base_url,
            time_events_from.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            limit,
        )

        events = [
            {
                "id": session_faker.pyint(min_value=1, max_value=1000),
                "device_rooted": session_faker.pybool(),
                "attack_vector": session_faker.word(),
                "backend_last_updated": session_faker.word(),
                "details": session_faker.word(),
                "device_id": session_faker.word(),
                "email": session_faker.word(),
                "event": session_faker.word(),
                "event_timestamp": session_faker.word(),
                "mdm_uuid": session_faker.word(),
                "name": session_faker.word(),
                "number": session_faker.word(),
                "severity": session_faker.word(),
                "threat_factors": session_faker.word(),
                "device_model": session_faker.word(),
                "client_version": session_faker.word(),
            }
            for _ in range(session_faker.pyint(min_value=1, max_value=limit))
        ]

        events_data = {
            "meta": {
                "limit": limit,
                "next": session_faker.word(),
                "previous": session_faker.word(),
                "offset": 0,
                "total_count": 0,
            },
            "objects": events,
        }

        mocked.post(http_client.auth_url, status=200, payload=token_data)
        mocked.get(get_events_url, status=200, payload=events_data)

        result = await http_client.get_harmony_mobile_alerts(time_events_from, limit)

        assert len(result) == len(events)
        assert [event.dict() for event in result] == events


@pytest.mark.asyncio
async def test_checkpoint_http_client_get_harmony_mobile_alerts_success_1(
    session_faker: Faker, http_client: CheckpointHttpClient, http_token: tuple[CheckpointToken, dict[str, Any]]
):
    """
    Test `get_harmony_mobile_alerts` method.

    Args:
        session_faker: Faker
        http_client: CheckpointHttpClient
        http_token: tuple[CheckpointToken, dict[str, Any]]
    """
    _, token_data = http_token
    with aioresponses() as mocked:
        time_events_from = session_faker.date_time()
        limit = session_faker.pyint(min_value=100, max_value=1000)
        get_events_url = "{0}/app/SBM/external_api/v3/alert/?backend_last_updated__gte={1}&limit={2}".format(
            http_client.base_url,
            time_events_from.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            limit,
        )

        events_data = {
            "meta": {
                "limit": limit,
                "next": session_faker.word(),
                "previous": session_faker.word(),
                "offset": 0,
                "total_count": 0,
            }
        }

        mocked.post(http_client.auth_url, status=200, payload=token_data)
        mocked.get(get_events_url, status=200, payload=events_data)

        assert await http_client.get_harmony_mobile_alerts(time_events_from, limit) == []
