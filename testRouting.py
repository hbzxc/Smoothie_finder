import math
import folium
import geocoder

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the distance (in kilometers) between two sets of latitude and longitude coordinates.
    """
    R = 6371  # Radius of the Earth in kilometers

    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(math.radians, [lat1, lon1, lat2, lon2])

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

    # Create a Folium map centered between the user's location and the closest location
    center_lat = (user_lat + float(lat)) / 2
    center_lon = (user_lon + float(lon)) / 2
    m = folium.Map(location=[center_lat, center_lon])

    # Add the user's location marker
    folium.Marker(location=[user_lat, user_lon], popup='User Location', icon=folium.Icon(color='blue')).add_to(m)

    # Add the closest location marker
    folium.Marker(location=[float(lat), float(lon)], popup=f'{town_name}, {state_abbreviation}', icon=folium.Icon(color='red')).add_to(m)

    # Add a line between the user's location and the closest location
    folium.PolyLine(locations=[[user_lat, user_lon], [float(lat), float(lon)]], color='red').add_to(m)

    # Fit the bounds of the map to show both locations
    bounds = [[user_lat, user_lon], [float(lat), float(lon)]]
    m.fit_bounds(bounds)

    # Add map key with distance
    map_key_html = f"""
    <div style="position: fixed; top: 10px; right: 10px; background-color: white; padding: 10px; border: 1px solid black; z-index: 9999;">
        <h3>Distance to Smoothie</h3>
        <p><strong>Distance:</strong> {distance:.2f} km</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(map_key_html))

    # Display the map
    m.save('route_map.html')
    print("Map saved as 'route_map.html'.")
else:
    print("No locations found.")
