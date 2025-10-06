import webbrowser
import requests
import yaml
import json
import re
from urllib.parse import quote


def search_web(query):
    """
    Searches the web using the default browser.
    Parameters: {"query": "The search term."}
    """
    url = f"https://www.google.com/search?q={query}"
    webbrowser.open(url)
    return f"Searching for '{query}'."

def get_weather(location=None):
    """
    Gets current weather. Uses the user's IP for location if not specified.
    Parameters: {"location": "The city for the weather, e.g., 'London'. Leave blank for your current location."}
    """
    try:
        with open("kortex/config.yaml", 'r') as f:
            config = yaml.safe_load(f)
        
        services_config = config.get('services', {})
        weather_config = services_config.get('weather', {})
        location_config = services_config.get('location', {})

        if not weather_config.get('enabled'):
            return "The weather feature is disabled. Please enable it in the settings."
        
        weather_api_key = weather_config.get('api_key')
        if not weather_api_key:
            return "The Meteosource weather API key is missing. Please add it in the settings."

        target_location = location
        is_current_location = False
        if not target_location or target_location.lower() in ['here', 'my location', 'current location', 'nearby']:
            is_current_location = True
            if not location_config.get('enabled'):
                return "Location services must be enabled to get weather for your current location."
            
            iplocate_api_key = location_config.get('iplocate_api_key')
            if not iplocate_api_key:
                return "IPLocate.io API key is missing. Cannot determine current location."

            ip_response = requests.get(f"https://iplocate.io/api/lookup?apikey={iplocate_api_key}")
            ip_response.raise_for_status()
            ip_data = ip_response.json()
            city = ip_data.get('city')

            if not city:
                return "Could not determine your current city from your IP address."
            target_location = city
            
        find_url = "https://www.meteosource.com/api/v1/free/find_places"
        find_params = {'text': target_location, 'key': weather_api_key}
        find_response = requests.get(find_url, params=find_params)
        find_response.raise_for_status()
        places = find_response.json()
        
        if not places:
            return f"Sorry, I couldn't find a location named '{target_location}'."
        
        place_id = places[0]['place_id']
        found_name = places[0]['name']

        weather_url = "https://www.meteosource.com/api/v1/free/point"
        weather_params = {'place_id': place_id, 'sections': 'current', 'units': 'auto', 'key': weather_api_key}
        weather_response = requests.get(weather_url, params=weather_params)
        weather_response.raise_for_status()
        data = weather_response.json()
        
        current = data.get('current', {})
        if not current:
            return f"Could not retrieve current weather for {found_name}."
            
        summary = current.get('summary', 'N/A')
        temp = current.get('temperature', 'N/A')
        units = '°C' if data.get('units') == 'metric' else '°F'
        
        location_desc = f"your location ({found_name})" if is_current_location else found_name
        return f"The current weather in {location_desc} is {summary.lower()} with a temperature of {temp}{units}."

    except requests.exceptions.RequestException as e:
        return f"A network error occurred: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

def convert_currency(amount, from_currency, to_currency):
    """
    Converts an amount from one currency to another using real-time exchange rates.
    Parameters: {"amount": "The numerical value to convert.", "from_currency": "The 3-letter currency code to convert from (e.g., 'USD').", "to_currency": "The 3-letter currency code to convert to (e.g., 'EUR')."}
    """
    try:
        with open("kortex/config.yaml", 'r') as f: config = yaml.safe_load(f)
        service_config = config.get('services', {}).get('currency_conversion', {})
        if not service_config.get('enabled'): return "Currency conversion is disabled in settings."
        api_key = service_config.get('api_key')
        if not api_key: return "CurrencyFreaks API key is missing in settings."

        from_curr = from_currency.upper()
        to_curr = to_currency.upper()
        
        url = "https://api.currencyfreaks.com/v2.0/rates/latest"
        params = {'apikey': api_key, 'symbols': f'{from_curr},{to_curr}'}
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        rates = data.get('rates', {})
        if from_curr not in rates or to_curr not in rates:
            return f"Could not get exchange rates for {from_curr} or {to_curr}."

        amount = float(amount)
        from_rate = float(rates[from_curr])
        to_rate = float(rates[to_curr])
        
        if from_rate == 0: return "Cannot convert from a currency with a rate of zero."
        
        converted_amount = (amount / from_rate) * to_rate
        return f"{amount:.2f} {from_curr} is approximately {converted_amount:.2f} {to_curr}."

    except requests.exceptions.HTTPError as e:
        return f"API Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"An error occurred during currency conversion: {e}"

def find_location(location_query):
    """
    Finds a location on a map and opens it in the browser. Handles 'near me' queries by finding the user's city via their IP.
    Parameters: {"location_query": "The place, address, or point of interest to find (e.g., 'Eiffel Tower' or 'pizza near me')."}
    """
    try:
        with open("kortex/config.yaml", 'r') as f: config = yaml.safe_load(f)
        service_config = config.get('services', {}).get('location', {})
        
        search_query = location_query
        
        match = re.search(r'(.+?)\s*\b(near|around)\s+me\b', location_query, re.IGNORECASE)
        if match:
            if not service_config.get('enabled'): return "Location services are disabled in settings."
            api_key = service_config.get('iplocate_api_key')
            if not api_key: return "IPLocate.io API key is missing in settings."

            ip_response = requests.get(f"https://iplocate.io/api/lookup?apikey={api_key}")
            ip_response.raise_for_status()
            ip_data = ip_response.json()
            city = ip_data.get('city')
            
            if city:
                subject_query = match.group(1).strip()
                search_query = f"{subject_query} in {city}"
            else:
                return "Could not determine your current city from your IP address."
        
        headers = {'User-Agent': 'KortexDesktopAssistant/1.0'}
        geocode_url = "https://nominatim.openstreetmap.org/search"
        params = {'q': search_query, 'format': 'json', 'limit': 1}
        
        geo_response = requests.get(geocode_url, params=params, headers=headers)
        geo_response.raise_for_status()
        geo_data = geo_response.json()
        
        if not geo_data:
            return f"Sorry, I couldn't find a location for '{search_query}'."
            
        maps_url = f"https://www.google.com/maps/search/?api=1&query={quote(search_query)}"
        webbrowser.open(maps_url)
        
        return f"Showing results for '{search_query}' on the map."

    except requests.exceptions.RequestException as e:
        return f"A network error occurred while finding the location: {e}"
    except Exception as e:
        return f"An unexpected error occurred while finding the location: {e}"