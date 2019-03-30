#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import csv
import logging
import requests
import argparse
from datetime import datetime, timedelta
from xml.etree import ElementTree

MOEX_QUOTES_URL = 'https://iss.moex.com/iss/history/engines/{engine}/markets/{market}/securities.xml' \
                  '?limit=100&date={date}&start={start}'
DATE_FORMAT = '%Y-%m-%d'


def download_moex_data(engine, market, date, start=0, save_raw_xml=False):
    url = MOEX_QUOTES_URL.format(
        engine=engine,
        market=market,
        date=date,
        start=start)

    logging.debug('Request: {}'.format(url))

    r = requests.get(url)

    if save_raw_xml:
        with open('./downloads/moex_data_{}_{}_{}_{}.xml'.format(engine, market, date, start), 'w') as f:
            f.write(r.text)

    return r.text


def save_to_csv(quotes, engine, market, date, header_attrs=None):
    date_parsed = datetime.strptime(date, DATE_FORMAT)
    filepath = './quotes/{year}/{month}/{day}/{year}-{month}-{day}-{engine}-{market}.csv'.format(
        year=date_parsed.strftime('%Y'),
        month=date_parsed.strftime('%m'),
        day=date_parsed.strftime('%d'),
        engine=engine,
        market=market)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    outfile = open(filepath, 'a' if os.path.exists(filepath) and header_attrs is None else 'w')
    writer = csv.writer(outfile)

    if header_attrs:
        writer.writerow(header_attrs.keys())

    for row in quotes:
        writer.writerow(row.values())

    outfile.close()


def parse_row_attributes(root):
    TYPES_MAP = {
        'string': str,
        'date': str,
        'time': str,
        'double': float,
        'int32': int,
        'int64': int,
    }

    result = {}
    for row in root.findall("data[@id='history']/metadata/columns/column"):
        result[row.get('name')] = TYPES_MAP.get(row.get('type'), str)

    return result


def parse_pagination(root):
    for row in root.findall("data[@id='history.cursor']/rows/row[@TOTAL]"):
        return {
            'total_items': int(row.get('TOTAL', 0)),
            'current_index': int(row.get('INDEX', 0)),
            'page_size': int(row.get('PAGESIZE', 0))
        }


def validate_quote(quote):
    return 'CLOSE' in quote


def parse_quotes(root, quote_attrs):
    DEFAULT_QUOTE_ATTR_VALUE = ''

    quotes = []
    for row in root.findall("data[@id='history']/rows/row"):
        quote = {}
        for attr_name, attr_type in quote_attrs.items():
            value = row.get(attr_name)
            quote[attr_name] = attr_type(value) if value else DEFAULT_QUOTE_ATTR_VALUE
        quotes.append(quote)
    return quotes


def parse_moex_data(xml_data):
    root = ElementTree.fromstring(xml_data)

    pagination = parse_pagination(root)
    quote_attrs = parse_row_attributes(root)
    quotes = parse_quotes(root, quote_attrs)

    return pagination, quote_attrs, quotes


def get_moex_data(engine, market, date, start=0, save_raw_xml=False):
    xml_data = download_moex_data(engine, market, date, start, save_raw_xml)
    pagination, quote_attrs, quotes = parse_moex_data(xml_data)

    valid_quotes = [q for q in quotes if validate_quote(q)]

    if len(valid_quotes):
        save_to_csv(valid_quotes, engine, market, date, quote_attrs if start == 0 else None)
    else:
        logging.error('No quotes for "{}, {}, {}, {}", pagination: {}'.format(
            engine, market, date, start, pagination))

    logging.debug('Got quotes: {:3d}/{:3d}, pagination: {}, params: {}, {}, {}, {}'.format(
        len(valid_quotes), len(quotes),
        '{} + {} < {}'.format(pagination['current_index'], pagination['page_size'], pagination['total_items']),
        engine, market, date, start))

    if pagination['current_index'] + pagination['page_size'] < pagination['total_items']:
        get_moex_data(engine, market, date, start + pagination['page_size'], save_raw_xml)


def configure_logging():
    logging.basicConfig(
        format='%(levelname)-7s:%(asctime)s: %(message)s',
        level=logging.DEBUG,
        handlers=[
            logging.FileHandler('./logs/requests.log'),
            logging.StreamHandler()])
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def parse_args():
    parser = argparse.ArgumentParser(description='MOEX quotes downloader')
    parser.add_argument(
        '--engine',
        default='stock',
        help='Доступные торговые системы: stock, currency https://iss.moex.com/iss/engines.xml',
    )
    parser.add_argument(
        '--market',
        required=True,
        help='Доступные рынки: index, shares, bonds https://iss.moex.com/iss/engines/stock/markets.xml',
    )
    parser.add_argument(
        '--date',
        required=True,
        type=lambda d: datetime.strptime(d, DATE_FORMAT),
        help='Дата, за которую скачивать котировки в формате YYYY-MM-DD',
    )
    parser.add_argument(
        '--dateend',
        type=lambda d: datetime.strptime(d, DATE_FORMAT),
        help='Дата окончания диапазона дат [date, dateend] в формате YYYY-MM-DD',
    )
    parser.add_argument(
        '--save-raw-xml',
        action='store_true',
        help='Сохранять ли исходные XML файлы',
    )
    return parser.parse_args()


def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + timedelta(n)


def main(args):
    if args.dateend is None:
        day_str = args.date.strftime(DATE_FORMAT)
        logging.info((args.engine, args.market, day_str))
        get_moex_data(args.engine, args.market, day_str, save_raw_xml=args.save_raw_xml)
    else:
        for day in daterange(args.date, args.dateend):
            if day.weekday() >= 5:
                # ignore weekends
                continue
            day_str = day.strftime(DATE_FORMAT)
            logging.info((args.engine, args.market, day_str))
            get_moex_data(args.engine, args.market, day_str, save_raw_xml=args.save_raw_xml)


if __name__ == "__main__":
    args = parse_args()
    configure_logging()
    main(args)
