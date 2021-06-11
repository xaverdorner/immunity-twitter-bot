"""
This is a set of functions for the "days to herd immunity" twitter bot.
The bot calculates how many days will pass until enough people in Germany are
vaccinated to have reached herd immunity. It then generates a graph showing
average daily vaccinations and the remaining days to herd immunity and
posts that graph to twitter.
"""
# imports
import urllib
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.ticker import StrMethodFormatter
import seaborn as sns
import xlrd
import requests
import datetime as dt
import os
import tweepy
import config
import logging

# DOWNLOAD AND PROCESSING OF VACCINATION NUMBERS FROM RKI
# download location
RKI_EXCEL_URL = 'https://www.rki.de/DE/Content/InfAZ/N/Neuartiges_Coronavirus/Daten/Impfquotenmonitoring.xlsx?__blob=publicationFile'
def file_downloader(url):
    """function that downloads the vaccination data excel file from RKI and
    converts it to a pandas dataframe"""
    file = requests.get(url, allow_redirects=True)
    impffile = pd.read_excel(file.content, sheet_name='Impfungen_proTag')
    return impffile

# function that cleans the dataframe
def frame_cleaner(data_frame):
    """takes the rki dataframe with daily vaccinations, and outputs all entries
    that contain data as a clean data frame"""
    # Look for first date with data: RKI data usually not for current day, but up to a few days old
    first_day_index = None
    for day in range(7):
        current_day = dt.datetime.today() - dt.timedelta(days=day)
        current_day_clean = current_day.strftime('%d.%m.%Y')
        day_index = data_frame[data_frame['Datum'] == current_day_clean].index.values
        if not len(day_index) == 0:
            first_day_index = day_index[0]
            break
        else:
            pass
    # check if a value has been found
    if first_day_index == None:
        logging.warning('DataFrame contains no usable values in last 7 days')
    # new frame until today's index is exculding today (which is usually NaN in RKI data)
    clean_frame = data_frame.iloc[:(first_day_index+1)].copy()
    clean_frame.loc[:,'Datum'] = pd.to_datetime(clean_frame.loc[:,'Datum'], yearfirst=True, format='%d.%m.%Y')
    # adding short date format (day.month)
    clean_frame.loc[:,'Datum'] = clean_frame.loc[:,'Datum'].dt.strftime('%d.%m.')
    return clean_frame

