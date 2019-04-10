import aiohttp

from datetime import datetime

DEFAULT_BASE_URL = "https://api-sandbox.noonlight.com/platform/v1"

NOONLIGHT_SERVICES_POLICE = 'police'
NOONLIGHT_SERVICES_FIRE = 'fire'
NOONLIGHT_SERVICES_MEDICAL = 'medical'

NOONLIGHT_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

class NoonlightAlarm(object):
    """
    Noonlight API Alarm Object
    
    :param client: NoonlightClient parent object
    :type client: NoonlightClient
    :param json_data: Parsed JSON dictionary from API response to populate 
        the NoonlightAlarm object
    :type json_data: dict
    """
    def __init__(self, client, json_data):
        """
        Creates a new :class:`NoonlightAlarm` instance.
        """
        self._client = client
        self._json_data = json_data
        self._sensor_events = []
        self._sent_sensor_events = []
        
    @classmethod
    async def create(cls, client, json_data_future):
        """
        Factory coroutine for creating NoonlightAlarm objects
        """
        return NoonlightAlarm(client, await json_data_future)
        
    @property
    def id(self):
        """Returns the ID of this NoonlightAlarm"""
        return self._json_data.get('id')
        
    @property
    def status(self):
        """Returns the last known status of this NoonlightAlarm"""
        return self._json_data.get('status')
        
    @property
    def services(self):
        """Returns a list of active services for this NoonlightAlarm"""
        services = self._json_data.get('services',{})
        return [key for key in services if services[key]]
        
    @property
    def is_police(self):
        """Returns True if police services are included in this alarm"""
        return NOONLIGHT_SERVICES_POLICE in self.services
        
    @property
    def is_fire(self):
        """Returns True if fire services are included in this alarm"""
        return NOONLIGHT_SERVICES_FIRE in self.services
        
    @property
    def is_medical(self):
        """Returns True if medical services are included in this alarm"""
        return NOONLIGHT_SERVICES_MEDICAL in self.services
        
    @property
    def created_at(self):
        """Returns the datetime the NoonlightAlarm was created"""
        try:
            return datetime.strptime(self._json_data.get('created_at',"0001-01-01T00:00:00.00Z"),NOONLIGHT_DATETIME_FORMAT)
        except:
            return datetime.min
        
    @property
    def locations(self):
        """
        Returns a list of locations for this NoonlightAlarm, sorted by most 
        recent first
        
        NOTE: Currently the Noonlight API only returns the first location when 
        the alarm is created, additional locations will be appended by this 
        library.
        """
        locations_merged = self._json_data.get('locations',{}).get('addresses',[]) + self._json_data.get('locations',{}).get('coordinates',[])
        for location in locations_merged:
            if 'created_at' in location and type(location['created_at']) is not datetime:
                try:
                    location['created_at'] = datetime.strptime(location['created_at'],NOONLIGHT_DATETIME_FORMAT)
                except:
                    pass
        return sorted(locations_merged,key=lambda x: x.get('created_at'), reverse = True)
        
    @property
    def events(self):
        return self._sensor_events
        
    @property
    def sent_events(self):
        return self._sent_sensor_events
        
    @property
    def unsent_events(self):
        return list(set(self.events) - set(self.sent_events))
        
    async def add_event(self, *, event, send_immediately = True):
        """
        Adds a :class:`NoonlightSensorEvent` to this :class:`NoonlightAlarm`'s
        sensor event queue and optionally flush the event queue to the
        Noonlight API immediately (true by default)
        
        :param event: a NoonlightSensorEvent object
        :type event: NoonlightSensorEvent
        :param send_immediately: set to True if the this event and all other 
            un-sent events in the queue should be sent to the Noonlight API 
            immediately (default: True)
        :type send_immediately: bool
        
        :returns: a list of transmitted events if `send_immediately` is True, 
            a list of un-transmitted events if `send_immediately` is False, 
            None if the event is already in queue to transmit or has been 
            transmitted already
        """
        if event and event not in self._sensor_events:
            self._sensor_events.append(event)
            if send_immediately:
                return await self.send_events()
            return self.unsent_events
        return None
                
    async def send_events(self):
        """
        Sends all previously un-sent `NoonlightSensorEvent`s in the queue to 
        the Noonlight API.
        """
        events_to_send = self.unsent_events
        if len(events_to_send) > 0:
            response = await self._client.send_sensor_events(sensor_events = events_to_send)
            if 'id' in response:
                self._sent_sensor_events.extend(events_to_send)
                return events_to_send
        return []
        
    async def cancel(self):
        """
        Cancels this alarm using the NoonlightClient that created this 
        NoonlightAlarm.
        
        :returns: True if alarm is cancelled, False if a response does not 
            have a 200 status
        :rtype: boolean
        """
        response = await self._client.update_alarm(id = self.id, body = {'status': 'CANCELED'})
        if response.get('status') == 200:
            self._json_data['status'] = 'CANCELED'
            return True
        return False
        
    async def update_location_coordinates(self, *, lat, lng, accuracy = 5.0):
        """
        Update the alarm location with the provided latitude and longitude.
        
        :param lat: Latitude of the new location
        :type lat: double
        :param lng: Longitude of the new location
        :type lng: double
        :param accuracy: (optional) Accuracy of the location in meters (default: 5m)
        :type accuracy: double
        
        :returns: True if location is updated and added to the locations list
        :rtype: boolean
        """
        data = {'lat':lat, 'lng':lng, 'accuracy': accuracy}
        return await self._update_location_by_type('coordinates', data)
        
    async def update_location_address(self, *, line1, line2 = None, city, state, zip):
        """
        Update the alarm location with the provided address.
        
        :param line1: Address line 1
        :type line1: str
        :param line2: Address line 2 (provide None or "" if N/A)
        :type line2: str
        :param city: Address city
        :type city: str
        :param state: Address state
        :type state: str
        :param zip: Address zip
        :type zip: str
        
        :returns: True if location is updated and added to the locations list
        :rtype: boolean
        """
        data = {'line1':line1, 'city':city, 'state': state.upper(), 'zip': zip}
        if line2 and len(line2) > 0:
            data['line2'] = line2
        return await self._update_location_by_type('address', data)
        
    async def _update_location_by_type(self, type, data):
        """
        Private method to update alarm location by type (coordinates or 
        address).
        
        :param type: Location type, 'coordinates' or 'address'
        :type type: str
        :param data: Location data, lat/lng or address information
        :type data: dict
        """
        if type in ('coordinates','address'):
            response = await self._client.update_alarm_location(id = self.id, body = {type: data} )
            if type in response:
                self._add_location(type, response[type])
                return True
        return False
        
    def _add_location(self, type, data):
        """
        Private method to add a location to the NoonlightAlarm object location 
        collection.
        
        :param type: Location type, 'coordinates' or 'address'
        :type type: str
        :param data: Location data, lat/lng or address information
        :type data: dict
        """
        if type in ('coordinates','address'):
            key = type
            if type == 'address':
                key = 'addresses'
            if 'locations' not in self._json_data:
                self._json_data['locations'] = {}
            if type not in self._json_data['locations']:
                self._json_data['locations'][key] = []
            self._json_data['locations'][key].append(data)
        
    async def get_status(self):
        """
        Update and return the current status of this NoonlightAlarm from 
        the API.
        """
        response = await self._client.get_alarm_status(id = self.id)
        if 'status' in response:
            self._json_data.update(response)
        return self.status

