#!/usr/bin/python3

import pandas as pd
import warnings


def read_eod_data(letter):
    """
    download a page from the most recent NASDAQ quotes from
    http://eoddata.com/, for all stocks whose tickers start with `letter`
    """

    # location of the EOD webpages
    eod_url = 'http://eoddata.com/stocklist/NASDAQ/{0}.htm'
    # attempt data download
    eod_data = pd.read_html(eod_url.format(letter),
                            match='Volume',
                            header=0)[0]

    # drop junk columns (corresponding to clickeable images in the website)
    eod_data = eod_data.drop(labels=['Unnamed: 7', 'Unnamed: 9'],
                             axis=1)
    # change one of the column names to something more descriptive
    eod_data = eod_data.rename({'Unnamed: 8': 'Change2'}, axis='columns')

    return eod_data


def get_letters_list(tickers):
    """
    eoddata.com displays the EOD data on separate pages depending on the first
    letter of each stock's ticker name, so we begin by figuring out which pages
    have stocks on them that we want by picking off the first letter of each
    ticker, and returning a list of all of the unique letters that were
    obtained
    """

    # case: no tickers provided, defaults to downloading all stock EOD data
    if tickers is None:
        letters = ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I',
                   'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R',
                   'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z')
    # case: tickers are provided, so step through them one-at-a-time and pick
    # off the first letter of every ticker
    else:
        letters_set = set()
        for curr_ticker in tickers:
            letters_set.add(curr_ticker[0])
        letters = sorted(letters_set)

    # note that this returns a sequence in all scenarios
    return letters


def get_vals_from_eoddata(tickers=None, n_tries=5, read_eod_fn=read_eod_data):
    """
    scrapes the most recent NASDAQ EOD stock data available from
    http://eoddata.com.  The default value for `tickers` returns all available
    stock quotes.  `n_tries` specifies the number of times we will try to
    download a page of quotes before giving up, and `read_eod_fn` specifies the
    function used to perform the download.
    """

    # obtain a list of the
    letters = get_letters_list(tickers)

    # each iteration attempts to read the EOD data for the current letter and
    # append the resulting DataFrame to `stock_vals`
    stock_vals = []
    for let in letters:

        # attempt to read the data for the current letter as many as `n_tries`
        # times, and will throw an error if the data can't be downloaded by
        # then.  If the download is successful then the resulting DataFrame is
        # appended to `stock_vals`
        for i in range(n_tries):
            try:
                curr_table = read_eod_fn(let)
                stock_vals.append(curr_table)
            except Exception:
                continue
            else:
                break
        # download was not successful, throw an error
        else:
            msg = 'Failed scraping letter {0} after {1} tries'
            raise Exception(msg.format(let, n_tries))

    # row-bind the stock values for the individual letters into a single
    # DataFrame
    combined = pd.concat(stock_vals)
    # conditionally subset to specified stock entries
    if tickers is not None:
        combined = combined[combined['Code'].isin(tickers)]
    combined.reset_index(drop=True, inplace=True)

    # provide a warning if any of the tickers that were provided aren't in the
    # downloaded data
    tickers_in_eod_bool = pd.Series(tickers).isin(combined['Code'])
    if (~tickers_in_eod_bool).any():
        tickers_not_in = pd.Series(tickers)[~tickers_in_eod_bool]
        msg = 'the following stocks were not found.\n'
        warnings.warn(msg + tickers_not_in.to_string(index=False))

    return combined


# get all stock values and print DataFrame
if __name__ == '__main__':

    stock_vals_single = get_vals_from_eoddata(['AAPL'])
    print(stock_vals_single)

    stock_vals_multiple = get_vals_from_eoddata(['AAPL',
                                                 'GOOGL',
                                                 'MSFT',
                                                 'AMZN'])
    print(stock_vals_multiple)

    stock_vals_missing = get_vals_from_eoddata(['AAPL',
                                                'NOTASTOCK'])
    print(stock_vals_missing)
