import aiohttp
import asyncio
import pytest
from aioresponses import aioresponses
from noonlight import NoonlightClient

alarm_id = 'abcd1234'

loop = asyncio.get_event_loop()
session = aiohttp.ClientSession(loop=loop)
client = NoonlightClient('test-token', session=session)


def test_get_alarm_status():
    with aioresponses() as mocked:
        mocked.get(
            'https://api-sandbox.safetrek.io/v1/alarms/' + alarm_id + '/status',
            status=200, body='{"status": "ACTIVE"}')

        resp = loop.run_until_complete(client.get_alarm_status(alarm_id))

        assert {'status': 'ACTIVE'} == resp


def test_update_alarm():
    with aioresponses() as mocked:
        mocked.put(
            'https://api-sandbox.safetrek.io/v1/alarms/' + alarm_id + '/status',
            status=200, body='{"status": 200}')

        resp = loop.run_until_complete(client.update_alarm(alarm_id, {"status": "CANCELED"}))

        assert {'status': 200} == resp


def test_create_alarm():
    with aioresponses() as mocked:
        mocked.post(
            'https://api-sandbox.safetrek.io/v1/alarms',
            status=200, body='{"status": 200}')

        resp = loop.run_until_complete(client.create_alarm({"anything": "anything"}))

        assert {'status': 200} == resp

def test_update_alarm_location():
    with aioresponses() as mocked:
        mocked.post(
            'https://api-sandbox.safetrek.io/v1/alarms/' + alarm_id + '/locations',
            status=200, body='{"status": 200}')

        resp = loop.run_until_complete(client.update_alarm_location(alarm_id, {"coordinates": {"lat": 1, "lng": 2}}))

        assert {'status': 200} == resp