class NoonlightSensorEvent(object):
    def __init__(self, *, 
            timestamp, device_id, device_model, device_manufacturer, 
            device_name, attribute, value, unit
        ):
        self._timestamp = timestamp
        if isinstance(timestamp,datetime):
            self._timestamp = "{}Z".format(timestamp.isoformat())
        self._device_id = device_id
        self._device_model = device_model
        self._device_manufacturer = device_manufacturer
        self._device_name = device_name
        self._attribute = attribute
        self._value = value
        self._unit = unit
        
    @property
    def timestamp(self):
        return self._timestamp
    @property
    def device_id(self):
        return self._device_id
    @property
    def device_model(self):
        return self._device_model
    @property
    def device_manufacturer(self):
        return self._device_manufacturer
    @property
    def device_name(self):
        return self._device_name
    @property
    def attribute(self):
        return self._attribute
    @property
    def value(self):
        return self._value
    @property
    def unit(self):
        return self._unit

    def __members(self):
        return (self.timestamp, self.device_id)

    def __eq__(self, other):
        if type(other) is type(self):
            return self.__members() == other.__members()
        else:
            return False

    def __hash__(self):
        return hash(self.__members())
        
class NoonlightClient(object):
    """
    NoonlightClient API client

    :param token: OAuth2 token for the Noonlight API
    :type token: str
    :param session: aiohttp session to use or None
    :type session: object or None
    :param timeout: seconds to wait for before triggering a timeout
    :type timeout: integer
    """
    def __init__(self, token, session=None,
                 timeout=aiohttp.client.DEFAULT_TIMEOUT):
        """
        Creates a new :class:`NoonlightClient` instance.
        """
        self._headers = {'Content-Type': 'application/json'}
        if session is not None:
            self._session = session
        else:
            self._session = aiohttp.ClientSession(timeout=timeout)
        
        self._base_url = DEFAULT_BASE_URL
        self.set_token(token = token)

    @property
    def alarms_url(self):
        """Noonlight API base URL for alarms."""
        return "{}/alarms".format(self._base_url)
        
    @property
    def alarm_status_url(self):
        """Noonlight API URL for alarm status."""
        return "{url}/{id}/status".format(url=self.alarms_url,id='{id}')
        
    @property
    def alarm_location_url(self):
        """Noonlight API URL for location updates."""
        return "{url}/{id}/locations".format(url=self.alarms_url,id='{id}')
        
    @property
    def alarm_sensor_events_url(self):
        """Noonlight API URL for sensor events."""
        return "{}/st-events".format(self._base_url)
        
    def set_token(self, *, token):
        """
        Sets the API token for this NoonlightClient
        
        :param token: OAuth2 token for the Noonlight API
        :type token: str
        """
        self._token = token
        self._headers['Authorization'] = "Bearer {}".format(self._token)
            
    async def get_alarm_status(self, *, id):
        """
        Get the status of an alarm by id

        :param id: Id of the alarm
        :returns: Alarm data as a dictionary
        :raises: ClientError, Unauthorized, BadRequest, Forbidden,
                 TooManyRequests, InternalServerError
        """
        return await self._get(self.alarm_status_url.format(id=id))

    async def create_alarm(self, *, body):
        """
        Create an alarm

        :param body: A dictionary of data to post with the alarm. Will be
            automatically serialized to JSON. See
            https://docs.noonlight.com/reference#create-alarm
        :returns: :class:`NoonlightAlarm` object
        :raises: ClientError, Unauthorized, BadRequest, Forbidden,
                 TooManyRequests, InternalServerError
        """
        return await NoonlightAlarm.create(self, self._post(self.alarms_url, body))

    async def update_alarm(self, *, id, body):
        """
        Create an alarm

        :param id: Id of the alarm
        :param body: A dictionary of data to post with the alarm. Will be
            automatically serialized to JSON. See
            https://docs.noonlight.com/reference#create-alarm
        :returns: Alarm data as a dictionary
        :raises: ClientError, Unauthorized, BadRequest, Forbidden,
                 TooManyRequests, InternalServerError
        """
        return await self._put(self.alarm_status_url.format(id=id), body)

    async def update_alarm_location(self, *, id, body):
        """
        Update the alarm location

        :param id: Id of the alarm
        :param body: A dictionary of data to post with the alarm. Will be
            automatically serialized to JSON. See
            https://docs.noonlight.com/reference#update-alarm-location
        :returns: Updated coordinates for the alarm
        :raises: ClientError, Unauthorized, BadRequest, Forbidden,
                 TooManyRequests, InternalServerError
        """
        return await self._post(self.alarm_location_url.format(id=id), body)
        
    def _sensor_event_to_dict(self, sensor_event):
        event_attrs = [
            'timestamp', 'device_id', 'device_model', 'device_manufacturer',
            'device_name', 'attribute', 'value', 'unit'
        ]
        return {attr: getattr(sensor_event,attr) for attr in event_attrs}
      
    async def send_sensor_events(self, *, sensor_events):
        """
        Send a stream of sensor events or states to Noonlight
        
        :param sensor_events: a list of :class:`NoonlightSensorEvent` objects
        :type sensor_events: list
        """
        events = [self._sensor_event_to_dict(event) for event in sensor_events if isinstance(event, NoonlightSensorEvent)]
        return await self._post(self.alarm_sensor_events_url, data = events)
        
    async def send_sensor_event(self, *, sensor_event):
        """
        Send one sensor event or state to Noonlight
        
        :param sensor_event: a :class:`NoonlightSensorEvent` object
        :type sensor_event: NoonlightSensorEvent
        """
        return await self.send_sensor_events(sensor_events = [sensor_event])
        

    @staticmethod
    def handle_error(status, error):
        if status == 400:
            raise NoonlightClient.BadRequest(error)
        elif status == 401:
            raise NoonlightClient.Unauthorized(error)
        elif status == 403:
            raise NoonlightClient.Forbidden(error)
        elif status == 429:
            raise NoonlightClient.TooManyRequests(error)
        elif status == 500:
            raise NoonlightClient.InternalServerError(error)
        else:
            raise NoonlightClient.ClientError(error)

    async def _get(self, path):
        async with self._session.get(
                path, headers=self._headers) as resp:
            if 200 <= resp.status < 300:
                return await resp.json()
            else:
                self.handle_error(resp.status, await resp.json())

    async def _post(self, path, data):
        async with self._session.post(
                path, json=data, headers=self._headers) as resp:
            if 200 <= resp.status < 300:
                return await resp.json()
            else:
                self.handle_error(resp.status, await resp.json())

    async def _put(self, path, data):
        async with self._session.put(
                path, json=data, headers=self._headers) as resp:
            if 200 <= resp.status < 300:
                return await resp.json()
            else:
                self.handle_error(resp.status, await resp.json())

    class ClientError(Exception):
        """Generic Error."""
        pass

    class Unauthorized(ClientError):
        """Failed Authentication."""
        pass

    class BadRequest(ClientError):
        """Request is malformed."""
        pass

    class Forbidden(ClientError):
        """Access is prohibited."""
        pass

    class TooManyRequests(ClientError):
        """Too many requests for this time period."""
        pass

    class InternalServerError(ClientError):
        """Server Internal Error."""
        pass

    class InvalidData(ClientError):
        """Can't parse response data."""
        pass
