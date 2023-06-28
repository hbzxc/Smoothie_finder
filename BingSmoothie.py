import requests
from bs4 import BeautifulSoup

url = "https://locations.tropicalsmoothiecafe.com"

response = requests.get(url)

soup = BeautifulSoup(response.content, "html.parser")

locations = soup.find_all("a", class_="Directory-listLink")

for location in locations:
    print(location.text.strip())