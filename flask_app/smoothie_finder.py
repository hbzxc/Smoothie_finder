from flask import Flask, render_template, request, jsonify
from flask_assets import Bundle, Environment
from smoothi_finder_fcns import*
import folium
import geocoder
import urllib.request
import json

app = Flask(__name__)

# Initialize Flask-Assets
assets = Environment(app)

# Define asset bundles
js_bundle = Bundle(
    'https://unpkg.com/leaflet@1.7.1/dist/leaflet.js',
    'https://unpkg.com/leaflet.locatecontrol/dist/L.Control.Locate.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.1/leaflet.markercluster.js'
)
css_bundle = Bundle(
    'https://unpkg.com/leaflet@1.7.1/dist/leaflet.css',
    'https://unpkg.com/leaflet.locatecontrol/dist/L.Control.Locate.min.css',
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.1/MarkerCluster.css',
    'https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.1/MarkerCluster.Default.css'
)

# Register asset bundles
assets.register('js_all', js_bundle)
assets.register('css_all', css_bundle)

app.static_folder = 'static'

# Read locations from files
tropical_smoothie_locations = read_locations('TropicalLocations.txt')
tropical_smoothie_locations_loc = [item + ["Tropical Smoothie"] for item in tropical_smoothie_locations]
jamba_locations = read_locations('Jamba_Locations.txt')
jamba_locations_loc = [item + ["Jamba Juice"] for item in jamba_locations]
smoothie_king_locations = read_locations('Smoothie_King_Locations.txt')
smoothie_king_locations_loc = [item + ["Smoothie King"] for item in smoothie_king_locations]

all_locations = tropical_smoothie_locations_loc + jamba_locations_loc + smoothie_king_locations_loc

# Count the number of locations
number_of = len(tropical_smoothie_locations)
number_of_jamba = len(jamba_locations)
number_of_smoothie_king = len(smoothie_king_locations)

# Extract smoothie locations
smoothie_locations = [coordinate[-2:] for coordinate in tropical_smoothie_locations]
smoothie_locations_jamba = [coordinate[-2:] for coordinate in jamba_locations]
smoothie_locations_smoothie_king = [coordinate[-2:] for coordinate in smoothie_king_locations]

api_keys = load_api_keys('api.txt')

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html', input_coordinates = smoothie_locations, input_coordinates_jamba = smoothie_locations_jamba, input_coordinates_smoothie_king = smoothie_locations_smoothie_king, total_location = number_of, total_location_jamba = number_of_jamba, total_location_smoothie_king = number_of_smoothie_king)

@app.route('/route_to', methods=['POST'])
def route_to():
    # Use Bing Maps to find a route
    bingMapsKey = api_keys[0]

    franchise = request.form['franchise']
    user_input= request.form['user_input']

    if franchise == 'Jamba Juice':
        route_settings = jamba_locations_loc
    elif franchise == 'Tropical Smoothie':
        route_settings = tropical_smoothie_locations_loc
    elif franchise == 'Smoothie King':
        route_settings = smoothie_king_locations_loc
    else:
        route_settings = all_locations
    
    lat = request.form['lat']
    lon = request.form['lon']
    
    #if there is no input default to [0,0]
    if lat == '' or lon =='':
        lat = 0
        lon = 0
        if user_input != '':
            lat,lon = get_coordinates(bingMapsKey, user_input)

    closest_location, distance = find_closest_location(['', '', '', lat, lon], route_settings)
    state_abbreviation, town_name, address, target_lat, target_lon, franchise_name = closest_location

    # Create a Folium map centered between the user's location and the closest location
    center_lat = (float(lat) + float(target_lat)) / 2
    center_lon = (float(lon) + float(target_lon)) / 2
    m = folium.Map(location=[center_lat, center_lon])

    routeUrl = f"http://dev.virtualearth.net/REST/V1/Routes/Driving?wp.0={lat},{lon}&wp.1={target_lat},{target_lon}&routePathOutput=Points&key={bingMapsKey}"
    try:
        response = urllib.request.urlopen(routeUrl)
        result = json.loads(response.read().decode(encoding="utf-8"))

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
        <h4>Distance to {}</h4>
        <p><strong>Distance as the crow flies:</strong> {} km</p>
        <b>Driving Route Information:</b><br>
        Distance: {} km<br>
        Traffic Level: {}<br>
        Travel Time: {}<br>
        
    </div>
    """.format(franchise_name,round(distance,2),tripDistance, traffic, Travel_Time)
    m.get_root().html.add_child(folium.Element(map_key_html))

    # Save the map as HTML
    route_map = m._repr_html_()
    return render_template('map.html', map_html=route_map, franchise=franchise)

@app.route('/current_location')
def get_current_location():
    ip_addr = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    g = geocoder.ip(ip_addr)
    if g.latlng:
        return jsonify({'lat': g.latlng[0], 'lon': g.latlng[1]})
    else:
        return jsonify({'error': 'Unable to retrieve current location'})


if __name__ == '__main__':
    app.run(debug=False)