# DMV Wait Times Data Collection

This project scrapes and analyzes DMV wait times data from [https://www.dmvwaittimes.live](https://www.dmvwaittimes.live).

## Data Collection Summary

✅ **Scraped actual table data from 176 California DMV offices**
- Properly scraped the main table to get real office list (not hardcoded!)
- Found 176 offices in the actual table vs. 156 in previous hardcoded attempt
- API success rate: 12.5% (22 successful calls out of 176)
- Total data collected: ~3.4MB
- API endpoint used: `https://www.dmvwaittimes.live/api/wait_times_daily_averages?slug={office_slug}`

## Lesson Learned

❌ **Don't hardcode office lists** - Always scrape the source data first!
✅ **Proper approach**: Parse HTML table → Extract real office slugs → Fetch API data

## Files Created

### Generated Files

#### 📁 `/data` Directory (Source of Truth)
- `dmv_offices_complete.json` - **MAIN DATA FILE** with all office info + coordinates
- `dmv_summary.json` - Scraping and geocoding statistics
- `dmv_insights.json` - Analysis insights and rankings
- `dmv_offices_analysis.csv` - Processed data for external analysis tools

#### 📁 `/dashboard` Directory (Visualizations)  
- `dmv_offices_map.html` - **Interactive map with markers**
- `dmv_heatmap.html` - **🌡️ Heat map (smooth coverage areas)**
- `dmv_heatmap_pro.html` - **🌡️ Professional heat map (high-res, precise boundaries)**
- `dmv_voronoi_map.html` - **🔷 Voronoi tessellation map (experimental)**

### Scripts
- `scrape_with_retry.py` - **Main script** - scraping + geocoding + mapping
- `dmv_heatmap_pro.py` - **🌡️ Professional heat map** - high-resolution precise boundaries **(BEST)**
- `dmv_heatmap.py` - **🌡️ Heat map** - smooth coverage areas visualization
- `dmv_voronoi_map.py` - **🔷 Voronoi tessellation map** - geometric coverage areas
- `analyze_from_source.py` - **Analysis example** - builds from source of truth
- `requirements.txt` - Python dependencies (includes folium, geopy, scipy, numpy, geopandas)

## Data Structure

The main data file (`data/dmv_offices_complete.json`) contains:
```json
[
  {
    "table_data": {
      "name": "Arleta",
      "slug": "arleta", 
      "address": "14400 Van Nuys Blvd, Arleta, CA 91331",
      "current_appt_wait": "23",
      "current_non_appt_wait": "79",
      "url": "https://www.dmvwaittimes.live/office/arleta",
      "latitude": 34.2479119,
      "longitude": -118.4452195,
      "geocoded": true
    },
    "api_data": {
      "slug": "arleta",
      "success": true,
      "data": { /* historical wait time data */ },
      "attempts_needed": 1
    }
  }
]
```

**Key Features:**
- ✅ **Complete office information** (name, address, current waits)
- ✅ **Geocoded coordinates** (latitude, longitude) 
- ✅ **Historical API data** (when available)
- ✅ **Single source of truth** for all analysis

## Key Features

### 📊 Data Collection
- **176 actual offices** scraped from live table
- **Improved success rates** with retry logic and proper delays
- **No hardcoded lists** - always gets current data

### 🌍 Geographic Mapping
- **Address geocoding** using free Nominatim service
- **Interactive map** with color-coded wait times
- **Clickable markers** showing office details and current waits

### 🎯 Smart Visualizations
- **Green markers** = No wait (0 min)
- **Orange/Red markers** = Longer waits (30+ min)
- **Popup details** with address, hours, wait times
- **Legend and tooltips** for easy navigation

### ⚡ Technical Improvements
- **Exponential backoff** for failed requests
- **Connection pooling** for better performance  
- **Progress tracking** with intermediate saves
- **Comprehensive error handling**

## Usage

### Running the Comprehensive Scraper & Mapper
```bash
pip install -r requirements.txt
python scrape_with_retry.py
```

This single script will:
1. 📋 Scrape the DMV office table  
2. 🔄 Fetch API data with retry logic
3. 🌍 Geocode addresses to coordinates
4. 🗺️ Create interactive map with wait times
5. 📊 Generate comprehensive statistics

### Creating Voronoi Coverage Map
```bash
python dmv_voronoi_map.py
```

Creates a beautiful **Voronoi tessellation map** showing:
- 🔷 Coverage areas for each DMV office
- 🌈 Color-coded regions by wait times (green=good, red=bad)
- 📍 Interactive markers with office details
- 💡 Helps you find the best DMV office in your area

### Running Additional Analysis
```bash
python analyze_from_source.py
```

This demonstrates how to:
- Load from the single source of truth (`data/dmv_offices_complete.json`)
- Convert to pandas DataFrame for analysis
- Generate insights and export to CSV
- Build all analysis from the same base data

## Data Details

- **Time Coverage**: Data includes average wait times broken down by:
  - Day of the week (Monday-Sunday)
  - Time of day (10-minute intervals)
  - Appointment vs. Non-appointment

- **Offices Covered**: All 156 California DMV offices listed on dmvwaittimes.live

- **Data Source**: [DMV Wait Times](https://www.dmvwaittimes.live) - Independent third-party service

## Notes

- Data represents historical averages, not real-time wait times
- DMV Wait Times is privately owned and not affiliated with the California DMV
- Wait times are generally shorter in the mornings and mid-week
- Some offices may have zero wait times due to being closed or having no historical data

## License

This data is collected from publicly available sources for analysis purposes. 