DMV Census Tract Analysis Data - README
==========================================

This document explains how to work with the data in:
pre-processing/data/dmv_census_tract_analysis.json

OVERVIEW
--------
This file contains demographic analysis of DMV wait times by California census tract.
The key data you want is in the "tracts_by_category" section, which organizes census
tracts by their DMV wait time categories.

DATA STRUCTURE
--------------
The JSON file has three main sections:

1. "metadata": Information about when and how the data was generated
2. "summary_statistics": Overall statistics about wait times across all tracts
3. "tracts_by_category": Census tract data organized by wait time categories

TRACT DATA FIELDS
------------------
Each census tract in "tracts_by_category" contains:
- tract_id: Full FIPS code for the census tract
- tract_name: Short tract identifier
- county_fips: County FIPS code
- wait_time_minutes: Current DMV wait time in minutes
- wait_time_category: Categorized wait time (e.g., "No Wait (0 min)", "Very Long (61-90 min)")
- nearest_dmv_office: Name of closest DMV office
- nearest_dmv_address: Full address of closest DMV office
- distance_to_dmv_degrees: Distance to DMV in degrees (geographic)
- dmv_appointment_wait: Appointment wait time
- dmv_walkin_wait: Walk-in wait time
- color_hex: Color code for mapping/visualization

WAIT TIME CATEGORIES
--------------------
- No Wait (0 min): No current wait time
- Excellent (1-15 min): Very short wait
- Good (16-30 min): Reasonable wait time
- Moderate (31-45 min): Moderate wait time
- Long (46-60 min): Long wait time
- Very Long (61-90 min): Very long wait time
- Extremely Long (90+ min): Extremely long wait time
- No Data: No wait time data available

CONVERTING TO PANDAS DATAFRAME
===============================

Method 1: Convert all tracts to a single DataFrame
--------------------------------------------------
import json
import pandas as pd

# Load the JSON data
with open('pre-processing/data/dmv_census_tract_analysis.json', 'r') as f:
    data = json.load(f)

# Extract all tracts from all categories
all_tracts = []
for category, tracts in data['tracts_by_category'].items():
    all_tracts.extend(tracts)

# Convert to DataFrame
df = pd.DataFrame(all_tracts)
print(f"Total tracts: {len(df)}")
print(df.head())

Method 2: Work with specific wait time categories
-------------------------------------------------
import json
import pandas as pd

# Load the JSON data
with open('pre-processing/data/dmv_census_tract_analysis.json', 'r') as f:
    data = json.load(f)

# Get tracts with extremely long wait times
long_wait_tracts = data['tracts_by_category']['Extremely Long (90+ min)']
long_wait_df = pd.DataFrame(long_wait_tracts)

print(f"Tracts with 90+ minute waits: {len(long_wait_df)}")
print(long_wait_df[['tract_id', 'wait_time_minutes', 'nearest_dmv_office']].head())

Method 3: Create a summary by county
------------------------------------
import json
import pandas as pd

# Load and convert to DataFrame
with open('pre-processing/data/dmv_census_tract_analysis.json', 'r') as f:
    data = json.load(f)

all_tracts = []
for category, tracts in data['tracts_by_category'].items():
    all_tracts.extend(tracts)

df = pd.DataFrame(all_tracts)

# Group by county and calculate average wait times
county_summary = df.groupby('county_fips').agg({
    'wait_time_minutes': ['mean', 'median', 'count'],
    'tract_id': 'count'
}).round(2)

print("Wait time summary by county:")
print(county_summary)

Method 4: Filter and analyze specific conditions
------------------------------------------------
import json
import pandas as pd

# Load and convert to DataFrame
with open('pre-processing/data/dmv_census_tract_analysis.json', 'r') as f:
    data = json.load(f)

all_tracts = []
for category, tracts in data['tracts_by_category'].items():
    all_tracts.extend(tracts)

df = pd.DataFrame(all_tracts)

# Find tracts with wait times over 2 hours
extreme_waits = df[df['wait_time_minutes'] > 120]
print(f"Tracts with 2+ hour waits: {len(extreme_waits)}")

# Find the most common DMV offices causing long waits
problem_offices = df[df['wait_time_minutes'] > 90]['nearest_dmv_office'].value_counts()
print("\nDMV offices with most 90+ minute wait tracts:")
print(problem_offices.head(10))

USEFUL PANDAS OPERATIONS
========================
Once you have the DataFrame, you can:

# Basic statistics
df['wait_time_minutes'].describe()

# Filter by wait time category
no_wait_tracts = df[df['wait_time_category'] == 'No Wait (0 min)']

# Group by DMV office
office_stats = df.groupby('nearest_dmv_office')['wait_time_minutes'].agg(['mean', 'count'])

# Find tracts in specific counties (first 3 digits of tract_id)
alameda_tracts = df[df['tract_id'].str.startswith('06001')]  # Alameda County

# Sort by wait time
worst_waits = df.nlargest(20, 'wait_time_minutes')

NOTES
-----
- The data represents a snapshot in time (check metadata.generated_date)
- Distance is in degrees (you may want to convert to miles/km for analysis)
- Some tracts may have "No Data" for wait times
- Each tract is assigned to its nearest DMV office

For questions or issues with this data, refer to the analysis scripts in
the pre-processing/ directory. 