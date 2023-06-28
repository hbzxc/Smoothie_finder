import folium

# Create a Folium map
m = folium.Map(location=[40.712, -74.227], zoom_start=12)

# Define the route coordinates
route_coordinates = [
    [40.712, -74.227],
    [40.713, -74.228],
    [40.714, -74.229],
    [40.715, -74.230],
    [40.716, -74.231]
]

# Add the route line to the map
route_line = folium.PolyLine(locations=route_coordinates, color='red')
route_line.add_to(m)

# Define the turn information
turn_information = [
    {'turn': 'Turn left onto Main St'},
    {'turn': 'Continue straight on Main St'},
    {'turn': 'Turn right onto Elm St'},
    {'turn': 'Continue straight on Elm St'},
    {'turn': 'Arrive at your destination'}
]

# Add markers with popups for turn information
for i, turn_info in enumerate(turn_information):
    lat, lon = route_coordinates[i]
    turn = turn_info['turn']
    marker = folium.Marker(location=[lat, lon], popup=turn)
    marker.add_to(m)

# Save the map as an HTML file
m.save('turn_by_turn_directions.html')
