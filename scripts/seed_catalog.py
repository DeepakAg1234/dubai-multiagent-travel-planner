"""Named rows for the curated dataset.

Coordinates are filled by scripts/curate_seed.py. Prices are verified only when
docs/research.md checked an official figure. Everything else is an estimate.
"""

from __future__ import annotations

# name | category | area | tags | min | max | price class | crowd | minutes | hours | indoor | timed | status | url | query
PLACES = """
Al Fahidi Historical Neighbourhood | neighbourhood | Old Dubai | culture | 0 | 0 | estimated | low | 90 | always | 0 | 0 | open | | Al Fahidi Historical Neighbourhood Dubai
Dubai Museum | museum | Old Dubai | culture | 3 | 30 | estimated | medium | 75 | 09-17 | 1 | 0 | open | | Dubai Museum Al Fahidi Fort
Sheikh Mohammed Centre for Cultural Understanding | museum | Old Dubai | culture | 0 | 0 | estimated | low | 60 | 09-17 | 1 | 0 | open | | Sheikh Mohammed Centre for Cultural Understanding Dubai
Coffee Museum | museum | Old Dubai | culture | 0 | 0 | estimated | low | 45 | 09-17 | 1 | 0 | open | | Coffee Museum Al Fahidi Dubai
Coin Museum | museum | Old Dubai | culture | 0 | 0 | estimated | low | 40 | 09-17 | 1 | 0 | open | | Coin Museum Dubai
Al Shindagha Museum | museum | Old Dubai | culture | 20 | 50 | estimated | medium | 90 | 10-22 | 1 | 0 | open | | Al Shindagha Museum Dubai
Gold Souk | market | Old Dubai | culture,shopping | 0 | 0 | estimated | medium | 60 | 10-22 | 0 | 0 | open | | Gold Souk Deira Dubai
Spice Souk | market | Old Dubai | culture,shopping,food | 0 | 0 | estimated | medium | 45 | 10-22 | 0 | 0 | open | | Spice Souk Deira Dubai
Textile Souk | market | Old Dubai | culture,shopping | 0 | 0 | estimated | medium | 45 | 10-22 | 0 | 0 | open | | Textile Souk Bur Dubai
Heritage Village | neighbourhood | Old Dubai | culture | 0 | 0 | estimated | low | 60 | 09-21 | 0 | 0 | open | | Heritage Village Bur Dubai
Diving Village | neighbourhood | Old Dubai | culture | 0 | 0 | estimated | low | 45 | 09-21 | 0 | 0 | open | | Diving Village Dubai
XVA Gallery | gallery | Old Dubai | culture | 0 | 0 | estimated | low | 40 | 10-22 | 1 | 0 | open | | XVA Gallery Al Fahidi Dubai
Jumeirah Mosque | mosque | Jumeirah | culture | 0 | 0 | estimated | medium | 45 | 10-22 | 0 | 0 | open | | Jumeirah Mosque Dubai
Etihad Museum | museum | Jumeirah | culture | 15 | 40 | estimated | medium | 75 | 10-22 | 1 | 0 | open | | Etihad Museum Dubai
Alserkal Avenue | neighbourhood | Al Quoz | culture | 0 | 0 | estimated | low | 90 | 10-22 | 0 | 0 | open | | Alserkal Avenue Dubai
Concrete | gallery | Al Quoz | culture | 0 | 0 | estimated | low | 45 | 10-22 | 1 | 0 | open | | Concrete Alserkal Avenue Dubai
Dubai Design District | neighbourhood | Al Quoz | culture,shopping | 0 | 0 | estimated | low | 90 | 10-22 | 0 | 0 | open | | Dubai Design District
Al Seef | neighbourhood | Dubai Creek | culture,shopping | 0 | 0 | estimated | medium | 90 | always | 0 | 0 | open | | Al Seef Dubai
Crossroads of Civilizations Museum | museum | Old Dubai | culture | 20 | 40 | estimated | low | 60 | 10-22 | 1 | 0 | open | | Crossroads of Civilizations Museum Dubai
Saruq Al Hadid Museum | museum | Dubai Creek | culture | 20 | 50 | estimated | medium | 75 | 10-22 | 1 | 0 | open | | Saruq Al Hadid Museum Dubai
Burj Khalifa At the Top | attraction | Downtown | landmark | 189 | 189 | estimated | high | 90 | 10-00 | 1 | 1 | open | https://www.burjkhalifa.ae | Burj Khalifa Dubai
Dubai Frame | attraction | Zabeel | landmark | 50 | 50 | verified | medium | 60 | 09-21 | 1 | 1 | open | https://www.dubaiframe.ae | Dubai Frame
Museum of the Future | museum | Downtown | landmark | 169 | 169 | estimated | high | 90 | 10-22 | 1 | 1 | reopening | https://museumofthefuture.ae | Museum of the Future Dubai
Ain Dubai | attraction | Marina / JBR | landmark | 145 | 145 | estimated | high | 60 | 10-22 | 1 | 1 | open | | Ain Dubai Bluewaters
The View at The Palm | viewpoint | Palm | landmark | 115 | 115 | estimated | medium | 60 | 10-22 | 1 | 1 | open | | The View at the Palm Dubai
Sky Views Dubai | viewpoint | Downtown | landmark | 89 | 89 | estimated | medium | 45 | 10-22 | 1 | 1 | open | | Sky Views Observatory Dubai
Burj Al Arab | landmark | Jumeirah | landmark,outdoor | 0 | 0 | estimated | high | 30 | always | 0 | 0 | open | | Burj Al Arab Dubai
Palm Jumeirah Boardwalk | neighbourhood | Palm | landmark,outdoor | 0 | 0 | estimated | medium | 60 | always | 0 | 0 | open | | Palm Jumeirah Boardwalk
Dubai Water Canal | neighbourhood | Business Bay | landmark,outdoor | 0 | 0 | estimated | medium | 60 | always | 0 | 0 | open | | Dubai Water Canal
Bluewaters Island | neighbourhood | Marina / JBR | landmark,outdoor | 0 | 0 | estimated | high | 90 | always | 0 | 0 | open | | Bluewaters Island Dubai
Ras Al Khor Wildlife Sanctuary | wildlife | Dubai Creek | landmark,outdoor | 0 | 0 | estimated | low | 60 | 09-17 | 0 | 0 | open | | Ras Al Khor Wildlife Sanctuary
The Pointe | neighbourhood | Palm | landmark,shopping,outdoor | 0 | 0 | estimated | medium | 90 | 10-00 | 0 | 0 | open | | The Pointe Palm Jumeirah
Emirates Towers | landmark | Downtown | landmark | 0 | 0 | estimated | medium | 30 | always | 0 | 0 | open | | Emirates Towers Dubai
Souk Al Bahar | market | Downtown | landmark,shopping | 0 | 0 | estimated | medium | 60 | 10-00 | 0 | 0 | open | | Souk Al Bahar Dubai
Dubai Opera | venue | Downtown | landmark | 150 | 500 | estimated | medium | 150 | 10-22 | 1 | 0 | open | | Dubai Opera
Kite Beach | beach | Jumeirah | beach,outdoor | 0 | 0 | estimated | high | 120 | day | 0 | 0 | open | | Kite Beach Dubai
Jumeirah Public Beach | beach | Jumeirah | beach,outdoor | 0 | 0 | estimated | high | 120 | day | 0 | 0 | open | | Jumeirah Beach Dubai
Sunset Beach | beach | Jumeirah | beach,outdoor | 0 | 0 | estimated | medium | 90 | day | 0 | 0 | open | | Sunset Beach Dubai Umm Suqeim
La Mer Beach | beach | Jumeirah | beach,outdoor | 0 | 0 | estimated | high | 120 | day | 0 | 0 | open | | La Mer Beach Dubai
JBR Beach | beach | Marina / JBR | beach,outdoor | 0 | 0 | estimated | high | 120 | day | 0 | 0 | open | | JBR Beach Dubai
Al Mamzar Beach Park | beach | Al Mamzar | beach,outdoor | 5 | 5 | estimated | medium | 150 | 08-22 | 0 | 0 | open | | Al Mamzar Beach Park Dubai
Black Palace Beach | beach | Jumeirah | beach,outdoor | 0 | 0 | estimated | low | 90 | day | 0 | 0 | open | | Black Palace Beach Dubai
Palm West Beach | beach | Palm | beach,outdoor | 0 | 0 | estimated | medium | 120 | day | 0 | 0 | open | | Palm West Beach Dubai
Zabeel Park | park | Zabeel | outdoor | 0 | 0 | estimated | medium | 90 | 08-22 | 0 | 0 | open | | Zabeel Park Dubai
Safa Park | park | Jumeirah | outdoor | 0 | 0 | estimated | medium | 90 | 08-22 | 0 | 0 | open | | Safa Park Dubai
Creek Park | park | Dubai Creek | outdoor | 5 | 5 | estimated | medium | 90 | 08-22 | 0 | 0 | open | | Creek Park Dubai
Al Qudra Lakes | park | Al Qudra | outdoor | 0 | 0 | estimated | low | 90 | day | 0 | 0 | open | | Al Qudra Lakes Dubai
Mushrif Park | park | Mushrif | outdoor | 5 | 5 | estimated | low | 120 | 08-22 | 0 | 0 | open | | Mushrif Park Dubai
Dubai Miracle Garden | park | Dubailand | outdoor | 40 | 80 | estimated | high | 90 | 09-21 | 0 | 0 | open | | Dubai Miracle Garden
The Dubai Mall | mall | Downtown | shopping | 0 | 0 | estimated | high | 180 | 10-00 | 1 | 0 | open | | The Dubai Mall
Mall of the Emirates | mall | Al Barsha | shopping | 0 | 0 | estimated | high | 180 | 10-00 | 1 | 0 | open | | Mall of the Emirates Dubai
Ibn Battuta Mall | mall | Jebel Ali | shopping | 0 | 0 | estimated | medium | 120 | 10-22 | 1 | 0 | open | | Ibn Battuta Mall Dubai
Dubai Marina Mall | mall | Marina / JBR | shopping | 0 | 0 | estimated | medium | 120 | 10-22 | 1 | 0 | open | | Dubai Marina Mall
Deira City Centre | mall | Old Dubai | shopping | 0 | 0 | estimated | medium | 120 | 10-22 | 1 | 0 | open | | Deira City Centre Dubai
Nakheel Mall | mall | Palm | shopping | 0 | 0 | estimated | medium | 120 | 10-22 | 1 | 0 | open | | Nakheel Mall Palm Jumeirah
Dubai Hills Mall | mall | Dubai Hills | shopping | 0 | 0 | estimated | medium | 150 | 10-22 | 1 | 0 | open | | Dubai Hills Mall
City Centre Mirdif | mall | Mirdif | shopping | 0 | 0 | estimated | medium | 120 | 10-22 | 1 | 0 | open | | City Centre Mirdif Dubai
BurJuman | mall | Old Dubai | shopping | 0 | 0 | estimated | medium | 90 | 10-22 | 1 | 0 | open | | BurJuman Centre Dubai
Dubai Aquarium and Underwater Zoo | attraction | Downtown | family | 120 | 180 | estimated | high | 90 | 10-22 | 1 | 1 | open | | Dubai Aquarium and Underwater Zoo
IMG Worlds of Adventure | theme_park | Dubailand | family | 250 | 399 | estimated | high | 300 | 10-22 | 1 | 1 | open | | IMG Worlds of Adventure Dubai
Motiongate Dubai | theme_park | Dubailand | family | 250 | 350 | estimated | medium | 300 | 10-22 | 0 | 1 | open | | Motiongate Dubai
Legoland Dubai | theme_park | Dubailand | family | 250 | 350 | estimated | medium | 300 | 10-22 | 0 | 1 | open | | Legoland Dubai
Ski Dubai | attraction | Al Barsha | family | 180 | 250 | estimated | medium | 120 | 10-22 | 1 | 1 | open | | Ski Dubai Mall of the Emirates
KidZania Dubai | attraction | Downtown | family | 150 | 220 | estimated | medium | 180 | 10-22 | 1 | 1 | open | | KidZania Dubai Mall
The Green Planet | attraction | Jumeirah | family | 100 | 160 | estimated | medium | 75 | 10-22 | 1 | 0 | open | | The Green Planet City Walk Dubai
Wild Wadi Waterpark | water_park | Jumeirah | family,outdoor | 200 | 320 | estimated | high | 240 | 10-18 | 0 | 1 | open | | Wild Wadi Waterpark Dubai
Aquaventure Waterpark | water_park | Palm | family,outdoor | 250 | 400 | estimated | high | 300 | 10-18 | 0 | 1 | open | | Aquaventure Waterpark Dubai
The Lost Chambers Aquarium | attraction | Palm | family | 100 | 160 | estimated | medium | 60 | 10-22 | 1 | 0 | open | | The Lost Chambers Aquarium Atlantis Dubai
Barasti | venue | Marina / JBR | nightlife,outdoor | 0 | 0 | estimated | high | 180 | 12-02 | 0 | 0 | open | | Barasti Beach Dubai
Zero Gravity | venue | Marina / JBR | nightlife,beach,outdoor | 0 | 0 | estimated | high | 180 | 10-02 | 0 | 0 | open | | Zero Gravity Beach Club Dubai
WHITE Dubai | venue | Meydan | nightlife | 0 | 150 | estimated | high | 180 | 22-04 | 1 | 0 | open | | WHITE Dubai Meydan
Blue Marlin Ibiza UAE | venue | Jebel Ali | nightlife,outdoor | 0 | 200 | estimated | high | 240 | 12-02 | 0 | 0 | open | | Blue Marlin Ibiza UAE Dubai
Ce La Vi Dubai | venue | Downtown | nightlife | 0 | 150 | estimated | medium | 180 | 12-02 | 1 | 0 | open | | Ce La Vi Dubai Downtown
Soho Garden | venue | Meydan | nightlife,outdoor | 0 | 100 | estimated | high | 180 | 18-02 | 0 | 0 | open | | Soho Garden Meydan Dubai
Lock Stock and Barrel | venue | Marina / JBR | nightlife | 0 | 0 | estimated | medium | 150 | 12-02 | 1 | 0 | open | | Lock Stock and Barrel Dubai Marina
City Walk | neighbourhood | Jumeirah | shopping,outdoor | 0 | 0 | estimated | medium | 90 | 10-22 | 0 | 0 | open | | City Walk Dubai
La Mer | neighbourhood | Jumeirah | shopping,outdoor | 0 | 0 | estimated | high | 90 | 10-00 | 0 | 0 | open | | La Mer Dubai
Dubai Marina Promenade | neighbourhood | Marina / JBR | outdoor | 0 | 0 | estimated | high | 60 | always | 0 | 0 | open | | Dubai Marina Walk
The Walk at JBR | neighbourhood | Marina / JBR | shopping,outdoor | 0 | 0 | estimated | high | 90 | 10-00 | 0 | 0 | open | | The Walk JBR Dubai
Gold and Diamond Park | market | Al Quoz | shopping | 0 | 0 | estimated | low | 75 | 10-22 | 1 | 0 | open | | Gold and Diamond Park Dubai
Al Quoz Pond Park | park | Al Quoz | outdoor | 0 | 0 | estimated | low | 45 | day | 0 | 0 | open | | Al Quoz Pond Park Dubai
Marasi Marina Promenade | neighbourhood | Business Bay | outdoor | 0 | 0 | estimated | low | 45 | always | 0 | 0 | open | | Marasi Business Bay Dubai
Bay Avenue | neighbourhood | Business Bay | shopping | 0 | 0 | estimated | medium | 60 | 10-22 | 1 | 0 | open | | Bay Avenue Business Bay Dubai
Dubai Festival City | neighbourhood | Dubai Creek | shopping | 0 | 0 | estimated | medium | 120 | 10-22 | 1 | 0 | open | | Dubai Festival City
Dubai Creek Abra Crossing | transit | Dubai Creek | outdoor | 1 | 1 | estimated | medium | 15 | always | 0 | 0 | open | | Bur Dubai Abra Station
Global Village | attraction | Dubailand | shopping | 15 | 30 | estimated | high | 180 | 16-00 | 0 | 0 | open | | Global Village Dubai
Expo City Dubai | neighbourhood | Expo | outdoor,shopping | 0 | 0 | estimated | medium | 120 | 10-22 | 0 | 0 | open | | Expo City Dubai
OliOli | attraction | Al Quoz | family | 80 | 140 | estimated | medium | 90 | 10-22 | 1 | 0 | open | | OliOli children museum Dubai
Souk Madinat Jumeirah | market | Jumeirah | shopping | 0 | 0 | estimated | medium | 75 | 10-00 | 0 | 0 | open | | Souk Madinat Jumeirah
"""

