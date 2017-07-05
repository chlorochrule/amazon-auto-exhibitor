#-*- coding: utf-8 -*-
import json
import pandas as pd
import re

settings = pd.read_csv('settings.csv')
max_shipping_fee = settings.ix[0, 'max_shipping_fee']

CONDITIONS = None
with open('./cond_note/conditions.json') as fh:
    CONDITIONS = json.loads(unicode(fh.read()))

BASETEXT = None
with open('./cond_note/basetext.txt') as fh:
    BASETEXT = fh.read()

def render_parts(parts_condition):
    condition_note_text = ''
    parts_type = re.findall('[a-z]+', parts_condition)[0]
    parts_dict = CONDITIONS[parts_type]
    if not re.search('[0-9]+', parts_condition):
        condition_note_text = parts_dict['all_ok_text']
    else:
        numbers = parts_condition.replace(parts_type, '')
        if len(numbers) < 3:
            return ''
        header = parts_dict['header'][int(numbers[0])]
        footer = parts_dict['footer'][int(numbers[-1])]
        delimiter = parts_dict['delimiter']
        status = reduce(lambda x, y: x + delimiter + y, [parts_dict['status'][int(i)] for i in numbers[1:-1]])
        condition_note_text = header + status + footer
    return parts_dict['basetext'].format(condition_note_text)

def teikeigai(weight):
    if weight < 50:
        return 120
    elif weight < 100:
        return 140
    elif weight < 150:
        return 205
    elif weight < 250:
        return 250
    elif weight < 500:
        return 400
    elif weight < 1000:
        return 600
    elif weight < 2000:
        return 870
    elif weight < 4000:
        return 1180
    else:
        print 'Too large!!\nPlease check your input: Missing or Invalid.'
        return max_shipping_fee

def calc_shipping_fee(height, length, width, weight):
    total_length = height + length + width
    if weight > 4000 or max(height, length, width) > 600 or total_length > 900:
        print 'Too large!!\nPlease check your input: Missing or Invalid.'
        return max_shipping_fee
    elif length > 307 or width > 217 or total_length > 520:
        return teikeigai(weight)
    elif weight < 250:
        return teikeigai(weight)
    elif height < 30:
        return 360
    else:
        return 510

def render_note(note):
    condition_note_text = ''
    if len(note) != 9:
        return ''
    numbers = note.replace('n', '')
    keys = ['header', 'where1', 'where2', 'how', 'what1', 'what2', 'status', 'footer']
    for k, i in zip(keys, list(numbers)):
        condition_note_text += CONDITIONS['n'][k][int(i)]
    return CONDITIONS['n']['basetext'].format(condition_note_text)

def render_condition_note(condition_note):
    condition_note_text = ''
    for parts_condition in re.findall('box[0-9]*|cover[0-9]*|body[0-9]*', condition_note):
        condition_note_text += render_parts(parts_condition)
    for note in re.findall('n[0-9]+', condition_note):
        condition_note_text += render_note(note)
    return condition_note_text

def main():
    books_df = pd.read_csv('tmp.csv')
    for i, book_row in books_df.iterrows():
        condition_note = book_row['condition_note']
        condition_note_text = BASETEXT.format(render_condition_note(condition_note)).strip()
        books_df.ix[i, 'condition_note_text'] = condition_note_text
        height = books_df.ix[i, 'height']
        length = books_df.ix[i, 'length']
        width = books_df.ix[i, 'width']
        weight = books_df.ix[i, 'weight']
        books_df.ix[i, 'shipping_fee'] = calc_shipping_fee(height - 1, length, width, weight * 1.1)
    books_df['quantity'] = books_df['quantity'].astype(int)
    books_df['price'] = books_df['price'].astype(int)
    books_df['minimum_price'] = books_df['minimum_price'].astype(int)
    books_df['numberofpages'][books_df['numberofpages'] != books_df['numberofpages']] = -1.
    books_df['numberofpages'] = books_df['numberofpages'].astype(int)
    books_df['height'] = books_df['height'].astype(int)
    books_df['length'] = books_df['length'].astype(int)
    books_df['width'] = books_df['width'].astype(int)
    density = 0.00070006621629
    df_3_values = books_df[['height', 'length', 'width']][books_df['weight'] != books_df['weight']]
    df_3_values = density * df_3_values['height'] * df_3_values['length'] * df_3_values['width']
    books_df['weight'][books_df['weight'] != books_df['weight']] = df_3_values.round()
    books_df['weight'] = books_df['weight'].astype(int)
    books_df['shipping_fee'] = books_df['shipping_fee'].astype(int)
    books_df.to_csv('exhibit.csv', index=False)
    settings.ix[0, 'db_locked'] = False
    settings.to_csv('settings.csv', index=False)

if __name__ == '__main__':
    main()
