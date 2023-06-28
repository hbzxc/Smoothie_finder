import math
import geocoder
import socket

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the Haversine distance between two points in kilometers.
    """
    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    radius = 6371  # Radius of the Earth in kilometers
    distance = radius * c

    return distance

def calculate_closest_point(target_lat, target_lon, points):
    """
    Calculate the closest point to the target coordinates from a list of points.
    """
    closest_point = None
    closest_distance = float("inf")  # Initialize with a large value

    for point in points:
        lat, lon = point[3], point[4]  # Extract latitude and longitude from the point
        distance = haversine_distance(target_lat, target_lon, lat, lon)

        if distance < closest_distance:
            closest_distance = distance
            closest_point = point

    return closest_point, closest_distance

def read_coordinates_from_file(file_path):
    with open(file_path, "r") as file:
        lines = file.readlines()
    
    coordinates = []
    for line in lines:
        location_data = line.strip()[1:-1].split(", ")
        state_abbreviation = location_data[0].strip("'")
        town_name = location_data[1].strip("'")
        address = location_data[2].strip("'")
        latitude = float(location_data[3].strip("'"))
        longitude = float(location_data[4].strip("'"))
        coordinates.append((state_abbreviation, town_name, address, latitude, longitude))
    
    return coordinates

def get_ip_address():
    """
    Get the user's current IP address.
    """
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    return ip_address

def get_location_from_ip(ip_address):
    """
    Get the location coordinates based on the IP address.
    """
    g = geocoder.ip(ip_address)
    if g.latlng:
        latitude, longitude = g.latlng
        return latitude, longitude
    return None

# Get current location coordinates
current_ip = get_ip_address()
print("This is the current ip: "+current_ip)
target_latitude, target_longitude = get_location_from_ip(current_ip)

# Example usage
#target_latitude = 34.1020383  # Latitude of the target point
#target_longitude = -118.3409414  # Longitude of the target point10 S VAN NESS AVE, SAN FRANCISCO, CA  94103, UNITED STATES
input_file = "LocAndCord.txt"  # File path to the input text file

# Read coordinates from the input file
coordinates = read_coordinates_from_file(input_file)

# Calculate the closest point
closest_point, closest_distance = calculate_closest_point(target_latitude, target_longitude, coordinates)

print("Target Coordinates:")
print(f"Latitude: {target_latitude}")
print(f"Longitude: {target_longitude}")
print()
print("Closest Point:")
print(f"State Abbreviation: {closest_point[0]}")
print(f"Town Name: {closest_point[1]}")
print(f"Address: {closest_point[2]}")
print(f"Latitude: {closest_point[3]}")
print(f"Longitude: {closest_point[4]}")
print(f"Distance: {closest_distance:.2f} km")