# name | area | cuisine | tier | meals | query
RESTAURANTS = """
Al Ustad Special Kabab | Old Dubai | Pakistani | budget | lunch,dinner | Al Ustad Special Kabab Dubai
Ravi Restaurant | Old Dubai | Pakistani | budget | lunch,dinner | Ravi Restaurant Bur Dubai
Special Ostadi | Old Dubai | Iranian | budget | lunch,dinner | Special Ostadi Grill Dubai
Sadaf Restaurant | Old Dubai | Iranian | budget | lunch,dinner | Sadaf Iranian Restaurant Dubai
Arabian Tea House | Old Dubai | Emirati | mid | breakfast,lunch,dinner | Arabian Tea House Al Fahidi Dubai
Al Fanar Restaurant | Old Dubai | Emirati | mid | lunch,dinner | Al Fanar Restaurant Al Seef Dubai
XVA Cafe | Old Dubai | Cafe | mid | breakfast,lunch | XVA Cafe Dubai
Bait Al Wakeel | Old Dubai | Emirati | mid | lunch,dinner | Bait Al Wakeel Dubai
Ashiana by Vineet | Old Dubai | Indian | upscale | lunch,dinner | Ashiana by Vineet Dubai
Aseelah | Old Dubai | Emirati | upscale | dinner | Aseelah Al Seef Dubai
Shake Shack Dubai Mall | Downtown | American | budget | lunch,dinner | Shake Shack Dubai Mall
Nando's Dubai Mall | Downtown | Portuguese | budget | lunch,dinner | Nando's Dubai Mall
Operation Falafel Downtown | Downtown | Levantine | budget | lunch,dinner | Operation Falafel Downtown Dubai
Pickl Downtown | Downtown | American | budget | lunch,dinner | Pickl Dubai Mall
Eataly | Downtown | Italian | mid | breakfast,lunch,dinner | Eataly Dubai Mall
Baker and Spice | Downtown | International | mid | breakfast,lunch | Baker and Spice Dubai Mall
Social House | Downtown | International | mid | lunch,dinner | Social House Dubai Mall
Carnival by Tresind | Downtown | Indian | mid | lunch,dinner | Carnival by Tresind Dubai
Zuma | Downtown | Japanese | upscale | lunch,dinner | Zuma Dubai
La Petite Maison | Downtown | French | upscale | lunch,dinner | La Petite Maison Dubai
Barbecue Delights | Marina / JBR | Indian | budget | lunch,dinner | Barbecue Delights JBR Dubai
Kababji Marina | Marina / JBR | Lebanese | budget | lunch,dinner | Kababji Grill Dubai Marina
Zaatar w Zeit Marina | Marina / JBR | Levantine | budget | breakfast,lunch,dinner | Zaatar w Zeit Dubai Marina
Gazebo Marina | Marina / JBR | Indian | budget | lunch,dinner | Gazebo Restaurant Dubai Marina
Couqley | Marina / JBR | French | mid | lunch,dinner | Couqley French Bistro Dubai Marina
Crystal Jade | Marina / JBR | Chinese | mid | lunch,dinner | Crystal Jade Dubai Marina
PF Chang's Marina | Marina / JBR | Asian | mid | lunch,dinner | PF Chang's Dubai Marina
Abd El Wahab | Marina / JBR | Lebanese | mid | lunch,dinner | Abd El Wahab Dubai Marina
Asia Asia | Marina / JBR | Asian | upscale | dinner | Asia Asia Pier 7 Dubai
Zero Gravity Restaurant | Marina / JBR | International | upscale | lunch,dinner | Zero Gravity Dubai restaurant
Bu Qtair | Jumeirah | Seafood | budget | lunch,dinner | Bu Qtair Dubai
Al Mallah | Jumeirah | Lebanese | budget | lunch,dinner | Al Mallah Satwa Dubai
Salt | Jumeirah | Burgers | budget | lunch,dinner | Salt Burger Kite Beach Dubai
Operation Falafel Jumeirah | Jumeirah | Levantine | budget | lunch,dinner | Operation Falafel Jumeirah Dubai
Logma | Jumeirah | Emirati | mid | breakfast,lunch,dinner | Logma Dubai
Comptoir 102 | Jumeirah | Healthy | mid | breakfast,lunch | Comptoir 102 Dubai
Lime Tree Cafe | Jumeirah | Cafe | mid | breakfast,lunch | Lime Tree Cafe Jumeirah Dubai
3 Fils | Jumeirah | Seafood | mid | lunch,dinner | 3 Fils Dubai
Pierchic | Jumeirah | Seafood | upscale | lunch,dinner | Pierchic Al Qasr Dubai
Pai Thai | Jumeirah | Thai | upscale | dinner | Pai Thai Madinat Jumeirah
Nightjar Coffee | Al Quoz | Cafe | budget | breakfast,lunch | Nightjar Coffee Alserkal Dubai
Common Grounds | Al Quoz | Cafe | budget | breakfast,lunch | Common Grounds Al Quoz Dubai
The Espresso Lab | Al Quoz | Cafe | budget | breakfast,lunch | The Espresso Lab Alserkal Dubai
Pickl Al Quoz | Al Quoz | American | budget | lunch,dinner | Pickl Alserkal Avenue Dubai
Tom and Serg | Al Quoz | Australian | mid | breakfast,lunch | Tom and Serg Al Quoz Dubai
The Sum of Us | Al Quoz | Australian | mid | breakfast,lunch,dinner | The Sum of Us Al Quoz Dubai
Mirai | Al Quoz | Japanese | mid | lunch,dinner | Mirai Al Quoz Dubai
Bistro Des Arts | Al Quoz | French | mid | lunch,dinner | Bistro Des Arts Al Quoz Dubai
Qbara | Al Quoz | Middle Eastern | upscale | dinner | Qbara Dubai
Goldfish Sushi | Al Quoz | Japanese | upscale | dinner | Goldfish Sushi and Izakaya Dubai
Shake Shack Palm | Palm | American | budget | lunch,dinner | Shake Shack Nakheel Mall Dubai
Nando's The Pointe | Palm | Portuguese | budget | lunch,dinner | Nando's The Pointe Palm Jumeirah
Zaatar w Zeit Palm | Palm | Levantine | budget | breakfast,lunch,dinner | Zaatar w Zeit Palm Jumeirah
Little Miss India | Palm | Indian | budget | lunch,dinner | Little Miss India Palm Jumeirah
The Shore | Palm | International | mid | lunch,dinner | The Shore Palm West Beach Dubai
101 Dining Lounge | Palm | International | mid | lunch,dinner | 101 Dining Lounge Palm Jumeirah
Khyber | Palm | Indian | mid | lunch,dinner | Khyber Palm Jumeirah Dubai
West 14th | Palm | Steak | mid | dinner | West 14th Palm Jumeirah
Nobu | Palm | Japanese | upscale | lunch,dinner | Nobu Atlantis The Palm Dubai
Ossiano | Palm | Seafood | upscale | dinner | Ossiano Atlantis The Palm
Al Fanar Festival City | Dubai Creek | Emirati | budget | lunch,dinner | Al Fanar Restaurant Dubai Festival City
The Noodle House Festival City | Dubai Creek | Asian | budget | lunch,dinner | The Noodle House Dubai Festival City
Gazebo Festival City | Dubai Creek | Indian | budget | lunch,dinner | Gazebo Dubai Festival City
Original Shawarma Festival City | Dubai Creek | Levantine | budget | lunch,dinner | Shawarma Dubai Festival City
Boardwalk | Dubai Creek | International | mid | lunch,dinner | Boardwalk Dubai Creek Golf
QDs | Dubai Creek | International | mid | lunch,dinner | QDs Dubai Creek
The Croft | Dubai Creek | British | mid | lunch,dinner | The Croft Dubai
Al Dawaar | Dubai Creek | International | mid | lunch,dinner | Al Dawaar Hyatt Regency Dubai
Shabestan | Dubai Creek | Iranian | upscale | lunch,dinner | Shabestan Radisson Blu Deira Creek
The Thai Kitchen | Dubai Creek | Thai | upscale | dinner | The Thai Kitchen Park Hyatt Dubai
Zaatar w Zeit Business Bay | Business Bay | Levantine | budget | breakfast,lunch,dinner | Zaatar w Zeit Business Bay Dubai
Operation Falafel Business Bay | Business Bay | Levantine | budget | lunch,dinner | Operation Falafel Business Bay Dubai
Pickl Business Bay | Business Bay | American | budget | lunch,dinner | Pickl Business Bay Dubai
Black Tap Business Bay | Business Bay | American | budget | lunch,dinner | Black Tap Business Bay Dubai
Clap | Business Bay | Japanese | mid | lunch,dinner | Clap Dubai Business Bay
BOCA | Business Bay | Mediterranean | mid | lunch,dinner | BOCA Dubai
Asia Republic | Business Bay | Asian | mid | lunch,dinner | Asia Republic Dubai
La Serre | Business Bay | French | mid | lunch,dinner | La Serre Dubai
Tresind | Business Bay | Indian | upscale | lunch,dinner | Tresind Dubai
Morimoto | Business Bay | Japanese | upscale | dinner | Morimoto Dubai
"""

