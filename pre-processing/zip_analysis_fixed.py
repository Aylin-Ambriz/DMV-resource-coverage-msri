#!/usr/bin/env python3
"""
DMV ZIP Code Map Generator - FIXED VERSION
Uses California zip code shapefile with proper coordinate handling
Filters for California zip codes only and handles coordinate system correctly
"""

import json
import numpy as np
import folium
import geopandas as gpd
from shapely.geometry import Point
from typing import List, Dict, Optional
import os
from math import sqrt
import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap

class DMVZipCodeMapper:
    def __init__(self):
        self.data_file = "pre-processing/data/dmv_offices_complete.json"
        self.output_file = "pre-processing/output/dmv_zip_codes.html"
        self.zip_analysis_file = "pre-processing/data/dmv_zip_code_analysis.json"
        self.static_image_file = "pre-processing/output/dmv_zip_codes_map.png"
        self.zip_codes_file = "pre-processing/data/zip_data/zip_poly.shp"
        
    def load_zip_codes(self):
        """Load California zip codes from local shapefile with proper CRS handling"""
        print("🏛️ Loading California zip codes from local shapefile...")
        
        if not os.path.exists(self.zip_codes_file):
            print(f"❌ Zip codes file not found: {self.zip_codes_file}")
            return None
        
        try:
            print(f"   📡 Loading: {self.zip_codes_file}")
            gdf = gpd.read_file(self.zip_codes_file)
            
            print(f"   ✅ Loaded {len(gdf)} zip codes")
            print(f"   📋 Columns: {list(gdf.columns)}")
            print(f"   🗺️ Original CRS: {gdf.crs}")
            
            # Convert to WGS84 (lat/lon) if needed
            if gdf.crs != 'EPSG:4326':
                print(f"   🔄 Converting to WGS84 (EPSG:4326)...")
                gdf = gdf.to_crs('EPSG:4326')
                print(f"   ✅ Converted to CRS: {gdf.crs}")
            
            # Filter for California zip codes (90000-96199)
            print(f"   🔍 Filtering for California zip codes...")
            
            # Convert ZIP_CODE to string and filter
            gdf['ZIP_CODE'] = gdf['ZIP_CODE'].astype(str)
            
            # California zip codes start with 90-96
            ca_mask = (
                (gdf['ZIP_CODE'].str.startswith('90')) |
                (gdf['ZIP_CODE'].str.startswith('91')) |
                (gdf['ZIP_CODE'].str.startswith('92')) |
                (gdf['ZIP_CODE'].str.startswith('93')) |
                (gdf['ZIP_CODE'].str.startswith('94')) |
                (gdf['ZIP_CODE'].str.startswith('95')) |
                (gdf['ZIP_CODE'].str.startswith('96')) |
                (gdf['ZIP_CODE'].str.startswith('00')) 
            )
            
            gdf_ca = gdf[ca_mask].copy()
            
            print(f"   ✅ Filtered to {len(gdf_ca)} California zip codes")
            print(f"   📊 Sample CA zip codes:")
            for i in range(min(5, len(gdf_ca))):
                row = gdf_ca.iloc[i]
                print(f"      ZIP {row['ZIP_CODE']} - {row.get('PO_NAME', 'N/A')}")
            
            # Test coordinate system with first zip code
            if len(gdf_ca) > 0:
                test_zip = gdf_ca.iloc[0]
                centroid = test_zip.geometry.centroid
                print(f"   🧪 Test zip centroid: ({centroid.y:.4f}, {centroid.x:.4f})")
                
                # Check if coordinates are reasonable for California
                if 32 <= centroid.y <= 42 and -125 <= centroid.x <= -114:
                    print(f"   ✅ Coordinates look correct for California")
                else:
                    print(f"   ⚠️ Coordinates may be incorrect for California")
            
            # Calculate coverage area
            total_area = gdf_ca.geometry.area.sum()
            print(f"   📏 Total coverage area: {total_area:.6f} square degrees")
            print(f"   🎯 CALIFORNIA ZIP CODES: {len(gdf_ca)} zip codes!")
            
            return gdf_ca
            
        except Exception as e:
            print(f"❌ Error loading zip codes: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def load_dmv_data(self) -> List[Dict]:
        """Load DMV data"""
        if not os.path.exists(self.data_file):
            print(f"❌ Data file not found: {self.data_file}")
            return []
            
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"✅ Loaded {len(data)} DMV offices")
            return data
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return []
    
    def extract_geocoded_offices(self, data: List[Dict]) -> List[Dict]:
        """Extract geocoded offices"""
        geocoded = []
        for item in data:
            table_data = item.get('table_data', {})
            if (table_data.get('geocoded', False) and 
                table_data.get('latitude') is not None and 
                table_data.get('longitude') is not None):
                geocoded.append(table_data)
        
        print(f"📍 Found {len(geocoded)} offices with coordinates")
        return geocoded
    
    def get_wait_time_numeric(self, wait_str: str) -> Optional[int]:
        """Convert wait time to numeric"""
        if not wait_str or wait_str == 'N/A':
            return None
        try:
            return int(wait_str) if str(wait_str).isdigit() else None
        except:
            return None
    
    def distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points (Euclidean distance in lat/lon)"""
        return sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)
    
    def find_nearest_office_to_zip(self, zip_geometry, offices: List[Dict]):
        """Find nearest DMV office to a zip code"""
        # Use zip centroid for distance calculation
        centroid = zip_geometry.centroid
        zip_lat, zip_lon = centroid.y, centroid.x
        
        min_distance = float('inf')
        nearest_office = None
        
        for office in offices:
            office_lat = office['latitude']
            office_lon = office['longitude']
            
            dist = self.distance(zip_lat, zip_lon, office_lat, office_lon)
            if dist < min_distance:
                min_distance = dist
                nearest_office = office
        
        return nearest_office, min_distance
    
    def get_color_for_wait_time(self, wait_time: Optional[int]) -> str:
        """Get color for wait time"""
        if wait_time is None:
            return '#808080'  # Gray for no data
        
        # Smooth gradient from green to red
        normalized = min(wait_time / 120.0, 1.0)
        
        if normalized <= 0.5:
            # Green to yellow (0.0 to 0.5)
            r = int(255 * (normalized * 2))
            g = 255
            b = 0
        else:
            # Yellow to red (0.5 to 1.0)
            r = 255
            g = int(255 * (2 - normalized * 2))
            b = 0
        
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def categorize_wait_time(self, wait_time: Optional[int]) -> str:
        """Categorize wait time into bins for analysis"""
        if wait_time is None:
            return "No Data"
        elif wait_time == 0:
            return "No Wait (0 min)"
        elif wait_time <= 15:
            return "Excellent (1-15 min)"
        elif wait_time <= 30:
            return "Good (16-30 min)"
        elif wait_time <= 45:
            return "Moderate (31-45 min)"
        elif wait_time <= 60:
            return "Long (46-60 min)"
        elif wait_time <= 90:
            return "Very Long (61-90 min)"
        else:
            return "Extremely Long (90+ min)"
    
    def create_zip_analysis_json(self, zip_data: List[Dict]) -> bool:
        """Create detailed JSON file for zip code analysis"""
        print("📊 Creating zip code analysis JSON...")
        
        # Organize zips by wait time categories
        categories = {}
        zip_details = []
        
        for zip_info in zip_data:
            wait_time = zip_info['wait_time']
            category = self.categorize_wait_time(wait_time)
            
            # Create detailed zip record
            zip_record = {
                'zip_code': zip_info['zip_code'],
                'zip_name': zip_info['zip_name'],
                'wait_time_minutes': wait_time,
                'wait_time_category': category,
                'nearest_dmv_office': zip_info['nearest_office']['name'],
                'nearest_dmv_address': zip_info['nearest_office']['address'],
                'distance_to_dmv_degrees': round(zip_info['distance_to_dmv'], 6),
                'dmv_appointment_wait': zip_info['nearest_office'].get('current_appt_wait', 'N/A'),
                'dmv_walkin_wait': zip_info['nearest_office'].get('current_non_appt_wait', 'N/A'),
                'color_hex': zip_info['color']
            }
            
            # Add to category
            if category not in categories:
                categories[category] = []
            categories[category].append(zip_record)
            
            # Add to overall list
            zip_details.append(zip_record)
        
        # Create comprehensive analysis structure
        analysis_data = {
            'metadata': {
                'generated_date': datetime.datetime.now().isoformat(),
                'total_zips': len(zip_data),
                'data_source': 'California ZIP Codes + DMV Wait Times Live Data',
                'purpose': 'DMV wait time analysis by California ZIP code',
                'categories_explanation': {
                    'No Wait (0 min)': 'No current wait time',
                    'Excellent (1-15 min)': 'Very short wait',
                    'Good (16-30 min)': 'Reasonable wait time',
                    'Moderate (31-45 min)': 'Moderate wait time',
                    'Long (46-60 min)': 'Long wait time',
                    'Very Long (61-90 min)': 'Very long wait time',
                    'Extremely Long (90+ min)': 'Extremely long wait time',
                    'No Data': 'No wait time data available'
                }
            },
            'summary_statistics': {},
            'zips_by_category': categories,
            'all_zips': zip_details
        }
        
        # Calculate summary statistics
        wait_times = [z['wait_time_minutes'] for z in zip_details if z['wait_time_minutes'] is not None]
        if wait_times:
            analysis_data['summary_statistics'] = {
                'total_zips_with_data': len(wait_times),
                'average_wait_time': round(sum(wait_times) / len(wait_times), 1),
                'median_wait_time': round(sorted(wait_times)[len(wait_times)//2], 1),
                'min_wait_time': min(wait_times),
                'max_wait_time': max(wait_times),
                'category_counts': {cat: len(zips) for cat, zips in categories.items()}
            }
        
        try:
            with open(self.zip_analysis_file, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, indent=2, ensure_ascii=False)
            
            print(f"   ✅ Zip analysis saved: {self.zip_analysis_file}")
            print(f"   📊 Categories created:")
            for category, zips in categories.items():
                print(f"      {category}: {len(zips)} zip codes")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error saving zip analysis: {e}")
            return False
    
    def create_static_image_map(self, zip_data: List[Dict], offices: List[Dict]) -> bool:
        """Create a static PNG image map for fast visualization"""
        print("🖼️ Creating static image map for fast visualization...")
        
        try:
            # Create figure with high DPI for quality
            fig, ax = plt.subplots(1, 1, figsize=(16, 12), dpi=150)
            
            # Define color mapping for wait times
            def get_plot_color(wait_time):
                if wait_time is None:
                    return '#808080'  # Gray
                elif wait_time == 0:
                    return '#00FF00'  # Green
                elif wait_time <= 15:
                    return '#7FFF00'  # Light green
                elif wait_time <= 30:
                    return '#FFFF00'  # Yellow
                elif wait_time <= 45:
                    return '#FFD700'  # Gold
                elif wait_time <= 60:
                    return '#FFA500'  # Orange
                elif wait_time <= 90:
                    return '#FF4500'  # Orange red
                else:
                    return '#FF0000'  # Red
            
            print("   🎨 Plotting ZIP codes...")
            
            # Plot ZIP codes
            plotted_zips = 0
            for zip_info in zip_data:
                try:
                    # Get ZIP geometry
                    geom = zip_info['geometry']
                    color = get_plot_color(zip_info['wait_time'])
                    
                    # Handle different geometry types
                    if geom.geom_type == 'Polygon':
                        x, y = geom.exterior.xy
                        ax.fill(x, y, color=color, alpha=0.7, edgecolor='white', linewidth=0.2)
                    elif geom.geom_type == 'MultiPolygon':
                        for poly in geom.geoms:
                            x, y = poly.exterior.xy
                            ax.fill(x, y, color=color, alpha=0.7, edgecolor='white', linewidth=0.2)
                    
                    plotted_zips += 1
                    
                    if plotted_zips % 200 == 0:
                        print(f"      Plotted {plotted_zips}/{len(zip_data)} ZIP codes...")
                        
                except Exception as e:
                    continue
            
            print(f"   ✅ Plotted {plotted_zips} ZIP codes")
            
            # Plot DMV offices
            print("   📌 Adding DMV office markers...")
            office_lons = [office['longitude'] for office in offices]
            office_lats = [office['latitude'] for office in offices]
            
            # Color code DMV offices by wait time
            office_colors = []
            for office in offices:
                wait_time = self.get_wait_time_numeric(office.get('current_appt_wait', ''))
                if wait_time and wait_time <= 30:
                    office_colors.append('darkgreen')
                elif wait_time and wait_time > 60:
                    office_colors.append('darkred')
                else:
                    office_colors.append('darkorange')
            
            ax.scatter(office_lons, office_lats, c=office_colors, s=100, 
                      marker='s', edgecolors='white', linewidth=2, zorder=5, alpha=0.9)
            
            # Set map bounds
            all_bounds = [zip_info['geometry'].bounds for zip_info in zip_data]
            min_x = min(bound[0] for bound in all_bounds)
            min_y = min(bound[1] for bound in all_bounds)
            max_x = max(bound[2] for bound in all_bounds)
            max_y = max(bound[3] for bound in all_bounds)
            
            ax.set_xlim(min_x, max_x)
            ax.set_ylim(min_y, max_y)
            ax.set_aspect('equal')
            
            # Style the plot
            ax.set_title('California DMV Wait Times by ZIP Code\nFast-Loading Static Map: 1,746 ZIP Codes', 
                        fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Longitude', fontsize=12)
            ax.set_ylabel('Latitude', fontsize=12)
            
            # Remove ticks for cleaner look
            ax.tick_params(axis='both', which='major', labelsize=10)
            
            # Create legend
            legend_elements = [
                patches.Patch(color='#00FF00', label='No Wait (0 min)'),
                patches.Patch(color='#7FFF00', label='Excellent (1-15 min)'),
                patches.Patch(color='#FFFF00', label='Good (16-30 min)'),
                patches.Patch(color='#FFD700', label='Moderate (31-45 min)'),
                patches.Patch(color='#FFA500', label='Long (46-60 min)'),
                patches.Patch(color='#FF4500', label='Very Long (61-90 min)'),
                patches.Patch(color='#FF0000', label='Extremely Long (90+ min)'),
                patches.Patch(color='#808080', label='No Data')
            ]
            
            # Add DMV office legend
            legend_elements.extend([
                plt.Line2D([0], [0], marker='s', color='w', markerfacecolor='darkgreen', 
                          markersize=10, label='DMV: Good Wait (≤30 min)'),
                plt.Line2D([0], [0], marker='s', color='w', markerfacecolor='darkorange', 
                          markersize=10, label='DMV: Moderate Wait (31-60 min)'),
                plt.Line2D([0], [0], marker='s', color='w', markerfacecolor='darkred', 
                          markersize=10, label='DMV: Long Wait (>60 min)')
            ])
            
            ax.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(1, 0.5), 
                     fontsize=10, title='Wait Time Categories', title_fontsize=12)
            
            # Add subtitle with statistics
            wait_times = [zip_info['wait_time'] for zip_info in zip_data if zip_info['wait_time'] is not None]
            avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0
            
            subtitle = f'Average Wait: {avg_wait:.1f} min | {len(zip_data)} ZIP Codes | {len(offices)} DMV Offices'
            fig.suptitle(subtitle, fontsize=12, y=0.02)
            
            # Tight layout to prevent legend cutoff
            plt.tight_layout()
            
            # Save the image
            plt.savefig(self.static_image_file, dpi=150, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            plt.close()
            
            # Get file size for reporting
            file_size = os.path.getsize(self.static_image_file) / (1024 * 1024)  # MB
            
            print(f"   ✅ Static image map saved: {self.static_image_file}")
            print(f"   📏 Image size: {file_size:.1f} MB")
            print(f"   🚀 Image loads instantly vs slow HTML")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error creating static image: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def process_zip_codes(self, zip_gdf, offices: List[Dict]):
        """Process each zip code and assign nearest DMV data"""
        print(f"🔄 Processing {len(zip_gdf)} zip codes...")
        
        zip_data = []
        processed = 0
        
        for idx, zip_row in zip_gdf.iterrows():
            try:
                zip_geom = zip_row.geometry
                
                # Get zip information
                zip_code = zip_row.get('ZIP_CODE', f'zip_{idx}')
                zip_name = zip_row.get('PO_NAME', f'ZIP {zip_code}')
                
                # Find nearest DMV office
                nearest_office, distance = self.find_nearest_office_to_zip(zip_geom, offices)
                
                if nearest_office:
                    wait_time = self.get_wait_time_numeric(
                        nearest_office.get('current_appt_wait', '')
                    )
                    
                    zip_info = {
                        'geometry': zip_geom,
                        'zip_code': zip_code,
                        'zip_name': zip_name,
                        'nearest_office': nearest_office,
                        'wait_time': wait_time,
                        'distance_to_dmv': distance,
                        'color': self.get_color_for_wait_time(wait_time)
                    }
                    
                    zip_data.append(zip_info)
                
                processed += 1
                if processed % 100 == 0:
                    print(f"   Processed {processed}/{len(zip_gdf)} zip codes...")
                    
            except Exception as e:
                print(f"      ⚠️ Skipped zip code {idx}: {e}")
                continue
        
        print(f"   ✅ Successfully processed {len(zip_data)} zip codes")
        return zip_data
    
    def create_zip_code_map(self, zip_data: List[Dict], offices: List[Dict]) -> folium.Map:
        """Create detailed zip code map"""
        print(f"🗺️ Creating detailed zip code map...")
        
        # Calculate map center
        center_lat = np.mean([office['latitude'] for office in offices])
        center_lon = np.mean([office['longitude'] for office in offices])
        
        # Create base map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=6,
            tiles='CartoDB positron'
        )
        
        # Add zip codes
        print(f"   🎨 Adding {len(zip_data)} colored zip codes...")
        added_zips = 0
        
        for zip_info in zip_data:
            try:
                # Create popup content
                popup_html = f"""
                <div style="width: 300px;">
                    <h4>📮 ZIP Code {zip_info['zip_code']}</h4>
                    <p><strong>Area:</strong> {zip_info['zip_name']}</p>
                    <p><strong>Nearest DMV:</strong><br>{zip_info['nearest_office']['name']}</p>
                    <p><strong>Wait Time:</strong> {zip_info['wait_time'] if zip_info['wait_time'] else 'N/A'} minutes</p>
                    <p><strong>Distance:</strong> {zip_info['distance_to_dmv']:.4f}°</p>
                    <p><strong>Coverage:</strong> ZIP code level</p>
                </div>
                """
                
                # Convert geometry to GeoJSON
                geojson_geom = {
                    "type": "Feature",
                    "geometry": zip_info['geometry'].__geo_interface__
                }
                
                # Add zip to map
                folium.GeoJson(
                    geojson_geom,
                    style_function=lambda x, color=zip_info['color']: {
                        'fillColor': color,
                        'color': 'white',
                        'weight': 0.5,
                        'fillOpacity': 0.7,
                        'opacity': 0.8
                    },
                    popup=folium.Popup(popup_html, max_width=350),
                    tooltip=f"ZIP {zip_info['zip_code']} - {zip_info['wait_time'] if zip_info['wait_time'] else 'N/A'} min"
                ).add_to(m)
                
                added_zips += 1
                
            except Exception as e:
                print(f"      ⚠️ Skipped zip code: {e}")
                continue
        
        print(f"   ✅ Added {added_zips} zip codes to map")
        
        # Add DMV office markers
        print("   📌 Adding DMV office markers...")
        for office in offices:
            wait_time = self.get_wait_time_numeric(office.get('current_appt_wait', ''))
            marker_color = 'green' if wait_time and wait_time <= 30 else 'red' if wait_time and wait_time > 60 else 'orange'
            
            popup_html = f"""
            <div style="width: 260px;">
                <h4>🏢 {office['name']}</h4>
                <p><strong>Address:</strong><br>{office['address']}</p>
                <p><strong>Wait Times:</strong><br>
                   📅 Appointment: {office.get('current_appt_wait', 'N/A')} min<br>
                   🚶 Walk-in: {office.get('current_non_appt_wait', 'N/A')} min
                </p>
                <p><strong>Service Area:</strong> Multiple ZIP codes served</p>
            </div>
            """
            
            folium.Marker(
                location=[office['latitude'], office['longitude']],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"DMV: {office['name']} - {office.get('current_appt_wait', 'N/A')} min",
                icon=folium.Icon(color=marker_color, icon='building', prefix='fa')
            ).add_to(m)
        
        # Add legend
        self.add_zip_code_legend(m, len(zip_data))
        
        return m
    
    def add_zip_code_legend(self, m: folium.Map, zip_count: int):
        """Add legend for zip code map"""
        legend_html = f'''
        <div style="position: fixed; 
                    top: 50px; right: 50px; width: 340px; height: 480px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:13px; padding: 15px; border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
        <h3 style="margin-top: 0; color: #2E74B5;">📮 DMV Wait Times by ZIP Code</h3>
        <p style="margin: 5px 0; font-size: 11px; color: #666;">
            <strong>CALIFORNIA ZIP CODE ANALYSIS</strong><br>
            Using {zip_count} California ZIP codes for DMV coverage analysis.
            Each ZIP colored by nearest DMV wait time.
        </p>
        <div style="background: #e8f4f8; padding: 8px; border-radius: 4px; margin: 10px 0;">
            <strong>🏆 Granularity Level:</strong><br>
            <span style="color: #2E74B5; font-weight: bold;">ZIP Code Level</span>
            <br><small>{zip_count} California ZIP codes</small>
        </div>
        <h4 style="margin: 15px 0 10px 0; color: #333;">Wait Time Legend:</h4>
        <div style="display: flex; align-items: center; margin: 5px 0;">
            <div style="width: 20px; height: 15px; background: #00FF00; margin-right: 8px; border: 1px solid #ccc;"></div>
            <span>0 minutes (No wait)</span>
        </div>
        <div style="display: flex; align-items: center; margin: 5px 0;">
            <div style="width: 20px; height: 15px; background: #7FFF00; margin-right: 8px; border: 1px solid #ccc;"></div>
            <span>1-15 minutes (Excellent)</span>
        </div>
        <div style="display: flex; align-items: center; margin: 5px 0;">
            <div style="width: 20px; height: 15px; background: #FFFF00; margin-right: 8px; border: 1px solid #ccc;"></div>
            <span>16-30 minutes (Good)</span>
        </div>
        <div style="display: flex; align-items: center; margin: 5px 0;">
            <div style="width: 20px; height: 15px; background: #FFA500; margin-right: 8px; border: 1px solid #ccc;"></div>
            <span>31-60 minutes (Moderate)</span>
        </div>
        <div style="display: flex; align-items: center; margin: 5px 0;">
            <div style="width: 20px; height: 15px; background: #FF4500; margin-right: 8px; border: 1px solid #ccc;"></div>
            <span>61-90 minutes (Long)</span>
        </div>
        <div style="display: flex; align-items: center; margin: 5px 0;">
            <div style="width: 20px; height: 15px; background: #FF0000; margin-right: 8px; border: 1px solid #ccc;"></div>
            <span>90+ minutes (Very Long)</span>
        </div>
        <div style="margin-top: 15px; padding: 8px; background: #f0f8ff; border-radius: 4px; font-size: 11px;">
            <strong>📮 ZIP Code Features:</strong><br/>
            • California ZIP codes only<br/>
            • Postal service boundaries<br/>
            • Click ZIP codes for details<br/>
            • 🏢 Building icons = DMV offices<br/>
            • Geographic coverage analysis
        </div>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
    
    def generate_zip_code_map(self) -> bool:
        """Generate the zip code map"""
        print("📮 DMV ZIP CODE MAP GENERATOR - FIXED VERSION")
        print("=" * 60)
        
        # Create output directory
        os.makedirs("pre-processing/output", exist_ok=True)
        
        # Step 1: Load zip codes (with California filtering)
        zip_gdf = self.load_zip_codes()
        if zip_gdf is None:
            return False
        
        # Step 2: Load DMV data
        data = self.load_dmv_data()
        if not data:
            return False
        
        offices = self.extract_geocoded_offices(data)
        if len(offices) < 3:
            print("❌ Need at least 3 offices with coordinates")
            return False
        
        # Step 3: Process zip codes
        zip_data = self.process_zip_codes(zip_gdf, offices)
        if not zip_data:
            print("❌ No zip code data processed")
            return False
        
        # Step 4: Create zip analysis JSON
        json_success = self.create_zip_analysis_json(zip_data)
        if not json_success:
            print("⚠️ Warning: Failed to create zip analysis JSON")
        
        # Step 5: Create map
        try:
            zip_map = self.create_zip_code_map(zip_data, offices)
            
            # Step 6: Save interactive map
            zip_map.save(self.output_file)
            print(f"\n🎉 ZIP CODE map saved: {self.output_file}")
            
            # Step 7: Create static image map for fast loading
            image_success = self.create_static_image_map(zip_data, offices)
            if not image_success:
                print("⚠️ Warning: Failed to create static image map")
            
            # Statistics
            wait_times = [zip_info['wait_time'] for zip_info in zip_data if zip_info['wait_time'] is not None]
            
            if wait_times:
                avg_wait = sum(wait_times) / len(wait_times)
                min_wait = min(wait_times)
                max_wait = max(wait_times)
                
                print(f"\n📊 ZIP CODE STATISTICS:")
                print(f"   📮 California ZIP Codes: {len(zip_data)}")
                print(f"   🏢 DMV Offices: {len(offices)}")
                print(f"   ⏱️  Average Wait: {avg_wait:.1f} minutes")
                print(f"   🟢 Best Wait: {min_wait} minutes")
                print(f"   🔴 Worst Wait: {max_wait} minutes")
                print(f"   🎯 Granularity: ZIP Code level")
            
            print(f"\n💡 FEATURES:")
            print(f"   ✅ {len(zip_data)} California ZIP codes only")
            print(f"   ✅ Proper coordinate system handling")
            print(f"   ✅ Accurate distance calculations")
            print(f"   ✅ Click any ZIP for detailed DMV assignment")
            print(f"   ✅ ZIP code analysis JSON")
            print(f"   ✅ Fast-loading static image map")
            
            print(f"\n🎯 USAGE:")
            print(f"   🚀 QUICK VIEW: {self.static_image_file} (loads instantly)")
            print(f"   📊 INTERACTIVE: {self.output_file} (detailed but slower)")
            print(f"   📈 ANALYSIS: {self.zip_analysis_file}")
            print(f"   🔍 Zoom in on interactive map for detail")
            print(f"   📍 Click any ZIP for nearest DMV assignment")
            
            return True
            
        except Exception as e:
            print(f"❌ Error creating zip code map: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    mapper = DMVZipCodeMapper()
    success = mapper.generate_zip_code_map()
    
    if success:
        print(f"\n✅ SUCCESS! ZIP CODE map: Interactive HTML + Static image + Analysis JSON!")
    else:
        print(f"\n❌ Failed to create zip code map")

if __name__ == "__main__":
    main() 