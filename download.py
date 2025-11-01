import datetime
import json
import locale
import os
from random import random
from pathlib import Path
import time

from bs4 import BeautifulSoup
import requests


session = requests.Session()
session.headers.update({
    'User-Agent': 'gzmusica-map-bot',  # user-agent has to be custom (https://operations.osmfoundation.org/policies/nominatim/)
    })

main_dir = Path(__file__).resolve().parent

# Set the locale to Galician (for parsing event dates)
locale.setlocale(locale.LC_TIME, 'gl_ES.UTF-8')


def randomize(*coord):
    """
    We don't use decorator because it didn't randomize when we
    took locations directly from `places.json`
    """
    return tuple(str(float(i) + 0.002 * random()) for i in coord)


# def randomize(f):
#     """
#     Decorator:
#     Randomize coordinates so that waypoints with same coordinates
#     don't collapse in exactly the same place.
#     """
#     def wrap(*args, **kwargs):
#         coord = f(*args, **kwargs)
#         return tuple(str(float(i) + 0.002 * random()) for i in coord)
#     return wrap


def get_coord(place):
    """
    We wait one second before each request to abide by the user terms:
    https://operations.osmfoundation.org/policies/nominatim/
    """
    url = 'https://nominatim.openstreetmap.org/search'

    params = {'country': 'Spain',
              'state': 'Galicia',
              'format': 'jsonv2'}
    plist = place.split('(')
    params['city'] = plist[0].split(',')[0].strip()
    if len(plist) == 2:
        params['county'] = plist[1][:-1].strip()

    time.sleep(1)
    r = session.get(url, params=params)
    r = r.json()

    if not r:
        # try variation
        params['city'] = plist[0].split(',')[-1].strip()
        time.sleep(1)
        r = session.get(url, params=params)
        r = r.json()
    if not r and 'county' in params.keys():
        # try variation
        params['city'] = params['county']
        params['county'] = ''
        time.sleep(1)
        r = session.get(url, params=params)
        r = r.json()
    if not r:
        # try non-structured query
        time.sleep(1)
        r = session.get(url, params={'q': place, 'format': 'jsonv2'})
        r = r.json()
    if r:
        # prioritize cities/villages in OSM results over anything else
        # https://nominatim.org/release-docs/latest/customize/Ranking/
        r1, r2 = [], []
        for i in r:
            if 13 <= i['place_rank'] <= 24:  # city/village
                r1.append(i)
            else:
                r2.append(i)
        r = r1 + r2
    if not r:
        # otherwise try Photon, which is tolerant to typos
        r = session.get(
            'https://photon.komoot.io/api',
            params={'q': place, 'limit': 1},
        )
        r = r.json()['features']
        if r:
            r = r[0]['geometry']['coordinates']
            r = [{'lon': r[0], 'lat': r[1]}]
    if r:
        return r[0]['lat'], r[0]['lon']
    else:
        raise Exception(f'{place} not found')


# import numpy as np
# @randomize
# def get_coord(place):
#     """
#     Dummy function for test. Returns random coord inside box.
#     """
#     lon = np.random.uniform(low=-7.119870, high=-8.524992)
#     lat = np.random.uniform(low=42.195923, high=43.251599)
#     return lat, lon


def download_events():
    print('# Downloading events from the calendar')
    dstart = datetime.date.today()
#     dstart = datetime.date(2021, 8, 1)

    data = {}
    week_num = 4

    if os.path.isfile(main_dir / 'data' / 'places.json'):
        with open(main_dir / 'data' / 'places.json', 'r') as f:
            places = json.load(f)
    else:
        places = {}

    s = requests.Session()
    base_url = 'https://www.gzmusica.com'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36'
            }

    for i in range(0, week_num + 1):
        print(f'Processing week {i+1} ...')

        tmpdate = dstart + datetime.timedelta(days=7*i)
        r = s.get(
            url=f'{base_url}/axenda/eventsbyweek/{tmpdate.year}/{tmpdate.month}/{tmpdate.day}/-.html',
            headers=headers,
            )
        content = BeautifulSoup(r.text, 'lxml')

        events = content.findAll('div', attrs={'class': 'jev_listrow'})
        for e in events:

            name = e.find('a', attrs={'class': 'ev_link_row'}).get('title')
            href = e.find('a', attrs={'class': 'ev_link_row'}).get('href')
            location = e.findAll('span')[-1].text
            date = e.find('a', attrs={'class': 'jevdateicon'}).text  # eg. 21Nov

            # Date string to datetime object
            datef = datetime.datetime.strptime(date, "%d%b").date()
            datef = datef.replace(year=dstart.year)
            date = datef.strftime('%Y-%m-%d')

            # Do not process past days or days above 30+ limit
            if datef < dstart or datef > dstart + datetime.timedelta(days=30):
                print(f'  {datef} {name}: skipping')
                continue
            print(f'  {datef} {name}: processing')

            # If the event already exists, it's just new date
            if name in data.keys():
                data[name]['dates'].append(date)
                continue

            # Find the event location
            location = location.split(' - ')[-1].strip()  # keep only city, as more detailed is usually not found in Nominatim
            if not location:
                print(f'    Event not located: {name}')
                continue
            elif location in places:
                lat, lon = places[location]['lat'], places[location]['lon']
            else:
                try:
                    lat, lon = get_coord(location)
                    places[location] = {'lat': lat, 'lon': lon}
                except Exception as e:
                    print(e)
                    continue

            lat, lon = randomize(lat, lon)
            data[name] = {
                'link': f'{base_url}{href}',
                'location': location,
                'lat': lat,
                'lon': lon,
                'dates': [date],
            }

    # If no data, we probably parsed it wrong
    if not data:
        raise Exception('No data found')

    # Save places to database
    with open(main_dir / 'data' / 'places.json', 'w') as f:
        json.dump(places, f, ensure_ascii=False, indent=4)

    # Save events to geojson
    geojson = {'type': 'FeatureCollection',
               'features': [{
                   'type': 'Feature',
                   'geometry': {
                       'type': 'Point',
                       'coordinates': [
                           d['lon'],
                           d['lat']
                       ]},
                   'properties': {
                       'name': name,
                       'location': d['location'],
                       'link': d['link'],
                       'dates': d['dates'],
                   }
               } for name, d in data.items()
               ]}

    with open(main_dir / 'data' / 'gzmusica.geojson', 'w') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    download_events()
