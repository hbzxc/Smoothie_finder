import requests
from SmoothieIngredients import*

Coord_out = []

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

def read_locations_from_file(file_path):
    with open(file_path, "r") as file:
        lines = file.readlines()
    
    locations = []
    for line in lines:
        location_data = line.strip()[1:-1].split(", ")
        state_abbreviation = location_data[0].strip("'")
        town_name = location_data[1].strip("'")
        address = location_data[2].strip("'")
        locations.append((state_abbreviation, town_name, address))
    
    return locations

# Bing Maps API key
api_key = "AiLQA37u7FIMRMLkFuTAwl1wl0yv-zsQoVC1Dh7lIQjMeG7zrHN0xL86gqyAMuvN"

# File path to the input text file
input_file = "textOut.txt"

# Read locations from the input file
locations = read_locations_from_file(input_file)

# Process each location and get the coordinates
for state_abbreviation, town_name, address in locations:
    full_address = f"{address}, {town_name}, {state_abbreviation}, United States"

    if "-" in town_name:
        print("This town contains a hypen in its name: "+town_name)
        coordinates = get_coordinates(api_key, full_address)
        if coordinates:
            latitude, longitude = coordinates
            print(f"Location: {town_name}, {state_abbreviation}")
            print(f"Address: {address}")
            print(f"Latitude: {latitude}")
            print(f"Longitude: {longitude}")
            print()
            Coord_out.append([state_abbreviation, town_name, address, latitude, longitude])
        else:
            print(f"Coordinates not found for: {town_name}, {state_abbreviation}")
            print()

export_list_to_text_file(Coord_out, "LocAndCordExtra.txt")
