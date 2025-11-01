import datetime
import json
import locale
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


# Set the locale to Galician (for displaying event dates in Galician)
locale.setlocale(locale.LC_TIME, 'gl_ES.UTF-8')


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
        [2025-10-30, 2025-10-31, 2025-11-01]
    to
        Xoves 30, Venres 31 [Outubro], Sábado 01 [Novembro]
    """

    for feature in geojson['features']:
        dates = feature['properties']['dates']
        dates = sorted(datetime.date.fromisoformat(d) for d in dates)

        parts = []
        for i, dt in enumerate(dates):
            part = f"{dt.strftime('%A')} {dt.day:02d}"
            # Append month in brackets when it's the last entry or the month changes afterwards
            if i == len(dates) - 1 or dt.month != dates[i+1].month:
                part += f" [{dt.strftime('%B')}]"
            parts.append(part)

        feature['properties']['dates'] = ', '.join(parts)

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
    html_str = template.render(
        geojson=geojson,
        today_geojson=filter_geojson(
            geojson,
            [today.strftime("%A %d")]),
        tomorrow_geojson=filter_geojson(
            geojson,
            [(today + datetime.timedelta(days=1)).strftime("%A %d")]),
        week_geojson=filter_geojson(
            geojson,
            [(today + datetime.timedelta(days=i)).strftime("%A %d") for i in range(0, 7)]),
    )

    with open(main_dir / 'htmls' / 'axenda.html', 'w') as f:
        f.write(html_str)


if __name__ == "__main__":
    generate_html()