# name | area | tier | query
HOTELS = """
ibis Deira City Centre | Old Dubai | budget | ibis Deira City Centre Dubai
Premier Inn Dubai International Airport | Old Dubai | budget | Premier Inn Dubai International Airport
Arabian Courtyard Hotel and Spa | Old Dubai | mid | Arabian Courtyard Hotel Dubai
Radisson Blu Hotel Dubai Deira Creek | Old Dubai | mid | Radisson Blu Hotel Dubai Deira Creek
Raffles Dubai | Old Dubai | luxury | Raffles Dubai
Grand Hyatt Dubai | Old Dubai | luxury | Grand Hyatt Dubai
Rove Downtown | Downtown | budget | Rove Downtown Dubai
ibis One Central | Downtown | budget | ibis One Central Dubai
Vida Downtown | Downtown | mid | Vida Downtown Dubai
Hotel Boulevard Autograph Collection | Downtown | mid | Hotel Boulevard Autograph Collection Dubai
Palace Downtown | Downtown | luxury | Palace Downtown Dubai
Armani Hotel Dubai | Downtown | luxury | Armani Hotel Dubai
Rove Dubai Marina | Marina / JBR | budget | Rove Dubai Marina
Premier Inn Dubai Internet City | Marina / JBR | budget | Premier Inn Dubai Internet City
Hilton Garden Inn Dubai Marina | Marina / JBR | mid | Hilton Garden Inn Dubai Marina
Amwaj Rotana | Marina / JBR | mid | Amwaj Rotana JBR Dubai
Address Beach Resort | Marina / JBR | luxury | Address Beach Resort JBR Dubai
Grosvenor House Dubai | Marina / JBR | luxury | Grosvenor House Dubai Marina
Rove City Walk | Jumeirah | budget | Rove City Walk Dubai
Beach Walk Hotel | Jumeirah | budget | Beach Walk Hotel Jumeirah Dubai
Sheraton Jumeirah Beach | Jumeirah | mid | Sheraton Dubai Jumeirah Beach Resort
La Ville Hotel City Walk | Jumeirah | mid | La Ville Hotel and Suites City Walk Dubai
Burj Al Arab Hotel | Jumeirah | luxury | Burj Al Arab hotel Dubai
Jumeirah Beach Hotel | Jumeirah | luxury | Jumeirah Beach Hotel Dubai
Arabian Gulf Hotel Apartments | Al Quoz | budget | Arabian Gulf Hotel Apartment Al Barsha Dubai
Dunes Hotel Apartments | Al Quoz | mid | Dunes Hotel Apartments Al Barsha Dubai
The Canvas Dubai | Al Quoz | luxury | The Canvas Dubai MGallery Hotel
Avani Palm View | Palm | budget | Avani Palm View Dubai Hotel
voco Dubai The Palm | Palm | mid | voco Hotel The Palm Dubai
Atlantis The Palm | Palm | luxury | Atlantis The Palm Dubai
Tulip Creek Hotel | Dubai Creek | budget | Tulip Creek Hotel Apartments Dubai
Aloft Dubai Creek | Dubai Creek | mid | Aloft Dubai Creek
Park Hyatt Dubai | Dubai Creek | luxury | Park Hyatt Dubai
Citymax Hotel Business Bay | Business Bay | budget | Citymax Hotel Business Bay Dubai
Renaissance Business Bay | Business Bay | mid | Renaissance Business Bay Hotel Dubai
Al Habtoor Palace | Business Bay | luxury | Al Habtoor Palace Dubai
"""

