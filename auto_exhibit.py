#-*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from sqlalchemy import create_engine
import json
import time
import pandas as pd
from datetime import datetime, timedelta

settings = pd.read_csv('settings.csv')
intervals = int(settings.ix[0, 'intervals'])
db_locked = bool(settings.ix[0, 'db_locked'])

ASC_URL = 'https://sellercentral.amazon.co.jp/'
SIGNIN_URL = 'https://sellercentral.amazon.co.jp/ap/signin'

def get_driver(driver_type='pjs'):
    if driver_type == 'pjs':
        pjs_path = './webdriver/phantomjs'
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'
        dcap = {
            'phantomjs.page.settings.userAgent' : user_agent,
            'marionette' : True
        }
        driver = webdriver.PhantomJS(executable_path=pjs_path, desired_capabilities=dcap)
    elif driver_type == 'chrome':
        driver = webdriver.Chrome('./webdriver/chromedriver')
    else:
        raise Exception('Such driver {} was not founded'.format(driver_type))
    return driver

def signedin(driver):
    driver.get(ASC_URL)
    return SIGNIN_URL in driver.current_url

def login_to_asc(driver, email, passwd):
    driver.get(ASC_URL)
    driver.find_element_by_id('ap_email').send_keys(email)
    driver.find_element_by_id('ap_password').send_keys(passwd)
    driver.find_element_by_id('signInSubmit').click()
    return driver

def dispatch_condition(condition):
    dispatch_table = {
        'nw': 'new, new',
        'ln': 'used, like_new',
        'vg': 'used, very_good',
        'gd': 'used, good',
        'ac': 'used, acceptable',
        'cln': 'collectible, like_new',
        'cvg': 'collectible, very_good',
        'cgd': 'collectible, good',
        'cac': 'collectible, acceptable'
    }
    return dispatch_table[condition]

def exhibit(driver, book, *login_info):
    if signedin(driver):
        driver = login_to_asc(*login_info)
    exh_url = 'https://catalog-sc.amazon.co.jp/abis/Display/ItemSelected?asin=' + str(book['asin'])
    driver.get(exh_url)
    WebDriverWait(driver, 60).until(
        EC.element_to_be_clickable((By.XPATH, '//label[@for="advanced-view-switch-top"]/span'))
    ).click()
    driver.find_element_by_id('standard_price').send_keys(int(book['price']))
    driver.execute_script('document.productForm.condition_note.value = "' + book['condition_note_text'] + '";')
    driver.find_element_by_id('quantity').send_keys(int(book['quantity']))
    driver.find_element_by_id('item_sku').send_keys(book['sku'])
    cond_elem = driver.find_element_by_id('condition_type')
    Select(cond_elem).select_by_value(dispatch_condition(book['condition']))
    WebDriverWait(driver, 60).until(
        EC.element_to_be_clickable((By.ID, 'main_submit_button'))
    ).click()

def main():
    email = 'your_email'
    passwd = 'your_password'
    books = pd.read_csv('exhibit.csv')
    driver = get_driver(driver_type='chrome')
    login_info = (driver, email, passwd)
    driver = login_to_asc(*login_info)
    local_engine = create_engine('your_database_url')
    url_text = None
    with open('database_url.json', 'r') as fh:
        url_text = fh.read()
    database_url = json.loads(url_text)
    engines = {server: create_engine(database_url[server]) for server in database_url}

    if db_locked:
        print 'Database is locking now!'
        return

    for i, book in books.iterrows():
        print 'Exhibiting row: {}'.format(i)
        exhibit(driver, book, *login_info)
        server = book['server']
        heroku_engine = create_engine(database_url[server])
        book = pd.DataFrame(book).T
        book.to_sql('books', engines[server], if_exists='append', index=False)
        book.to_sql('books', local_engine, if_exists='append', index=False)
        books = books[books['sku'] != book.ix[i, 'sku']]
        books.to_csv('exhibit.csv', index=False)
        time.sleep(intervals)
    settings.ix[0, 'db_locked'] = True

def ending():
    start = settings.ix[0, 'start_time']
    start = datetime.strptime(start, '%Y-%m-%d %H:%M:%S.%f')
    exec_time = datetime.now() - start
    progress = max(pd.read_csv('tmp.csv').index) + 1
    wtap = pd.read_csv('working_time_and_progress.csv')
    previous_worked_date = datetime.strptime(wtap.ix[max(wtap.index), 'date'], '%Y-%m-%d').date()
    previous_worked_date += timedelta(days=1)
    while previous_worked_date < datetime.now().date():
        wtap = pd.concat([wtap, pd.DataFrame([previous_worked_date, 0, '0:00:00.000000'], index=wtap.columns).T])
        previous_worked_date += timedelta(days=1)
    if wtap[wtap['date'] == datetime.now().date().strftime('%Y-%m-%d')].empty:
        wtap = pd.concat([wtap, pd.DataFrame([datetime.now().date(), progress, exec_time], index=wtap.columns).T])
    else:
        wtap.ix[max(wtap.index), 'progress'] += progress
        previous_time = datetime.strptime(wtap.ix[max(wtap.index), 'wtime'], '%H:%M:%S.%f')
        wtap.ix[max(wtap.index), 'wtime'] = timedelta(hours=previous_time.hour,
            minutes=previous_time.minute,
            seconds=previous_time.second,
            microseconds=previous_time.microsecond) + exec_time
    wtap.to_csv('working_time_and_progress.csv', index=False)
    wtap = pd.read_csv('working_time_and_progress.csv')
    input_time = datetime.strptime(wtap.ix[max(wtap.index), 'wtime'], '%H:%M:%S.%f')
    input_time = timedelta(hours=input_time.hour,
        minutes=input_time.minute,
        seconds=input_time.second,
        microseconds=input_time.microsecond)
    print '\n****** Today input data ******'
    print 'Inputed amount: {} [books]'.format(wtap.ix[max(wtap.index), 'progress'])
    print 'Input time: {}'.format(input_time)
    print 'Input speed: {} [seconds/book]'.format(input_time.total_seconds()/wtap.ix[max(wtap.index), 'progress'])
    print '***end***'
    aia = wtap['progress'].sum() / (max(wtap.index) + 1)
    total_time = timedelta(hours=0,
        minutes=0,
        seconds=0,
        microseconds=0)
    for i, row in wtap.iterrows():
        itime = datetime.strptime(row['wtime'], '%H:%M:%S.%f')
        itime = timedelta(hours=itime.hour,
            minutes=itime.minute,
            seconds=itime.second,
            microseconds=itime.microsecond)
        total_time += itime
    ave_itime = total_time / wtap['progress'].sum()
    print '\n****** Average input data ******'
    print 'Average inputed amount: {} [books/day]'.format(aia)
    print 'Average input speed: {} [seconds/book]'.format(ave_itime.total_seconds())
    print '***end***'
    settings.to_csv('settings.csv', index=False)

if __name__ == '__main__':
    main()
    print 'All product was exhibited successfully!'
    ending()
