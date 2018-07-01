#!/usr/bin/python3

import os
import argparse
import time
import datetime
import re
from progress.bar import FillingSquaresBar
from bs4 import BeautifulSoup
from selenium import webdriver

import credentials


# a workaround to allow Chromedriver to download files while in headless mode.
# See https://bugs.chromium.org/p/chromium/issues/detail?id=696481#c86 for
# details.
def enable_download_in_headless_chrome(driver, download_dir):
    """
    Pass a Selenium webdriver `driver` to enable file downloads for a headless
    Chrome browser.  The driver is configured to download files to
    `download_dir`
    """

    send_command = ("POST", '/session/$sessionId/chromium/send_command')
    driver.command_executor._commands["send_command"] = send_command

    params = {'cmd': 'Page.setDownloadBehavior',
              'params': {'behavior': 'allow', 'downloadPath': download_dir}}
    driver.execute("send_command", params)


# construct and return a Selenium driver for use with the eoddata service
def construct_eoddate_driver(download_dir):
    """
    Construct and return a Selenium driver that is configured to download files
    to `download_dir`
    """

    # this process takes a few seconds so provide some feedback to the user
    print('Initializing the browser and providing credentials to eoddata...')

    # set up Chrome options to enable downloads to `download_dir` when not in
    # headless mode
    chrome_options = webdriver.ChromeOptions()
    prefs = {'download.default_directory': download_dir}
    chrome_options.add_experimental_option('prefs', prefs)
    chrome_options.add_argument('--headless')

    # construct driver
    driver = webdriver.Chrome(chrome_options=chrome_options)
    enable_download_in_headless_chrome(driver, download_dir)

    # go to eoddata main page
    driver.get('http://www.eoddata.com/')

    # enter account email
    text_area_email = driver.find_element_by_id('ctl00_cph1_lg1_txtEmail')
    text_area_email.send_keys(credentials.credentials['eoddata']['id'])
    # enter account password
    text_area_pw = driver.find_element_by_id('ctl00_cph1_lg1_txtPassword')
    text_area_pw.send_keys(credentials.credentials['eoddata']['password'])
    # click on the submit button
    button_submit = driver.find_element_by_id('ctl00_cph1_lg1_btnLogin')
    button_submit.click()

    return driver


# verify that the user has supplied valid dates
def check_valid_dates(start_date, end_date, n_days_history):
    """
    Provide datetime.date objects `start_date` and `end_date` and integer
    `n_days_history` to check that the dates are valid.
    """

    today = datetime.datetime.today().date()
    n_days_timedelta = datetime.timedelta(days=n_days_history)
    earliest_day = today - n_days_timedelta
    if start_date < earliest_day:
        raise ValueError('The eoddata service only lets you look back 30 '
                         'days.  The specified starting date was {0} on '
                         'today\'s date of {1}.'.format(start_date, today))

    if today < start_date:
        raise ValueError('The specified starting date of {0} is after '
                         'today\'s date of {1}.'.format(earliest_day, today))

    if end_date < start_date:
        raise ValueError('The specified starting date of {0} is after the '
                         'specified ending date of '
                         '{1}.'.format(start_date, end_date))


