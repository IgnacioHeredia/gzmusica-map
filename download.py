import datetime
import json
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

month_map = {
    'xaneiro': 'january',
    'febreiro':'february',
    'marzo': 'march',
    'abril': 'april',
    'maio': 'may',
    'xuño': 'june',
    'xullo': 'july',
    'agosto': 'august',
    'setembro': 'september',
    'outubro': 'october',
    'novembro': 'november',
    'decembro': 'december',
}


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
            url=base_url + f'/axenda/eventsbyweek/{tmpdate.year}/{tmpdate.month}/{tmpdate.day}/-.html',
            headers=headers,
            )
        content = BeautifulSoup(r.text, 'lxml')
        # table = content.find('table', attrs={'class': 'ev_table'}).findAll('tr')[1:]

        dates = content.findAll('a', attrs={'class': 'ev_link_weekday'})  # dates in the week
        day_data = content.findAll('ul', attrs={'class': 'ev_ul'})  # events each day

        for date, day_data in zip(dates, day_data):

            date = date.text.replace("\n", "").replace("\t", "")

            # Transform month name from Galician to English
            tmp_day, tmp_month = date.strip().split(' ')
            tmp_month = month_map[tmp_month.lower()]
            date = f"{tmp_day} {tmp_month}"

            # Date string to datetime object
            datef = datetime.datetime.strptime(f"{date} {tmpdate.year}", "%d %B %Y").date()
            datef = datef.replace(year=dstart.year)
            date = f"{datef.strftime('%A')} {date}"  # add weekday to date

            if datef < dstart or datef > dstart + datetime.timedelta(days=30):  # remove past days or days above 30+ limit
                print(f'  skipping {date}')
                continue
            print(f'  processing {date}')

            events = day_data.find_all('li', attrs={'class': 'ev_td_li'})
            if not events:
                continue

            for event in events:

                href = base_url + event.find('a')['href']
                dtext = event.text.split('::')
                name = dtext[0].split('\t')[-1].split('\xa0')[0]

                location = dtext[-1].strip().split('\n')[-1]
                location = location.split(' - ')[-1]  # keep only city, as more detailed is usually not found in Nominatim
                location = location.strip()
                if not location:
                    print(f'    Event not located: {dtext}')
                    continue

                if name in data.keys():  # the event already exists, it's just new date
                    data[name]['dates'].append(date)

                else:  # new event
                    if location in places:
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
                        'link': href,
                        'location': location,
                        'lat': lat,
                        'lon': lon,
                        'dates': [date],
                    }

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
