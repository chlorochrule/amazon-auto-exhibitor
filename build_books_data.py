#-*- coding: utf-8 -*-
import json
import re
import pandas as pd
import datetime as dt
from bottlenose import api
from bs4 import BeautifulSoup
import urllib2

COLUMNS = ['asin', 'shelf_number', 'status', 'server', 'title', 'condition', 'condition_note',
    'quantity', 'price', 'sku', 'date_of_registration', 'mode', 'minimum_price', 'author', 'publisher',
    'publicationdate', 'numberofpages', 'height', 'length', 'width', 'weight', 'shipping_fee', 'condition_note_text', 'note'
]

settings = pd.read_csv('settings.csv')
STATUS = 'nos'
shelf_number = settings['shelf_number'][0]
server_sum = int(settings['server_sum'][0])
CONDITION = settings['condition'][0]
CONDITION_NOTE = settings['condition_note'][0]
QUANTITY = '1'
DEFAULT_PRICE = settings['price'][0]
MINIMUM_PRICE = settings['minimum_price'][0]

def item_lookup(amazon, *args, **kwargs):
    try:
        return amazon.ItemLookup(*args, **kwargs)
    except urllib2.HTTPError:
        return item_lookup(amazon, *args, **kwargs)

def convert_isbn_13_to_10(isbn13):
    if len(str(isbn13)) != 13:
        if len(str(isbn13)) == 10:
            return isbn13
        raise Exception("Passed ISBN is not ISBN13")
    isbn10 = str(isbn13)[3:-1]
    cd = 11 - sum(int(isbn10[i])*n for i, n in enumerate(range(10, 1, -1))) % 11
    cd = '0' if cd == 11 else 'X' if cd == 10 else str(cd)
    isbn10 += cd
    return isbn10

def load_isbns():
    isbns = []
    with open('books.txt', 'r') as f:
        base = 'ISBN: '
        pattern = base + '\d{13}'
        lines = f.readlines()
        for line in lines:
            isbn13 = re.match(pattern, line).group().replace(base, '')
            isbns.append(isbn13)
    return isbns


def load_asins():
    asins = []
    with open('asins.txt', 'r') as f:
        asins = f.read().strip().split('\n')
    return asins

def auth_amazon():
    keys = None
    with open('aws_keys.json', 'r') as f:
        keys = json.loads(f.read())
    access_key = keys['AWS_ACCESS_KEY']
    secret_key = keys['AWS_SECRET_KEY']
    ass_tag = keys['AMAZON_ASSOCIATE_TAG']
    return api.Amazon(access_key, secret_key, ass_tag, Region='JP')

def build_books(asins):
    books_info_df = pd.DataFrame(columns=COLUMNS)
    amazon = auth_amazon()
    for i, asin in enumerate(asins):
        res = item_lookup(amazon, ItemId=asin, ResponseGroup='Large')
        with open('res.html', 'w') as f:
            f.write(res)
        soup = BeautifulSoup(res, 'lxml')
        item = soup.find('itemattributes')
        if item is None:
            continue
        title = item.find('title').text if item.find('title') is not None else ''
        lowestprice = soup.find('lowestusedprice').find('amount').text if soup.find('lowestusedprice') is not None else 'nan'
        price = int(lowestprice) + 1000 if lowestprice.isdigit() else DEFAULT_PRICE
        server = settings['server'][0]
        settings.ix[0, 'server'] = settings.ix[0, 'server'][:-1] + str(int(settings.ix[0, 'server'][-1]) % server_sum + 1)
        sku = settings['sku'][0]
        settings.ix[0, 'sku'] = 'sku' + str(int(sku.replace('sku', '')) + 1)
        sku = sku + '_' + shelf_number + '_' + str(i)
        date = str(dt.date.today())
        author = ''
        if item.find('author') is None:
            author = item.find('creator').text if item.find('creator') is not None else ''
        else:
            author = item.find('author').text
        publisher = item.find('publisher').text if item.find('publisher') is not None else ''
        publicationdate = item.find('publicationdate').text if item.find('publicationdate') is not None else ''
        pages = item.find('numberofpages').text if item.find('numberofpages') is not None else ''
        height = round(float(item.find('height').text) * 0.254) if item.find('height') is not None else ''
        length = round(float(item.find('length').text) * 0.254) if item.find('length') is not None else ''
        width = round(float(item.find('width').text) * 0.254) if item.find('width') is not None else ''
        weight = round(float(item.find('weight').text) * 4.53592) if item.find('weight') is not None else ''
        add_row = [asin, shelf_number, STATUS, server, title, CONDITION, CONDITION_NOTE, QUANTITY, price, sku, date, 'auto',
            MINIMUM_PRICE, author, publisher, publicationdate, pages, height, length, width, weight, '', '', '']
        add_row = dict(zip(COLUMNS, add_row))
        add_row = {k:[v] for k, v in add_row.items()}
        add_df = pd.DataFrame(add_row, columns=COLUMNS)
        books_info_df = pd.concat([books_info_df, add_df])
    return books_info_df

def main():
    isbns = load_asins()
    isbns = [convert_isbn_13_to_10(isbn) for isbn in isbns]
    books_df = build_books(isbns)
    #pd.options.display.float_format = '{:,.0f}'.format
    books_df.to_csv('tmp.csv', index=False)

if __name__ == '__main__':
    main()

settings.to_csv('settings.csv', index=False)
