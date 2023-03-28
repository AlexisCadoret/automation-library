import signal
from datetime import datetime, time, timedelta, timezone
from functools import cached_property
from threading import Event
from typing import Generator
from urllib.parse import urljoin

import requests
from orjson import orjson
from pydantic import Field
from sekoia_automation.connector import Connector, DefaultConnectorConfiguration
from sekoia_automation.storage import PersistentJSON

from withsecure import WithSecureModule
from withsecure.client import ApiClient
from withsecure.constants import API_BASE_URL
from withsecure.helper import get_upper_second
from withsecure.logging import get_logger

logger = get_logger()


class FetchEventsException(Exception):
    pass


class SecurityEventsConnectorConfiguration(DefaultConnectorConfiguration):
    organization_id: str | None = Field(..., description="UUID of the organization (if missing, default org. is used)")
    frequency: int = 5


class SecurityEventsConnector(Connector):
    """
    This connector fetches security events from the API of WithSecure
    """

    module: WithSecureModule
    configuration: SecurityEventsConnectorConfiguration

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = Event()
        self.context = PersistentJSON("context.json", self._data_path)
        self.from_date = self.most_recent_date_seen
        self.fetch_events_limit = 1000

        # Register signal to terminate thread
        signal.signal(signal.SIGINT, self.exit)
        signal.signal(signal.SIGTERM, self.exit)

    def exit(self, _, __):
        self.log(message="Stopping WithSecure Security Events connector", level="info")
        # Exit signal received, asking the processor to stop
        self._stop_event.set()

    @property
    def most_recent_date_seen(self):
        now = datetime.now(timezone.utc)

        with self.context as cache:
            most_recent_date_seen_str = cache.get("most_recent_date_seen")

            # if undefined, retrieve events from the last minute
            if most_recent_date_seen_str is None:
                return now - timedelta(minutes=1)

            # parse the most recent date seen
            most_recent_date_seen = datetime.fromisoformat(most_recent_date_seen_str)

            # We don't retrieve messages older than one week
            one_week_ago = now - timedelta(days=7)
            if most_recent_date_seen < one_week_ago:
                most_recent_date_seen = one_week_ago

            return most_recent_date_seen

    @cached_property
    def client(self):
        return ApiClient(
            client_id=self.module.configuration.client_id, secret=self.module.configuration.secret, log_cb=self.log
        )

    def _handle_response_error(self, response: requests.Response):
        if not response.ok:
            message = f"Request on WithSecure API to fetch events failed with status {response.status_code} - {response.reason}"

            # enrich error logs with detail from the WithSecure API
            try:
                error = response.json()
                message = f"{message}: {error['errorCode']} - {error['errorSummary']}"
            except Exception:
                pass

            raise FetchEventsException(message)

    def __fetch_next_events(self, from_date: datetime) -> Generator[list, None, None]:
        """
        Fetch all the events that occurred after the specified from date
        """
        # set parameters
        params = {
            "serverTimestampStart": from_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": self.fetch_events_limit,
            "order": "asc",
            "organizationId": self.configuration.organization_id,
        }

        # get the first page of events
        headers = {"Accept": "application/json"}
        url = urljoin(API_BASE_URL, "/security-events/v1/security-events")
        response = self.client.get(url, params=params, headers=headers)

        while not self._stop_event.is_set():
            # manage the last response
            self._handle_response_error(response)

            # get events from the response
            payload = response.json()
            events = payload.get("items", [])

            # yielding events if defined
            if events:
                yield events
            else:
                logger.info(
                    f"The last page of events was empty. Waiting {self.configuration.frequency}s "
                    "before fetching next page"
                )
                time.sleep(self.configuration.frequency)

            anchor = payload.get("nextAnchor")
            if not anchor:
                return
            params["anchor"] = anchor

            response = self.client.get(url, params=params, headers=headers)

    def fetch_events(self) -> Generator[list, None, None]:
        most_recent_date_seen = self.from_date

        for next_events in self.__fetch_next_events(most_recent_date_seen):
            if next_events:
                last_event_date = datetime.fromisoformat(next_events[-1]["serverTimestampStart"])

                # save the greater date ever seen
                if last_event_date > most_recent_date_seen:
                    most_recent_date_seen = get_upper_second(
                        last_event_date
                    )  # get the upper second to exclude the most recent event seen

                # forward current events
                yield next_events

        # save the most recent date
        if most_recent_date_seen > self.from_date:
            self.from_date = most_recent_date_seen

            # save in context the most recent date seen
            with self.context as cache:
                cache["most_recent_date_seen"] = most_recent_date_seen.isoformat()

    def next_batch(self):
        # save the starting time
        batch_start_time = time.time()

        # Fetch next batch
        for events in self.fetch_events():
            batch_of_events = [orjson.dumps(event).decode("utf-8") for event in events]

            # if the batch is full, push it
            if len(batch_of_events) > 0:
                self.log(
                    message=f"Forwarded {len(batch_of_events)} events to the intake",
                    level="info",
                )
                self.push_events_to_intakes(events=batch_of_events)
            else:
                self.log(
                    message="No events to forward",
                    level="info",
                )

        # get the ending time and compute the duration to fetch the events
        batch_end_time = time.time()
        batch_duration = int(batch_end_time - batch_start_time)
        logger.debug(f"Fetched and forwarded events in {batch_duration} seconds")

        # compute the remaining sleeping time. If greater than 0, sleep
        delta_sleep = self.configuration.frequency - batch_duration
        if delta_sleep > 0:
            logger.debug(f"Next batch in the future. Waiting {delta_sleep} seconds")
            time.sleep(delta_sleep)

    def run(self):
        self.log(message="Start fetching WithSecure security events", level="info")

        while not self._stop_event.is_set():
            try:
                self.next_batch()
            except Exception as error:
                self.log_exception(error, message="Failed to forward events")
