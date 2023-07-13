# scrape smoothie websites to get addresses and output as a list
import requests
from SmoothieIngredients import*
from bs4 import BeautifulSoup

# URL of the webpages to scrape
smoothie = [
    ("tropical_smoothie", "https://locations.tropicalsmoothiecafe.com/index.html"),
    ("Jamba", "https://locations.jamba.com/"),
    ("Smoothie_King" , "https://locations.smoothieking.com/site-map/us/")
    ]

enable_prints = True
single_test = False

# List of US states and their abbreviations
us_states = [
    ("Alabama", "AL"),
    ("Alaska", "AK"),
    ("Arizona", "AZ"),
    ("Arkansas", "AR"),
    ("California", "CA"),
    ("Colorado", "CO"),
    ("Connecticut", "CT"),
    ("Delaware", "DE"),
    ("Florida", "FL"),
    ("Georgia", "GA"),
    ("Hawaii", "HI"),
    ("Idaho", "ID"),
    ("Illinois", "IL"),
    ("Indiana", "IN"),
    ("Iowa", "IA"),
    ("Kansas", "KS"),
    ("Kentucky", "KY"),
    ("Louisiana", "LA"),
    ("Maine", "ME"),
    ("Maryland", "MD"),
    ("Massachusetts", "MA"),
    ("Michigan", "MI"),
    ("Minnesota", "MN"),
    ("Mississippi", "MS"),
    ("Missouri", "MO"),
    ("Montana", "MT"),
    ("Nebraska", "NE"),
    ("Nevada", "NV"),
    ("New Hampshire", "NH"),
    ("New Jersey", "NJ"),
    ("New Mexico", "NM"),
    ("New York", "NY"),
    ("North Carolina", "NC"),
    ("North Dakota", "ND"),
    ("Ohio", "OH"),
    ("Oklahoma", "OK"),
    ("Oregon", "OR"),
    ("Pennsylvania", "PA"),
    ("Rhode Island", "RI"),
    ("South Carolina", "SC"),
    ("South Dakota", "SD"),
    ("Tennessee", "TN"),
    ("Texas", "TX"),
    ("Utah", "UT"),
    ("Vermont", "VT"),
    ("Virginia", "VA"),
    ("Washington", "WA"),
    ("West Virginia", "WV"),
    ("Wisconsin", "WI"),
    ("Wyoming", "WY")
]

for smoothies in smoothie:
    Location_list = []

    if enable_prints:
        print(f"---------Now Checking {smoothies[0]}---------")

    # Send a GET request to the webpage
    response = requests.get(smoothies[1])

    # Create a BeautifulSoup object to parse the HTML content
    soup = BeautifulSoup(response.content, "html.parser")

    # Find all the <a> tags containing the state names and check if it is the smoothie king website
    state_tags = soup.find_all("a", class_="Directory-listLink")
    if state_tags == []:
        for li in soup.find_all('li'):
            state_tags.append(li)
            King = True
    else:
        King = False

    #print("found all a tags")
    #print(state_tags)

    # Extract the text content from the <a> tags and filter for US state names
    found_states = [tag.text for tag in state_tags if tag.text in [state[0] for state in us_states]]

    #for testing single output
    if single_test:
        abbreviation = [abbrev for name, abbrev in us_states if name == found_states[0]][0]
        state_abbreviation(smoothies[1], abbreviation, Location_list, King)
        #print(smoothies[1])
        #print(abbreviation)
        #print(Location_list)

    if single_test == False:
        for state in found_states:
            abbreviation = [abbrev for name, abbrev in us_states if name == state][0]
            state_abbreviation(smoothies[1], abbreviation, Location_list, King)

    name_out = str(smoothies[0])+"Out.txt"
    export_list_to_text_file(Location_list, name_out)
