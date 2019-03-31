import os
import csv
import argparse
import importlib
import pandas as pd
from datetime import datetime
from collections import defaultdict

from helpers import daterange, DATE_FORMAT


def load_graph_builder(name):
    module = importlib.import_module('graph_data.{}.graph'.format(name))
    return module.GraphBuilder()


def load_graph_builders(graphs_list):
    if graphs_list is None:
        graphs_list = next(os.walk('./graph_data'))[1]

    graphs = defaultdict(list)
    for graph_name in graphs_list:
        if '__' in graph_name:
            continue

        builder = load_graph_builder(graph_name)
        market_filter = builder.market_filter()
        graphs[(market_filter['engine'], market_filter['market'])].append({
            'name': graph_name,
            'builder': builder
        })

    return graphs


def load_data(engine, market, day):
    # day = datetime.strptime(date, DATE_FORMAT)
    filepath = './quotes/{year}/{month}/{day}/{year}-{month}-{day}-{engine}-{market}.csv'.format(
        year=day.strftime('%Y'),
        month=day.strftime('%m'),
        day=day.strftime('%d'),
        engine=engine,
        market=market
    )
    if os.path.exists(filepath):
        return pd.read_csv(filepath)
    else:
        return None


def filter_data(df, filters):
    return df.loc[(df[list(filters)] == pd.Series(filters)).all(axis=1)]


def merge_values(date, value):
    return [date] + (list(value) if isinstance(value, (list, tuple)) else [value])


def get_timestamp(day):
    # TODO: utc -> moscow time
    return int(day.timestamp()) * 1000


def calc_value(df, builder, day):
    df_filtered = filter_data(df, builder.quote_filter())
    if df_filtered.shape[0] >= 1:
        value = builder.get_value(df_filtered)
        return merge_values(get_timestamp(day), value)
    else:
        return None


def save_values(name, values, clear=False):
    filepath = './graph_data/{}/values.csv'.format(name)
    outfile = open(filepath, 'a' if os.path.exists(filepath) and not clear else 'w')
    writer = csv.writer(outfile)

    for row in values:
        writer.writerow(row)
    outfile.close()


def parse_args():
    parser = argparse.ArgumentParser(description='MOEX quotes graph builder')
    parser.add_argument(
        '--date',
        required=True,
        type=lambda d: datetime.strptime(d, DATE_FORMAT),
        help='Дата, за которую строить графики в формате YYYY-MM-DD',
    )
    parser.add_argument(
        '-g',
        '--graphs',
        '--graph',
        nargs='*',
        help='Названия графиков, которые пересчитать (английские названия папок). По-умолчанию — все.',
    )
    parser.add_argument(
        '-c',
        '--clear',
        action='store_true',
        help='Очищать ли предыдущие данные',
    )
    parser.add_argument(
        '--dateend',
        type=lambda d: datetime.strptime(d, DATE_FORMAT),
        help='Дата окончания диапазона дат [date, dateend] в формате YYYY-MM-DD',
    )
    return parser.parse_args()


def main(args):
    graph_builders = load_graph_builders(args.graphs)

    if args.dateend:
        dates = daterange(args.date, args.dateend)
    else:
        dates = [args.date]

    results = defaultdict(list)
    for day in dates:
        for (engine, market), builders in graph_builders.items():
            data = load_data(engine, market, day)
            if data is None:
                continue
            for builder in builders:
                result = calc_value(data, builder['builder'], day)
                if result is not None:
                    results[builder['name']].append(result)

    for name, values in results.items():
        save_values(name, values, args.clear)

    print(results)


if __name__ == "__main__":
    args = parse_args()
    main(args)
