from flask import Flask, render_template, request, jsonify
from flask_assets import Bundle, Environment
import folium
import geocoder
import math
import urllib.request
import json

app = Flask(__name__)

# Initialize Flask-Assets
assets = Environment(app)

# Define asset bundles
js_bundle = Bundle(
    'https://unpkg.com/leaflet@1.7.1/dist/leaflet.js',
    'https://unpkg.com/leaflet.locatecontrol/dist/L.Control.Locate.min.js'
)
css_bundle = Bundle(
    'https://unpkg.com/leaflet@1.7.1/dist/leaflet.css',
    'https://unpkg.com/leaflet.locatecontrol/dist/L.Control.Locate.min.css'
)

# Register asset bundles
assets.register('js_all', js_bundle)
assets.register('css_all', css_bundle)

app.static_folder = 'static'

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

# Setup the locations
locations = []
with open('TropicalLocations.txt', 'r') as file:
    for line in file:
        location_data = line.strip()[1:-1].split(", ")
        locations.append(location_data)

apiKeys = []
with open('api.txt', 'r') as file:
    for line in file:
        apiKeys.append(line)

smoothie_loactions = []
for coordinate in locations:
    #print(coordinate[-2:])
    smoothie_loactions.append(coordinate[-2:])

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        lat = request.form['lat']
        lon = request.form['lon']
        closest_location, distance = find_closest_location(['', '', '', lat, lon], locations)
        state_abbreviation, town_name, address, target_lat, target_lon = closest_location

        # Create a Folium map centered between the user's location and the closest location
        center_lat = (float(lat) + float(target_lat)) / 2
        center_lon = (float(lon) + float(target_lon)) / 2
        m = folium.Map(location=[center_lat, center_lon])

        # Use Bing Maps to find a route
        bingMapsKey = apiKeys[0]

        routeUrl = f"http://dev.virtualearth.net/REST/V1/Routes/Driving?wp.0={lat},{lon}&wp.1={target_lat},{target_lon}&routePathOutput=Points&key={bingMapsKey}"
        try:
            response = urllib.request.urlopen(routeUrl)
            result = json.loads(response.read().decode(encoding="utf-8"))
            print("loading request")

            resources = result["resourceSets"][0]["resources"][0]
            itineraryItems = resources["routeLegs"][0]["itineraryItems"]
            plotPoints = resources.get('routePath', {}).get('line', {}).get('coordinates')
            tripDistance = round(resources["travelDistance"],2)
            traffic = resources["trafficCongestion"]
            tripTime = resources["travelDuration"]
            bbox = resources["bbox"]
            # Convert trip time to hours and minutes
            trip_hours, remainder = divmod(tripTime, 3600)
            trip_minutes, _ = divmod(remainder, 60)

            #account for hour or hours
            if trip_hours == 1:
                Travel_Time = f"{trip_hours} hour and {trip_minutes} minutes"
            elif trip_hours == 0:
                Travel_Time = f"{trip_minutes} minutes"
            else:
                Travel_Time = f"{trip_hours} hours and {trip_minutes} minutes"
            
            # Append the directions to the list
            directions = [item["instruction"]["text"] for item in itineraryItems]

            # Set the plot points
            coordinates = [(point[0], point[1]) for point in plotPoints] if plotPoints else []

            # Create a line connecting the points

            folium.PolyLine(locations=coordinates, color='green').add_to(m)
        except:
            print("no land route found")
            tripDistance = "No land route found"
            traffic = "N/A"
            Travel_Time = "N/A"

        # Add the user's location marker
        folium.Marker(location=[float(lat), float(lon)], popup='User Location', icon=folium.Icon(color='blue')).add_to(m)

        # Add the closest location marker
        folium.Marker(location=[float(target_lat), float(target_lon)], popup=f'{town_name}, {state_abbreviation}, {address}', icon=folium.Icon(color='red')).add_to(m)

        # Add a line between the user's location and the closest location
        folium.PolyLine(locations=[[float(lat), float(lon)], [float(target_lat), float(target_lon)]], color='red').add_to(m)

        # Fit the bounds of the map to show both locations
        bounds = [[float(lat), float(lon)], [float(target_lat), float(target_lon)]]
        m.fit_bounds(bounds)

        # Add map key with distance and phrase
        map_key_html = """
        <div style="
            position: fixed; 
            bottom: 10px; 
            left: 10px; 
            background-color: white; 
            padding: 10px; 
            border: 1px solid black; 
            z-index: 9999;
        ">
            <h3>Distance to Smoothie</h3>
            <p><strong>Distance as the crow flies:</strong> {} km</p>
            <b>Driving Route Information:</b><br>
            Distance: {} km<br>
            Traffic Level: {}<br>
            Travel Time: {}
            
        </div>
        """.format(round(distance,2),tripDistance, traffic, Travel_Time)
        m.get_root().html.add_child(folium.Element(map_key_html))

        # Save the map as HTML
        route_map = m._repr_html_()
        return render_template('map.html', map_html=route_map)
    return render_template('index.html', input_coordinates = smoothie_loactions)


@app.route('/current_location')
def get_current_location():
    g = geocoder.ip('me')
    if g.latlng:
        return jsonify({'lat': g.latlng[0], 'lon': g.latlng[1]})
    else:
        return jsonify({'error': 'Unable to retrieve current location'})


if __name__ == '__main__':
    app.run(debug=True)
