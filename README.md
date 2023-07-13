# Smoothie
Find a smoothie store near you

------- Parsing the store location information -------
These scripts will parse infromation from the following websites
"https://locations.tropicalsmoothiecafe.com/index.html"
"https://locations.jamba.com/"
"https://locations.smoothieking.com/site-map/us/"

it will grab address information for all of their locations.

--- The first script to run is: SmoothiePls.py ---

it uses beautiful soup to parse the website creating a lists called JambaOut.txt, SmoothieK_KingOut.txt and tropical_smoothieOut.txt

The result should be a list containing the state, town name and street address for every location.
['al', 'auburn', '316-west-magnolia-ave']

--- The next script: AddCord.py ---

This will use the Bing maps rest api to get latitude and longitude using geocoding.

The coordinates are then added to the original input and the result will be an entry that contains state, town name, streed address and location coordinates.
['al', 'auburn', '316-west-magnolia-ave', 32.606815, -85.486015]

Now that all the data is collected it just needs to be shown.

This is done using leaflet to display the coordinates on a map and uses flask to run the web application.
Again Bing is used for route finding between two points.
Currrently the process to calculate the closest store to the user is done using a straight line.
It is done this way as to reduce the number of api calls since factoring in route information would require sending a request for every coordinate. A straight line can be calculated on my side.

------- Using the Route finder -------

A user can choose a point on the map or input their address.
Then select a specific franchise to be routed to or choose to be taken to the closest one reguardless of company.

If no driving route is found it will show a map with a straight line path to the destination and the distance to it.

If a driving route is found it will show both the straight line path and a land route with a time estimate and traffic prediction

If no starting selection is made the default start point is 

Markers to show all the locations can be toggled on and off by clicking their respective "Show" button
They are clustered using leaflet marker clusters https://github.com/Leaflet/Leaflet.markercluster with custom styling