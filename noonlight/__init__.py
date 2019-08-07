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
        
    def set_token(self, *, token):
        """
        Sets the API token for this NoonlightClient
        
        :param token: OAuth2 token for the Noonlight API
        :type token: str
        """
        self._token = token
        self._headers['Authorization'] = "Bearer {}".format(self._token)

    def set_base_url(self, base_url):
        """
        Override the default Noonlight base url for API calls.

        :param base_url: Base URL for the Noonlight API
        :type base_url: str
        """
        self._base_url = base_url
            
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
