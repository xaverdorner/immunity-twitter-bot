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
        current_day_clean = current_day.replace(hour=0, minute=0, second=0,microsecond=0)
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
    clean_frame.loc[:,'Datum'] = pd.to_datetime(clean_frame.loc[:,'Datum'], yearfirst=True, format='%D.%M.%Y')
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
    - days to herd immunity
    - sustainable vaccination speed to achieve herd immunity
    """
    # check and warn if the column name has changed
    if 'Vollständig geimpft' not in data_frame.columns:
        logging.warning('Column name in RKI data has changed')
    data_dict = {}
    rolling_average = data_frame['Vollständig geimpft'].rolling(7).mean()
    data_dict['pct_daily_chg'] = rolling_average.pct_change()
    # last value of rolling average of 'Vollständig geimpft' vaccinations
    data_dict['avg_daily_vacs'] = int(rolling_average.iloc[-1])
    # calculate how many prople still need to be vaccinated
    GER_POP = 83_000_000
    # 0.7 * German population needs to be vaccinated for herd immnity
    data_dict['herd_pop'] = int(GER_POP * 0.7)
    data_dict['immu_pop'] = int(data_frame['Vollständig geimpft'].cumsum().iloc[-1])
    data_dict['missing_pop'] = int(data_dict['herd_pop'] - data_dict['immu_pop'])
    data_dict['days_to_herd'] = int(data_dict['missing_pop']/data_dict['avg_daily_vacs'])
    avg_days_month = 30.43
    vac_immu_duration = 5*avg_days_month
    # vaccination speed must be enough to achieve herd immunity before individual immunity wears off
    data_dict['sustain_vac_speed'] = int(data_dict['herd_pop']/vac_immu_duration)
    return data_dict

### function that plots daily vacs vs required vacs
def vac_plotter(dataframe, result_dict):
    """generates a plot showing current vaccination numbers
    and days to herd immunity"""
    # find first index with non-zero values
    frame_len = dataframe.shape[0]
    first_nonzero = dataframe[dataframe['Vollständig geimpft'].ne(0)].shape[0]
    start_index = frame_len - first_nonzero
    # creating canvas, axis labels
    plt.figure(figsize=(8,4.5))
    plt.tight_layout()
    plot_height = plt.ylim([0, 450_000])
    plt.title('DAILY IMMUNIZING VACCINATIONS IN GERMANY')
    plt.xlabel('DATE')
    plt.ylabel('DAILY VACCINATIONS (immunizing dose)')
    plt.grid(axis='y')
    plt.xticks(rotation=-45)
    # define a relative position for the text on the x axis
    x_text_pos = len(dataframe['Datum'].iloc[start_index:].values) * 0.175
    plt.text(x_text_pos, plot_height[1]*0.75, f"{result_dict['days_to_herd']} days left", size=22, rotation=0,
            ha="center", va="center",
            bbox=dict(boxstyle="round", ec=(1., 0.5, 0.5), fc=(1., 0.9, 0.8)))
    bar = plt.bar(x=dataframe['Datum'].iloc[start_index:].values, height=dataframe['Vollständig geimpft'].iloc[start_index:].values, color='blue', label='avg. immun. vacs/day')
    line = plt.axhline(result_dict['sustain_vac_speed'], color="r", linestyle="--", label='req. immun. vacs/day')
    plt.legend()
    plt.savefig('/tmp/daily_vacs.png')

def twitter_texter(result_dict):
    """generates a string using vaccination metrics in the dicctionary
    from the data preparation function"""
    twitter_text = f'Vaccination projection GERMANY:\nRequired population for herd immunity (HI): {result_dict["herd_pop"]/1_000_000} Mio. (70% of total)\nCurrent daily immunizing vaccinations: {result_dict["avg_daily_vacs"]}\nRemaining time at current speed: {result_dict["days_to_herd"]} days'
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