# code | name | wikipedia title
RED_MAIN = """
11 | Centrepoint | Centrepoint (Dubai Metro)
12 | Emirates | Emirates (Dubai Metro)
13 | Airport Terminal 3 | Airport Terminal 3 (Dubai Metro)
14 | Airport Terminal 1 | Airport Terminal 1 (Dubai Metro)
15 | Al Garhoud | GGICO (Dubai Metro)
16 | City Centre Deira | Deira City Centre (Dubai Metro)
17 | Al Rigga | Al Rigga (Dubai Metro)
18 | Union | Union (Dubai Metro)
19 | BurJuman | BurJuman (Dubai Metro)
20 | ADCB | ADCB (Dubai Metro)
21 | Max | Max (Dubai Metro)
22 | World Trade Centre | World Trade Centre (Dubai Metro)
23 | Emirates Towers | Emirates Towers (Dubai Metro)
24 | Financial Centre | Financial Centre (Dubai Metro)
25 | Burj Khalifa/Dubai Mall | Burj Khalifa/Dubai Mall (Dubai Metro)
26 | Business Bay | Business Bay (Dubai Metro)
29 | Garmin | Garmin (Dubai Metro)
31 | Equiti | Equiti (Dubai Metro)
32 | Mall of the Emirates | Mall of the Emirates (Dubai Metro)
33 | Insurance Market | Mashreq (Dubai Metro)
34 | Dubai Internet City | Dubai Internet City (Dubai Metro)
35 | Al Fardan Exchange | Al Khail (Dubai Metro)
36 | Sobha Realty | Dubai Marina (Dubai Metro)
37 | DMCC | DMCC (Dubai Metro)
38 | National Paints | Jabal Ali (Dubai Metro)
"""

