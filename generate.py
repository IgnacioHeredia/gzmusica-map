import datetime
import json
import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


main_dir = Path(__file__).resolve().parent


def filter_geojson(geojson, filter_dates):
    """
    Keep only events whose dates are included
    in filter dates
    """
    tmp = {
        "type": "FeatureCollection",
        "features": []
    }
    for feature in geojson['features']:
        dates = feature['properties']['dates']
        for d in filter_dates:
            if d in dates:
                tmp['features'].append(feature)
                break
    return tmp


def format_dates(geojson):
    """
    Transform
        [Sunday10 October, Monday11 October]
    to
        Sunday10, Monday 11 [October]
    """
    
    for feature in geojson['features']:
        dates = feature['properties']['dates']

        date_str = ''
        days = [i.split(' ')[0] for i in dates]
        months = [i.split(' ')[1] for i in dates] 

        for i in range(len(days)):
            date_str += days[i]

            if i == len(days)-1 or months[i] != months[i+1]:
                date_str += f' [{months[i]}] '
            else:
                date_str += ', '
                
        feature['properties']['dates'] = date_str
        
    return geojson


def generate_html():
    print('# Generating html map')

    with open(main_dir / 'data' / 'gzmusica.geojson') as f:
        geojson = json.load(f)
    geojson = format_dates(geojson)

    today = datetime.date.today()
#     today = datetime.date(2021, 8, 1)

    env = Environment(loader=FileSystemLoader(main_dir / 'htmls'),
                             trim_blocks=True)
    template = env.get_template('axenda_template.html')
    html_str = template.render(geojson=geojson,
                               today_geojson=filter_geojson(geojson,
                                                            [today.strftime("%A%d")]),
                               tomorrow_geojson=filter_geojson(geojson,
                                                               [(today + datetime.timedelta(days=1)).strftime("%A%d")]),
                               week_geojson=filter_geojson(geojson,
                                                           [(today + datetime.timedelta(days=i)).strftime("%A%d") for i in range(0, 7)]),
                              )

    with open(main_dir / 'htmls' / 'axenda.html', 'w') as f:
        f.write(html_str)
        

if __name__ == "__main__":
    generate_html()
