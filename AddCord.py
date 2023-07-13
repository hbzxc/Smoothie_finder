import requests
import os
from SmoothieIngredients import*

Coord_out = []

debug = True

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
#extract from the api file
apiKeys = []
with open('api.txt', 'r') as file:
    for line in file:
        apiKeys.append(line)

#set the first item as the bing api key
bingAPI = apiKeys[0]

#get a list of all txt files in the current directory
current_directory = os.getcwd()
txt_files = [file for file in os.listdir(current_directory) if file.endswith('.txt')]

#skip the api file and check the other text files for locations
for file in txt_files:
    if file != "api.txt":

        #set the name of the output file
        out_name = file.split("Out")[0]+"_Locations.txt"

        # Read locations from the input file
        locations = read_locations_from_file(file)

        # Process each location and get the coordinates
        for state_abbreviation, town_name, address in locations:
            full_address = f"{address}, {town_name}, {state_abbreviation}, United States"

            if "-" in town_name:
                if debug == True:
                    print("This town contains a hypen in its name: "+town_name)
            coordinates = get_coordinates(bingAPI, full_address)
            if coordinates:
                latitude, longitude = coordinates
                if debug == True:
                    print(f"Location: {town_name}, {state_abbreviation}")
                    print(f"Address: {address}")
                    print(f"Latitude: {latitude}")
                    print(f"Longitude: {longitude}")
                Coord_out.append([state_abbreviation, town_name, address, latitude, longitude])
            else:
                print(f"Coordinates not found for: {town_name}, {state_abbreviation}")

        export_list_to_text_file(Coord_out, out_name)