RED_LIFE = """
39 | Ibn Battuta | Ibn Battuta (Dubai Metro)
40 | Energy | Energy (Dubai Metro)
41 | Danube | Danube (Dubai Metro)
42 | Life Pharmacy | Life Pharmacy (Dubai Metro)
"""

RED_EXPO = """
70 | The Gardens | The Gardens (Dubai Metro)
71 | Discovery Gardens | Discovery Gardens (Dubai Metro)
72 | Al Furjan | Al Furjan (Dubai Metro)
73 | Jumeirah Golf Estates | Jumeirah Golf Estates (Dubai Metro)
74 | Dubai Investment Park | Dubai Investment Park (Dubai Metro)
76 | Expo 2020 | Expo 2020 (Dubai Metro)
"""

GREEN = """
11 | E& | Etisalat by e& (Dubai Metro)
12 | Al Qusais | Al Qusais (Dubai Metro)
13 | Dubai Airport Free Zone | Dubai Airport Free Zone (Dubai Metro)
14 | Al Nahda | Al Nahda (Dubai Metro)
15 | Stadium | Stadium (Dubai Metro)
16 | Al Qiyadah | Al Qiyadah (Dubai Metro)
17 | Abu Hail | Abu Hail (Dubai Metro)
18 | Abu Baker Al Siddique | Abu Baker Al Siddique (Dubai Metro)
19 | Salah Al Din | Salah Al Din (Dubai Metro)
20 | Union | Union (Dubai Metro)
21 | Baniyas Square | Baniyas Square (Dubai Metro)
22 | Gold Souq | Gold Souq (Dubai Metro)
23 | Al Ras | Al Ras (Dubai Metro)
24 | Al Ghubaiba | Al Ghubaiba (Dubai Metro)
25 | Sharaf DG | Sharaf DG (2020 Dubai Metro)
26 | BurJuman | BurJuman (Dubai Metro)
27 | Oud Metha | Oud Metha (Dubai Metro)
28 | Dubai Healthcare City | Dubai Healthcare City (Dubai Metro)
29 | Al Jadaf | Al Jadaf (Dubai Metro)
30 | Creek | Dubai Creek (Dubai Metro)
"""

