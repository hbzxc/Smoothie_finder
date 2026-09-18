import os
from flask import Flask, render_template, request, jsonify
from smoothi_finder_fcns import *
from db import (
    FRANCHISE_KEYS,
    count_locations,
    ensure_db,
    find_closest_in_db,
    get_meta,
    markers_for_franchise,
)
import folium
import geocoder

app = Flask(__name__)
app.static_folder = 'static'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = ensure_db(BASE_DIR)

# Azure Maps primary key: flask_app/api.txt (first line) or AZURE_MAPS_KEY env var.
api_keys = load_api_keys(os.path.join(BASE_DIR, 'api.txt'))
azure_maps_key = api_keys[0] if api_keys else os.environ.get('AZURE_MAPS_KEY', '').strip()

FRANCHISE_FORM = {
    'Jamba Juice': FRANCHISE_KEYS['jamba'],
    'Tropical Smoothie': FRANCHISE_KEYS['tropical'],
    'Smoothie King': FRANCHISE_KEYS['king'],
}


def franchise_updated(franchise: str) -> str:
    return get_meta(DB_PATH, f'updated:{franchise}', 'unknown')


@app.route('/', methods=['GET', 'POST'])
def index():
    # Keep the homepage light: counts + timestamps only. Marker data loads on demand.
    return render_template(
        'index.html',
        total_location=count_locations(DB_PATH, FRANCHISE_KEYS['tropical']),
        total_location_jamba=count_locations(DB_PATH, FRANCHISE_KEYS['jamba']),
        total_location_smoothie_king=count_locations(DB_PATH, FRANCHISE_KEYS['king']),
        tropical_updated=franchise_updated(FRANCHISE_KEYS['tropical']),
        jamba_updated=franchise_updated(FRANCHISE_KEYS['jamba']),
        smoothie_king_updated=franchise_updated(FRANCHISE_KEYS['king']),
    )


@app.route('/api/locations/<franchise_key>')
def api_locations(franchise_key):
    franchise = FRANCHISE_KEYS.get(franchise_key)
    if not franchise:
        return jsonify({'error': 'Unknown franchise'}), 404
    return jsonify({
        'franchise': franchise,
        'updated': franchise_updated(franchise),
        'locations': markers_for_franchise(DB_PATH, franchise),
    })


@app.route('/route_to', methods=['POST'])
def route_to():
    franchise = request.form['franchise']
    user_input = request.form['user_input']

    franchise_filter = FRANCHISE_FORM.get(franchise)  # None => search all brands

    lat = request.form['lat']
    lon = request.form['lon']

    # Prefer map-click coordinates (0 Azure geocode calls). Only geocode when needed.
    if lat == '' or lon == '':
        lat = 0
        lon = 0
        if user_input != '':
            coords = get_coordinates(user_input, api_key=azure_maps_key)
            if coords:
                lat, lon = coords
    else:
        lat = float(lat)
        lon = float(lon)

    closest_location, distance = find_closest_in_db(
        DB_PATH, lat, lon, franchise=franchise_filter
    )
    if closest_location is None:
        return "No locations found in database.", 404

    state_abbreviation = closest_location[0]
    town_name = closest_location[1]
    address = closest_location[2]
    target_lat = closest_location[3]
    target_lon = closest_location[4]
    store_hours = closest_location[5] if len(closest_location) > 6 else None
    franchise_name = closest_location[-1]

    center_lat = (float(lat) + float(target_lat)) / 2
    center_lon = (float(lon) + float(target_lon)) / 2
    m = folium.Map(location=[center_lat, center_lon])

    route = get_driving_route(lat, lon, target_lat, target_lon, azure_maps_key=azure_maps_key)
    if route:
        tripDistance = route["distance_km"]
        traffic = route["traffic"]
        Travel_Time = format_travel_time(route["duration_seconds"])
        folium.PolyLine(locations=route["coordinates"], color='green').add_to(m)
    else:
        tripDistance = "No land route found"
        traffic = "N/A"
        Travel_Time = "N/A"

    folium.Marker(location=[float(lat), float(lon)], popup='User Location', icon=folium.Icon(color='blue')).add_to(m)

    popup_bits = [f'{town_name}, {state_abbreviation}', address]
    if store_hours:
        popup_bits.append(f'Hours: {store_hours}')
    folium.Marker(
        location=[float(target_lat), float(target_lon)],
        popup=' | '.join(popup_bits),
        icon=folium.Icon(color='red'),
    ).add_to(m)

    folium.PolyLine(
        locations=[[float(lat), float(lon)], [float(target_lat), float(target_lon)]],
        color='red',
    ).add_to(m)

    bounds = [[float(lat), float(lon)], [float(target_lat), float(target_lon)]]
    m.fit_bounds(bounds)

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
        <b>Store Hours:</b><br>
        {}<br>
    </div>
    """.format(
        franchise_name,
        round(distance, 2),
        tripDistance,
        traffic,
        Travel_Time,
        store_hours or "N/A",
    )
    m.get_root().html.add_child(folium.Element(map_key_html))

    route_map = m._repr_html_()
    return render_template('map.html', map_html=route_map, franchise=franchise)


@app.route('/current_location')
def get_current_location():
    ip_addr = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    g = geocoder.ip(ip_addr)
    if g.latlng:
        return jsonify({'lat': g.latlng[0], 'lon': g.latlng[1]})
    return jsonify({'error': 'Unable to retrieve current location'})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