# perform the data download from the eoddata service
def download_from_eoddata(start_date, end_date, market, driver):
    """Provide datetime.date arguments `start_date` and `end_date`, a string
    `market`, and Selenium driver `driver`.  The function will then download
    the EOD data for the appropriate market and dates from the eoddata
    """

    # navigate to the downloads page
    driver.get('http://www.eoddata.com/download.aspx')

    # get a list of the all of the hyperlink tags in the pagen
    bs_obj = BeautifulSoup(driver.page_source, "lxml")
    url_list = bs_obj.find_all('a')

    # each iteration steps through the list of hyperlink tags in the page until
    # it finds the list of example downloads, and then extracts the `k` field
    k = ''
    for url in url_list:

        if not url.has_attr('href'):
            continue

        # looks for a link of the form
        # /data/filedownload.aspx?e=INDEX&sd=20180606&ed=20180606&d=4&k=ph72h4ynw2&o=d&ea=1&p=0
        # Once we find one, we need to extract the `k` field so that we can use
        # it when constructing our own HTML request.
        url_string = url.attrs['href']
        if re.match('/data/filedownload.aspx', url_string):
            k = re.search('k=([^&]*)', url_string).group(1)
            break
    if not k:
        raise Exception

    # construct the URL according to the dates and market that we want to
    # download
    url_template = '{url_base}?e={e}&sd={sd}&ed={ed}&d={d}&k={k}&o={o}&ea={ea}&p={p}'
    url_download = url_template.format(
        url_base='http://www.eoddata.com/data/filedownload.aspx',
        e=market,
        sd=start_date.strftime('%Y%m%d'),
        ed=end_date.strftime('%Y%m%d'),
        d='4',
        k=k,
        o='d',
        ea='1',
        p='0'
    )
    # submit the download request
    driver.get(url_download)

    # wait for 10 seconds to ensure that the file has time to download
    bar = FillingSquaresBar('Downloading data ', max=100)
    for i in range(100):
        bar.next()
        time.sleep(0.1)
    bar.finish()


# a data structure that specifies the functions that are used to download the
# data for a given service
service_info = {
    'eoddata': {'construct_driver_fcn': construct_eoddate_driver,
                'download_data_fcn':    download_from_eoddata,
                'n_days_history':       30}
}


# download the EOD data for a given market `market` during the interval of time
# specified by `start_date` and `end_date` using service `service`, and placing
# the downloaded data in the directory `download_dir`
def download_stock_vals(start_date, end_date, market, download_dir, service):
    """
    `start_date` and `end_date` are datetime.date objects.  `market` is a
    string describing specifying the stock market of interest, `download_dir`
    is a string specifying what directory to place the downloaded data into,
    and `service` is a string specifying the service that we are using to
    download the data.
    """

    # look up the appropriate functions to use for the specified service
    construct_driver_fcn = service_info[service]['construct_driver_fcn']
    download_data_fcn = service_info[service]['download_data_fcn']

    # call the initialization and downloading routines
    try:
        driver = construct_driver_fcn(download_dir)
        download_data_fcn(start_date, end_date, market, driver)
    except Exception:
        raise
    finally:
        driver.close()


if __name__ == '__main__':

    # construct the argument parser
    ap = argparse.ArgumentParser()
    ap.add_argument('-s',
                    '--start_date',
                    required=True,
                    help='The earliest date for which to request EOD data, in the form YYYY-MM-DD.')
    ap.add_argument('-e',
                    '--end_date',
                    required=True,
                    help='The latest date for which to request EOD data, in the form YYYY-MM-DD.')
    ap.add_argument('-m',
                    '--market',
                    required=True,
                    help='The desired stock market.')
    ap.add_argument('-d',
                    '--download_dir',
                    required=True,
                    help='The directory into which the data is written.')
    ap.add_argument('-v',
                    '--service',
                    required=True,
                    help='The name of the service to query for the data.')
    # parse the command-line arguments
    args = vars(ap.parse_args())

    # check that the EOD service is known
    if args['service'] not in service_info:
        raise ValueError('The {0} service is not known'.format(args['service']))

    # convert date strings to `datetime.date` objects
    start_date_canon = datetime.datetime.strptime(args['start_date'], '%Y-%m-%d').date()
    end_date_canon = datetime.datetime.strptime(args['end_date'], '%Y-%m-%d').date()
    # check that dates make sense
    check_valid_dates(start_date_canon,
                      end_date_canon,
                      service_info[args['service']]['n_days_history'])

    # check that directory for downloads exists and is writeable
    if not os.access(args['download_dir'], os.W_OK | os.X_OK):
        raise ValueError('The specified directory of {0} does not exist or we '
                         'don\'t have permission to '
                         'access it.'.format(args['download_dir']))

    # call the main function to download EOD data
    download_stock_vals(start_date_canon,
                        end_date_canon,
                        args['market'],
                        args['download_dir'],
                        args['service'])