# function to output all neccesary values for twitter post
def data_preparator(data_frame):
    """takes a cleaned dataframe and outputs a dictionary
    containing:
    - population required for German herd immunity
    - immunized population
    - missing population for herd immunity
    - percentage of immunized population
    - days to herd immunity
    """
    # check and warn if the column name has changed
    if 'Zweitimpfung' not in data_frame.columns:
        logging.warning('Column name in RKI data has changed')
    data_dict = {}
    current_date = data_frame['Datum'].iloc[-1]
    data_dict['data_as_of'] = current_date
    rolling_average = data_frame['Zweitimpfung'].rolling(7).mean()
    data_dict['pct_daily_chg'] = rolling_average.pct_change()
    # last value of rolling average of 'Zweitimpfung' vaccinations
    data_dict['avg_daily_vacs'] = int(rolling_average.iloc[-1])
    # calculate how many prople still need to be vaccinated
    GER_POP = 83_000_000
    # 0.7 * German population needs to be vaccinated for herd immnity
    data_dict['herd_pop'] = int(GER_POP * 0.7)
    data_dict['immu_pop'] = int(data_frame['Zweitimpfung'].cumsum().iloc[-1])
    data_dict['immu_percent'] = int((data_dict['immu_pop']/GER_POP)*100)
    # calculating still unvaccinated population
    data_dict['missing_pop'] = int(data_dict['herd_pop'] - data_dict['immu_pop'])
    data_dict['days_to_herd'] = int(data_dict['missing_pop']/data_dict['avg_daily_vacs'])
    avg_days_month = 30.43
    # getting a string to denote which part of the month immunity is achieved
    target_date = (dt.date.today() + dt.timedelta(days=data_dict['days_to_herd']))
    target_month = target_date.strftime("%B")
    target_year = target_date.strftime("%Y")
    avg_days_month = 30.43
    # segmenting days in a month in 3 parts
    month_third = int(avg_days_month//3)
    # creating 3 ranges for early, mid and late part of the month
    month_ranges = [range((third + 1) * (month_third)) for third in range(3)]
    # creating corresponding strings for the ranges
    month_segments = ['early ', 'mid-', 'late ']
    # zipping ranges and strings together
    month_segment_dict = list(zip(month_segments, month_ranges)) # zip can only used once -> to list
    # extracting the correct string from the month segment dict
    target_third = [third[0] for third in month_segment_dict if target_date.day in third[1]][0]
    # stiching all info together for an info string
    target_month_info_string = target_third+target_month+' '+target_year
    data_dict['immunity_month_string'] = target_month_info_string
    return data_dict

### function that plots daily vacs vs required vacs
def vac_plotter(dataframe, result_dict):
    """generates a plot showing current vaccination numbers
    and days to herd immunity"""
    plt.tight_layout()
    fig, ax = plt.subplots(figsize=(8,4.5))
    # getting plot height by using biggest value in month dataset
    y_max_value = dataframe['Gesamtzahl verabreichter Impfstoffdosen'].iloc[-30:].max()
    plot_height = ax.set_ylim([0, y_max_value+100_000])
    current_date = dataframe['Datum'].iloc[-1]
    # setting ',' as thousands separator
    ax.yaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
    ax.grid(axis='y')
    ax.title.set_text(f'DAILY VACCINATIONS IN GERMANY (data as of: {current_date})')
    ax.set_xlabel('DATE')
    ax.set_ylabel('DAILY VACCINATIONS')
    # rotate x-axis 45 degrees to for readability
    ax.tick_params(axis='x', rotation=-45)
    x_text_pos = len(dataframe['Datum'].iloc[-30:].values) * 0.15
    ax.text(x_text_pos, plot_height[1]*0.7, f"{result_dict['days_to_herd']} days left", size=22, rotation=0,
             ha="center", va="center",
             bbox=dict(boxstyle="round", ec=(1., 0.5, 0.5), fc=(1., 0.9, 0.8)))
    # defining the same x-axis for all elements of the plot
    xaxis_month_values = dataframe['Datum'].iloc[-30:].values
    firstdose_values = dataframe['Erstimpfung'].iloc[-30:].values
    immunized_values = dataframe['Zweitimpfung'].iloc[-30:].values
    immunized_bar = ax.bar(x=xaxis_month_values, height=immunized_values, color='#223843', label='immun. vacs/day')
    firstdose_bar = ax.bar(x=xaxis_month_values, bottom=immunized_values, height=firstdose_values, color='#DBD3D8', label='first dose vacs/day')
    # using 37 values, to be able to drop 7 Na values and also have 30 in total
    rolling_average = dataframe['Zweitimpfung'].iloc[-36:].rolling(7).mean().dropna()
    average_line = ax.plot(xaxis_month_values, rolling_average, color="red", linewidth=2, linestyle="--", label='immun. vacs/7-day-avg. ')
    ax.legend()
    plt.savefig('/tmp/daily_vacs.png')

def twitter_texter(result_dict):
    """generates a string using vaccination metrics in the dicctionary
    from the data preparation function"""
    twitter_text = f'Vaccination projection GERMANY:\nRequired population for herd immunity (HI): {result_dict["herd_pop"]/1_000_000} Mio. (70% of total)\nCurrent daily immunizing vaccinations: {result_dict["avg_daily_vacs"]}\nRemaining time at current speed: {result_dict["days_to_herd"]} days ({result_dict["immunity_month_string"]})'
    return twitter_text

# a function that posts images to twitter
def twitter_poster(text):
    """posts graph and text to twitter as an update"""
    auth = tweepy.OAuthHandler(config.API_KEY, config.API_SECRET_KEY)
    auth.set_access_token(config.ACCESS_TOKEN, config.ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    api.update_with_media('/tmp/daily_vacs.png', status=text)

if __name__ == "__main__":
    try:
        url = tbh.RKI_EXCEL_URL
        vac_file = file_downloader(url)
        clean_frame = frame_cleaner(vac_file)
        immu_days = days_to_immunity(clean_frame)
        img = image_generator(immu_days)
        twitter_poster()
        print('Bot ran successfully')
    except Exception as ex:
        print(ex)
