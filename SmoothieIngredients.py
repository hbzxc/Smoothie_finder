import requests
from bs4 import BeautifulSoup

# Toggle flag for print statements
enable_prints = False

def state_abbreviation(base_url, state_abbreviation, Location_list):
    stripped_url = base_url.split("index")
    url = stripped_url[0] + state_abbreviation.lower()
    town_names(url, Location_list)

def town_names(state_url, Location_list):
    response = requests.get(state_url)
    soup = BeautifulSoup(response.content, "html.parser")

    locations = soup.select("a.Directory-listLink")

    for location in locations:
        state_raw = location.get_text(strip=True)
        if enable_prints:
            print("This is the town name:", state_raw)

        #if there are spaces in a town name replace them with a dash to confrom to the format
        state = state_raw.replace(" ", "-")
        address = location["href"].split("/")
        try:
            town = address[2]
            if enable_prints:
                print("This is the address:", town)
            Location_list.append([address[0], address[1], town])
        except IndexError:
            if enable_prints:
                print("---------Multiple locations found---------")
            multiple_locations(state_url + "/" + state.lower(), Location_list)
            if enable_prints:
                print("----------Multiple locations end----------")

def multiple_locations(multi_url, Location_list):

    try:
        response = requests.get(multi_url)
        soup = BeautifulSoup(response.content, "html.parser")

        locations = soup.select("a.Teaser-titleLink")
        for location in locations:
            address = location["href"].split("/")
            town = address[3]
            if enable_prints:
                print("These are the addresses:", town)
            Location_list.append([address[1], address[2], town])
    except:
        print("invalid url for: "+ multi_url)

def export_list_to_text_file(lst, file_path):
    with open(file_path, "w") as file:
        for item in lst:
            file.write(str(item) + "\n")
