# noonlight-py
Asynchronous Noonlight API client for Python
(*based on the API documented [here](https://docs.noonlight.com/reference)*)

## Usage

```
>>> import noonlight

# Initialize the client with your token from completing an OAuth2 flow 
#    with Noonlight (and optionally your aiohttp session and timeout)

>>> client = noonlight.NoonlightClient(token = "my_api_token_from_noonlight")

# Create an alarm object using the body parameters documented here:
#   https://docs.noonlight.com/reference#create-alarm

>>> alarm = await client.create_alarm(body = {'location.coordinates': {'lat':38.897957, 'lng':‎-77.036560, 'accuracy': 5} } )

# Check alarm status

>>> print(alarm.status)

# Cancel alarm

>>> cancelled = await alarm.cancel()
```