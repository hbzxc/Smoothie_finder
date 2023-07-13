import math
import requests

# Functions to find the closest location
def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the distance (in kilometers) between two sets of latitude and longitude coordinates.
    """
    R = 6371  # Radius of the Earth in kilometers

    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance

def find_closest_location(input_location, locations):
    """
    Find the closest location to the input location from a list of locations.
    """
    min_distance = float('inf')
    closest_location = None

    input_lat, input_lon = input_location[3], input_location[4]

    for location in locations:
        lat, lon = map(float, location[3:5])

        distance = calculate_distance(input_lat, input_lon, lat, lon)

        if distance < min_distance:
            min_distance = distance
            closest_location = location

    return closest_location, min_distance

def read_locations(file_path):
    locations = []
    with open(file_path, 'r') as file:
        for line in file:
            location_data = line.strip()[1:-1].split(", ")
            locations.append(location_data)
    return locations

def load_api_keys(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file]
    
def get_coordinates(api_key, address):
    url = "https://dev.virtualearth.net/REST/v1/Locations"
    params = {
        "q": address,
        "key": api_key
    }
    response = requests.get(url, params=params)
    data = response.json()

    if response.status_code == 200 and data["statusCode"] == 200:
        resources = data["resourceSets"][0]["resources"]
        if resources:
            point = resources[0]["point"]
            latitude = point["coordinates"][0]
            longitude = point["coordinates"][1]
            return latitude, longitude
    return None