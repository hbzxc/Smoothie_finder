import requests
from SmoothieIngredients import*
from bs4 import BeautifulSoup

# URL of the webpage to scrape
url = "https://locations.tropicalsmoothiecafe.com/index.html"

single_test = False

Location_list = []

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

# Send a GET request to the webpage
response = requests.get(url)

# Create a BeautifulSoup object to parse the HTML content
soup = BeautifulSoup(response.content, "html.parser")

# Find all the <a> tags containing the state names
state_tags = soup.find_all("a", class_="Directory-listLink")

# Extract the text content from the <a> tags and filter for US state names
found_states = [tag.text for tag in state_tags if tag.text in [state[0] for state in us_states]]

if single_test:
    abbreviation = [abbrev for name, abbrev in us_states if name == found_states[29]][0]
    state_abbreviation(url, abbreviation, Location_list)

if single_test == False:
    for state in found_states:
        abbreviation = [abbrev for name, abbrev in us_states if name == state][0]
        state_abbreviation(url, abbreviation, Location_list)

export_list_to_text_file(Location_list, "textOut.txt")

