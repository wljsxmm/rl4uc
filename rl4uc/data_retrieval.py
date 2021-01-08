#!/usr/bin/env python

import pandas as pd
import os
import requests
import io
import dotenv

def get_wind_data(start_date, end_date, unit_id):

	COLUMNS = ['Settlement Date', 'SP', 'Quantity (MW)'] # specify only these required columns

	date_range = pd.date_range(start_date, end_date).tolist()
	date_range = [f.strftime('%Y-%m-%d') for f in date_range]
	all_df = pd.DataFrame(columns=COLUMNS)

	for date in date_range: 
	    url = 'https://api.bmreports.com/BMRS/B1610/v2?APIKey={}&SettlementDate={}&Period=*&ServiceType=csv&NGCBMUnitID={}'.format(API_KEY, date, unit_id)
	    response = requests.get(url, allow_redirects=True)
	    df = pd.read_csv(io.StringIO(response.content.decode('utf-8')), header=1).filter(COLUMNS)
	    all_df = all_df.append(df)

	# Sort and rename cols
	all_df = all_df.sort_values(['Settlement Date', 'SP']).reset_index(drop=True)
	all_df = all_df.rename(columns={'Settlement Date': 'date', 'SP': 'period', 'Quantity (MW)': 'wind_mw'})
	all_df.date = pd.to_datetime(all_df.date)

	return all_df 

def get_demand_data(start_date, end_date):
	date_range = pd.date_range(start_date, end_date).tolist()
	date_range = [f.strftime('%Y-%m-%d') for f in date_range]

	COLUMNS = ['date', 'period', 'demand_mw']
	all_df = pd.DataFrame(columns=COLUMNS)

	for date in date_range:
		url = 'https://api.bmreports.com/BMRS/SYSDEM/v1?APIKey={}&FromDate={}&ToDate={}&ServiceType=csv'.format(API_KEY, date, date)
		response = requests.get(url, allow_redirects=True)
		df = pd.read_csv(io.StringIO(response.content.decode('utf-8'))).reset_index()

		# Rename columns
		df = df.rename(columns={'level_0': 'type', 'level_1': 'date', 'HDR': 'period', 'SYSTEM DEMAND': 'demand_mw'})

		# Get just ITSDO standing for Initial Transmission System Demand Outturn
		df = df[df.type=='ITSDO']

		# Reformat dates and periods
		df.date = pd.to_datetime(df.date, format='%Y%m%d')
		df.period = df.period.astype('int')

		df = df.filter(COLUMNS)

		all_df = all_df.append(df)

	all_df.date = pd.to_datetime(all_df.date)

	return all_df

if __name__=="__main__":

	dotenv.load_dotenv('../.env')
	API_KEY = os.getenv('BMRS_KEY')

	SAVE_DIR = 'data'
	os.makedirs(SAVE_DIR, exist_ok=True)

	WIND_UNIT_ID = 'WHILW-1' # specify the BM Unit ID to retrieve for wind data
	WIND_PEN = 0.07 # desired wind penetration as a decimal

	# Dates for entire date set
	start_date = '2015-01-01'
	end_date = '2019-12-31'

	# Train/test split dates ([0] is beginning [1] is end)
	train_dates = ('2015-01-01', '2018-12-31')
	test_dates = ('2019-01-01', '2019-12-31')

	print("Getting demand data...")
	demand_df = get_demand_data(start_date, end_date)
	print("Getting wind data...")
	wind_df = get_wind_data(start_date, end_date, WIND_UNIT_ID)

	all_df = pd.merge(demand_df, wind_df, on=['date', 'period'])
	train_df = all_df[(all_df.date >= train_dates[0]) & (all_df.date <= train_dates[1])]
	test_df = all_df[(all_df.date >= test_dates[0]) & (all_df.date <= test_dates[1])]

	# Now we need to scale wind such that it meets the desired wind penetration throughout the data set 
	# Scale linearly by a factor of target total wind / current total wind 
	current_wind = sum(all_df.wind_mw) 
	target_wind = sum(all_df.demand_mw) * WIND_PEN
	all_df.wind_mw = all_df.wind_mw * target_wind / current_wind 

	# Check that wind never exceeds demand. 
	assert(all(all_df.demand_mw > all_df.wind_mw)), "demand exceeds wind at some timesteps. turn down wind penetration"

	# Save to .csv
	train_df.to_csv(os.path.join(SAVE_DIR, 'train_data.csv'), index=False)
	test_df.to_csv(os.path.join(SAVE_DIR, 'test_data.csv'), index=False)