# Wikipedia's tram table order, with the spelling corrected.
TRAM = """
1 | Jumeirah Beach Residence 1 | Jumeirah Beach Residence 1 Dubai Tram station
2 | Jumeirah Beach Residence 2 | Jumeirah Beach Residence 2 Dubai Tram station
3 | Jumeirah Lakes Towers | Jumeirah Lakes Towers Dubai Tram station
4 | Dubai Marina Mall | Dubai Marina Mall Tram station
5 | Dubai Marina | Dubai Marina Tram station
6 | Marina Towers | Marina Towers Dubai Tram station
7 | Mina Seyahi | Mina Seyahi Dubai Tram station
8 | Media City | Dubai Media City Tram station
9 | Palm Jumeirah | Palm Jumeirah Dubai Tram station
10 | Knowledge Village | Knowledge Village Dubai Tram station
11 | Al Sufouh | Al Sufouh Dubai Tram station
"""

PLACE_COLUMNS = (
    "name",
    "category",
    "area",
    "tags",
    "min",
    "max",
    "price_class",
    "crowd",
    "minutes",
    "hours",
    "indoor",
    "timed",
    "status",
    "url",
    "query",
)
RESTAURANT_COLUMNS = ("name", "area", "cuisine", "tier", "meals", "query")
HOTEL_COLUMNS = ("name", "area", "tier", "query")
STATION_COLUMNS = ("code", "name", "ref")


def parse_table(text: str, columns: tuple[str, ...]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != len(columns):
            raise ValueError(f"expected {len(columns)} fields, got {len(parts)}: {line}")
        rows.append(dict(zip(columns, parts, strict=True)))
    return rows
