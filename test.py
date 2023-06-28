import math
import geocoder
import requests
import folium
import urllib.request
import json
import matplotlib.pyplot as plt

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the distance (in kilometers) between two sets of latitude and longitude coordinates.
    """
    R = 6371  # Radius of the Earth in kilometers

    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

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

    for location in locations:
        lat = float(location[3])
        lon = float(location[4])

        distance = calculate_distance(input_location[3], input_location[4], lat, lon)

        if distance < min_distance:
            min_distance = distance
            closest_location = location

    return closest_location, min_distance

def plot_route(start_latitude, start_longitude, end_latitude, end_longitude):
    """
    Plot a route on Bing Maps between two sets of latitude and longitude coordinates.
    """
    bingMapsKey = "AiLQA37u7FIMRMLkFuTAwl1wl0yv-zsQoVC1Dh7lIQjMeG7zrHN0xL86gqyAMuvN"

    routeUrl = "http://dev.virtualearth.net/REST/V1/Routes/Driving?wp.0=" + str(start_latitude) + "," + str(start_longitude) + "&wp.1=" + str(end_latitude)+","+str(end_longitude) + "&routePathOutput=Points" "&key=" + bingMapsKey

    request = urllib.request.Request(routeUrl)
    response = urllib.request.urlopen(request)

    r = response.read().decode(encoding="utf-8")
    result = json.loads(r)
    resources = result["resourceSets"][0]["resources"][0]
    itineraryItems = resources["routeLegs"][0]["itineraryItems"]
    plotPoints = resources['routePath']['line']['coordinates']
    itineraryItems = resources["routeLegs"][0]["itineraryItems"]
    tripDistance = resources["travelDistance"]
    traffic = resources["trafficCongestion"]
    tripTime = resources["travelDuration"]
    bbox = resources["bbox"]
    print(bbox)

    directions = []

    for item in itineraryItems:
        directions.append(item["instruction"]["text"])

    print("This is the trip time: "+str(tripTime))
    print("This is the trip distance: "+str(tripDistance))
    print("This is the expected traffic: "+str(traffic))
    print("These are the directions:")
    for direction in directions:
        print(direction)
    #print(resource_set["resource"])

    #route_data = json.loads(resource_set["resources"])

    

    # Extract the coordinates from the route path
    if plotPoints is None:
        print("No route path found.")
        return

    coordinates = []
    for point in plotPoints:
        lat = point[0]
        lon = point[1]
        coordinates.append((lat, lon))

    #set the bounding box
    southwest = [bbox[0], bbox[1]]
    northeast = [bbox[2], bbox[3]]

    #get the center of the coordiantes
    center = [(southwest[0] + northeast[0]) / 2, (southwest[1] + northeast[1]) / 2]

    # Plot the route
    m = folium.Map(center)

    #set bounds
    m.fit_bounds([southwest, northeast])

    # Plot the points as markers on the map
    for i, point in enumerate(coordinates):
        turn = directions[i]
        folium.Marker(location=point, popup=turn).add_to(m)

    # Create a line connecting the points
    folium.PolyLine(locations=coordinates, color='red').add_to(m)

    # Create a custom map control for the map key
    map_key = """
        <div style="
            position: fixed;
            bottom: 50px;
            left: 50px;
            z-index: 1000;
            background-color: white;
            padding: 10px;
            border: 1px solid black;
            font-family: Arial, sans-serif;
            font-size: 12px;
        ">
            <b>Route Information:</b><br>
            Distance: {}<br>
            Traffic Level: {}<br>
            Travel Time: {}
        </div>
    """.format(tripDistance, traffic, tripTime)

    # Add the custom map control to the map
    m.get_root().html.add_child(folium.Element(map_key))

    m.save('route_map.html')



# Get the user's current location
g = geocoder.ip('me')
user_lat, user_lon = g.latlng

# Read locations from the text file
locations = []
with open('TropicalLocations.txt', 'r') as file:
    for line in file:
        location_data = line.strip()[1:-1].split(", ")
        locations.append(location_data)

# Find the closest location to the user's location
closest_location, distance = find_closest_location(['', '', '', user_lat, user_lon], locations)

if closest_location:
    state_abbreviation, town_name, address, lat, lon = closest_location
    print(f"The closest location is {town_name}, {state_abbreviation} ({address}), {distance:.2f} km away.")

    # Plot the route between user's location and the closest location
    plot_route(user_lat, user_lon, float(lat), float(lon))
else:
    print("No locations found.")
