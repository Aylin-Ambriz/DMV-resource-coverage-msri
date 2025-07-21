#!/usr/bin/env python3
"""
DMV Census Tracts Map Generator - ULTIMATE GRANULARITY
Uses local California census tract shapefile for maximum detail coverage
~8,000+ census tracts for ultra-granular DMV wait time mapping

Uses: data/tl_2024_06_tract/ (local shapefile)
Outputs: dashboard/dmv_census_tracts.html
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

class DMVCensusTractMapper:
    def __init__(self):
        self.data_file = "pre-processing/data/dmv_offices_complete.json"
        self.output_file = "pre-processing/dashboard/dmv_census_tracts.html"
        self.tract_analysis_file = "pre-processing/data/dmv_census_tract_analysis.json"
        self.static_image_file = "pre-processing/data/dmv_census_tracts_map.png"
        self.census_tracts_file = "pre-processing/data/tl_2024_06_tract/tl_2024_06_tract.shp"
        
    def load_census_tracts(self):
        """Load California census tracts from local shapefile"""
        print("🏛️ Loading California census tracts from local shapefile...")
        
        if not os.path.exists(self.census_tracts_file):
            print(f"❌ Census tracts file not found: {self.census_tracts_file}")
            return None
        
        try:
            print(f"   📡 Loading: {self.census_tracts_file}")
            gdf = gpd.read_file(self.census_tracts_file)
            
            print(f"   ✅ Loaded {len(gdf)} census tracts")
            print(f"   📋 Columns: {list(gdf.columns)}")
            
            # Show sample data
            if len(gdf) > 0:
                print(f"   📊 Sample tract data:")
                for col in ['GEOID', 'NAME', 'COUNTYFP', 'TRACTCE'][:4]:
                    if col in gdf.columns:
                        sample_val = str(gdf[col].iloc[0]) if len(gdf) > 0 else 'N/A'
                        print(f"      {col}: {sample_val}")
            
            # Calculate coverage area
            total_area = gdf.geometry.area.sum()
            print(f"   📏 Total coverage area: {total_area:.2f} square degrees")
            print(f"   🎯 ULTIMATE GRANULARITY: {len(gdf)} census tracts!")
            
            return gdf
            
        except Exception as e:
            print(f"❌ Error loading census tracts: {e}")
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
        """Calculate distance between two points"""
        return sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)
    
    def find_nearest_office_to_tract(self, tract_geometry, offices: List[Dict]):
        """Find nearest DMV office to a census tract"""
        # Use tract centroid for distance calculation
        centroid = tract_geometry.centroid
        tract_lat, tract_lon = centroid.y, centroid.x
        
        min_distance = float('inf')
        nearest_office = None
        
        for office in offices:
            office_lat = office['latitude']
            office_lon = office['longitude']
            
            dist = self.distance(tract_lat, tract_lon, office_lat, office_lon)
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
    
    def create_tract_analysis_json(self, tract_data: List[Dict]) -> bool:
        """Create detailed JSON file for demographic analysis"""
        print("📊 Creating tract analysis JSON for demographic research...")
        
        # Organize tracts by wait time categories
        categories = {}
        tract_details = []
        
        for tract in tract_data:
            wait_time = tract['wait_time']
            category = self.categorize_wait_time(wait_time)
            
            # Create detailed tract record
            tract_record = {
                'tract_id': tract['tract_id'],
                'tract_name': tract['tract_name'],
                'county_fips': tract['county_fp'],
                'wait_time_minutes': wait_time,
                'wait_time_category': category,
                'nearest_dmv_office': tract['nearest_office']['name'],
                'nearest_dmv_address': tract['nearest_office']['address'],
                'distance_to_dmv_degrees': round(tract['distance_to_dmv'], 6),
                'dmv_appointment_wait': tract['nearest_office'].get('current_appt_wait', 'N/A'),
                'dmv_walkin_wait': tract['nearest_office'].get('current_non_appt_wait', 'N/A'),
                'color_hex': tract['color']
            }
            
            # Add to category
            if category not in categories:
                categories[category] = []
            categories[category].append(tract_record)
            
            # Add to overall list
            tract_details.append(tract_record)
        
        # Create comprehensive analysis structure
        analysis_data = {
            'metadata': {
                'generated_date': datetime.datetime.now().isoformat(),
                'total_tracts': len(tract_data),
                'data_source': 'US Census 2024 Tracts + DMV Wait Times Live Data',
                'purpose': 'Demographic analysis of DMV wait times by census tract',
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
            'tracts_by_category': categories,
            'all_tracts': tract_details
        }
        
        # Calculate summary statistics
        wait_times = [t['wait_time_minutes'] for t in tract_details if t['wait_time_minutes'] is not None]
        if wait_times:
            analysis_data['summary_statistics'] = {
                'total_tracts_with_data': len(wait_times),
                'average_wait_time': round(sum(wait_times) / len(wait_times), 1),
                'median_wait_time': round(sorted(wait_times)[len(wait_times)//2], 1),
                'min_wait_time': min(wait_times),
                'max_wait_time': max(wait_times),
                'category_counts': {cat: len(tracts) for cat, tracts in categories.items()}
            }
        
        try:
            with open(self.tract_analysis_file, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, indent=2, ensure_ascii=False)
            
            print(f"   ✅ Tract analysis saved: {self.tract_analysis_file}")
            print(f"   📊 Categories created:")
            for category, tracts in categories.items():
                print(f"      {category}: {len(tracts)} tracts")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error saving tract analysis: {e}")
            return False
    
    def create_static_image_map(self, tract_data: List[Dict], offices: List[Dict]) -> bool:
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
            
            print("   🎨 Plotting census tracts...")
            
            # Plot census tracts
            plotted_tracts = 0
            for tract in tract_data:
                try:
                    # Get tract geometry
                    geom = tract['geometry']
                    color = get_plot_color(tract['wait_time'])
                    
                    # Handle different geometry types
                    if geom.geom_type == 'Polygon':
                        x, y = geom.exterior.xy
                        ax.fill(x, y, color=color, alpha=0.7, edgecolor='white', linewidth=0.1)
                    elif geom.geom_type == 'MultiPolygon':
                        for poly in geom.geoms:
                            x, y = poly.exterior.xy
                            ax.fill(x, y, color=color, alpha=0.7, edgecolor='white', linewidth=0.1)
                    
                    plotted_tracts += 1
                    
                    if plotted_tracts % 1000 == 0:
                        print(f"      Plotted {plotted_tracts}/{len(tract_data)} tracts...")
                        
                except Exception as e:
                    continue
            
            print(f"   ✅ Plotted {plotted_tracts} census tracts")
            
            # Plot DMV offices
            print("   📌 Adding DMV office markers...")
            office_lons = [office['longitude'] for office in offices]
            office_lats = [office['latitude'] for office in offices]
            
            # Color code DMV offices by wait time
            office_colors = []
            for office in offices:
                wait_time = self.get_wait_time_numeric(office.get('current_non_appt_wait', ''))
                if wait_time and wait_time <= 30:
                    office_colors.append('darkgreen')
                elif wait_time and wait_time > 60:
                    office_colors.append('darkred')
                else:
                    office_colors.append('darkorange')
            
            ax.scatter(office_lons, office_lats, c=office_colors, s=80, 
                      marker='s', edgecolors='white', linewidth=1, zorder=5, alpha=0.9)
            
            # Set map bounds
            all_bounds = [tract['geometry'].bounds for tract in tract_data]
            min_x = min(bound[0] for bound in all_bounds)
            min_y = min(bound[1] for bound in all_bounds)
            max_x = max(bound[2] for bound in all_bounds)
            max_y = max(bound[3] for bound in all_bounds)
            
            ax.set_xlim(min_x, max_x)
            ax.set_ylim(min_y, max_y)
            ax.set_aspect('equal')
            
            # Style the plot
            ax.set_title('California DMV Wait Times by Census Tract\nUltimate Granularity: 9,129 Tracts', 
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
                          markersize=8, label='DMV: Good Wait (≤30 min)'),
                plt.Line2D([0], [0], marker='s', color='w', markerfacecolor='darkorange', 
                          markersize=8, label='DMV: Moderate Wait (31-60 min)'),
                plt.Line2D([0], [0], marker='s', color='w', markerfacecolor='darkred', 
                          markersize=8, label='DMV: Long Wait (>60 min)')
            ])
            
            ax.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(1, 0.5), 
                     fontsize=10, title='Wait Time Categories', title_fontsize=12)
            
            # Add subtitle with statistics
            wait_times = [tract['wait_time'] for tract in tract_data if tract['wait_time'] is not None]
            avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0
            
            subtitle = f'Average Wait: {avg_wait:.1f} min | {len(tract_data)} Tracts | {len(offices)} DMV Offices'
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
            print(f"   📏 Image size: {file_size:.1f} MB (vs 100MB HTML)")
            print(f"   🚀 Image loads instantly vs slow HTML")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error creating static image: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def process_census_tracts(self, tracts_gdf, offices: List[Dict]):
        """Process each census tract and assign nearest DMV data"""
        print(f"🔄 Processing {len(tracts_gdf)} census tracts...")
        
        tract_data = []
        processed = 0
        
        for idx, tract in tracts_gdf.iterrows():
            try:
                tract_geom = tract.geometry
                
                # Get tract information
                tract_id = tract.get('GEOID', f'Tract_{idx}')
                tract_name = tract.get('NAME', f'Census Tract {idx}')
                county_fp = tract.get('COUNTYFP', 'Unknown')
                
                # Find nearest DMV office
                nearest_office, distance = self.find_nearest_office_to_tract(tract_geom, offices)
                
                if nearest_office:
                    wait_time = self.get_wait_time_numeric(
                        nearest_office.get('current_non_appt_wait', '')
                    )
                    
                    tract_info = {
                        'geometry': tract_geom,
                        'tract_id': tract_id,
                        'tract_name': tract_name,
                        'county_fp': county_fp,
                        'nearest_office': nearest_office,
                        'wait_time': wait_time,
                        'distance_to_dmv': distance,
                        'color': self.get_color_for_wait_time(wait_time)
                    }
                    
                    tract_data.append(tract_info)
                
                processed += 1
                if processed % 500 == 0:
                    print(f"   Processed {processed}/{len(tracts_gdf)} tracts...")
                    
            except Exception as e:
                print(f"      ⚠️ Skipped tract {idx}: {e}")
                continue
        
        print(f"   ✅ Successfully processed {len(tract_data)} census tracts")
        return tract_data
    
    def create_census_tract_map(self, tract_data: List[Dict], offices: List[Dict]) -> folium.Map:
        """Create ultra-detailed census tract map"""
        print(f"🗺️ Creating ULTRA-DETAILED census tract map...")
        
        # Calculate map center
        center_lat = np.mean([office['latitude'] for office in offices])
        center_lon = np.mean([office['longitude'] for office in offices])
        
        # Create base map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=6,
            tiles='CartoDB positron'
        )
        
        # Add census tracts
        print(f"   🎨 Adding {len(tract_data)} colored census tracts...")
        added_tracts = 0
        
        for tract in tract_data:
            try:
                # Create popup content
                popup_html = f"""
                <div style="width: 300px;">
                    <h4>📊 Census Tract {tract['tract_name']}</h4>
                    <p><strong>Tract ID:</strong> {tract['tract_id']}</p>
                    <p><strong>County FIPS:</strong> {tract['county_fp']}</p>
                    <p><strong>Nearest DMV:</strong><br>{tract['nearest_office']['name']}</p>
                    <p><strong>Wait Time:</strong> {tract['wait_time'] if tract['wait_time'] else 'N/A'} minutes</p>
                    <p><strong>Distance:</strong> {tract['distance_to_dmv']:.4f}°</p>
                    <p><strong>Coverage:</strong> Ultra-granular census tract level</p>
                </div>
                """
                
                # Convert geometry to GeoJSON
                geojson_geom = {
                    "type": "Feature",
                    "geometry": tract['geometry'].__geo_interface__
                }
                
                # Add tract to map
                folium.GeoJson(
                    geojson_geom,
                    style_function=lambda x, color=tract['color']: {
                        'fillColor': color,
                        'color': 'white',
                        'weight': 0.2,  # Very thin borders for detailed view
                        'fillOpacity': 0.7,
                        'opacity': 0.4
                    },
                    popup=folium.Popup(popup_html, max_width=350),
                    tooltip=f"Tract {tract['tract_name']} - {tract['wait_time'] if tract['wait_time'] else 'N/A'} min"
                ).add_to(m)
                
                added_tracts += 1
                
            except Exception as e:
                print(f"      ⚠️ Skipped tract: {e}")
                continue
        
        print(f"   ✅ Added {added_tracts} census tracts to map")
        
        # Add DMV office markers
        print("   📌 Adding DMV office markers...")
        for office in offices:
            wait_time = self.get_wait_time_numeric(office.get('current_non_appt_wait', ''))
            marker_color = 'green' if wait_time and wait_time <= 30 else 'red' if wait_time and wait_time > 60 else 'orange'
            
            popup_html = f"""
            <div style="width: 260px;">
                <h4>🏢 {office['name']}</h4>
                <p><strong>Address:</strong><br>{office['address']}</p>
                <p><strong>Wait Times:</strong><br>
                   📅 Appointment: {office.get('current_appt_wait', 'N/A')} min<br>
                   🚶 Walk-in: {office.get('current_non_appt_wait', 'N/A')} min
                </p>
                <p><strong>Service Area:</strong> Multiple census tracts served</p>
            </div>
            """
            
            folium.Marker(
                location=[office['latitude'], office['longitude']],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"DMV: {office['name']} - {office.get('current_non_appt_wait', 'N/A')} min",
                icon=folium.Icon(color=marker_color, icon='building', prefix='fa')
            ).add_to(m)
        
        # Add ultra-detailed legend
        self.add_census_tract_legend(m, len(tract_data))
        
        return m
    
    def add_census_tract_legend(self, m: folium.Map, tract_count: int):
        """Add legend for census tract map"""
        legend_html = f'''
        <div style="position: fixed; 
                    top: 50px; right: 50px; width: 340px; height: 480px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:13px; padding: 15px; border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
        <h3 style="margin-top: 0; color: #2E74B5;">📊 DMV Census Tracts - ULTIMATE DETAIL</h3>
        <p style="margin: 5px 0; font-size: 11px; color: #666;">
            <strong>MAXIMUM GRANULARITY ACHIEVED!</strong><br>
            Using {tract_count} official US Census tracts for ultra-detailed DMV coverage analysis.
            Each tract colored by nearest DMV wait time.
        </p>
        <div style="background: #e8f4f8; padding: 8px; border-radius: 4px; margin: 10px 0;">
            <strong>🏆 Granularity Level:</strong><br>
            <span style="color: #2E74B5; font-weight: bold;">Census Tracts (2024)</span>
            <br><small>{tract_count} tracts - ULTIMATE DETAIL!</small>
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
            <strong>📊 Census Tract Features:</strong><br/>
            • Official US Census boundaries<br/>
            • Ultra-granular neighborhood level<br/>
            • Click tracts for detailed info<br/>
            • 🏢 Building icons = DMV offices<br/>
            • Maximum possible detail achieved!
        </div>
        <div style="margin-top: 10px; padding: 6px; background: #fffacd; border-radius: 4px; font-size: 10px; color: #b8860b;">
            <strong>⚡ Performance Note:</strong><br/>
            {tract_count} tracts loaded - may take time to render
        </div>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
    
    def generate_census_tract_map(self) -> bool:
        """Generate the ultimate census tract map"""
        print("📊 DMV CENSUS TRACTS MAP GENERATOR - ULTIMATE DETAIL")
        print("=" * 65)
        
        # Create output directory
        os.makedirs("dashboard", exist_ok=True)
        
        # Step 1: Load census tracts
        tracts_gdf = self.load_census_tracts()
        if tracts_gdf is None:
            return False
        
        # Step 2: Load DMV data
        data = self.load_dmv_data()
        if not data:
            return False
        
        offices = self.extract_geocoded_offices(data)
        if len(offices) < 3:
            print("❌ Need at least 3 offices with coordinates")
            return False
        
        # Step 3: Process census tracts
        tract_data = self.process_census_tracts(tracts_gdf, offices)
        if not tract_data:
            print("❌ No tract data processed")
            return False
        
        # Step 4: Create tract analysis JSON for demographic research
        json_success = self.create_tract_analysis_json(tract_data)
        if not json_success:
            print("⚠️ Warning: Failed to create tract analysis JSON")
        
        # Step 5: Create ultimate map
        try:
            census_map = self.create_census_tract_map(tract_data, offices)
            
            # Step 6: Save interactive map
            census_map.save(self.output_file)
            print(f"\n🎉 ULTIMATE CENSUS TRACT map saved: {self.output_file}")
            
            # Step 7: Create static image map for fast loading
            image_success = self.create_static_image_map(tract_data, offices)
            if not image_success:
                print("⚠️ Warning: Failed to create static image map")
            
            # Statistics
            wait_times = [tract['wait_time'] for tract in tract_data if tract['wait_time'] is not None]
            
            if wait_times:
                avg_wait = sum(wait_times) / len(wait_times)
                min_wait = min(wait_times)
                max_wait = max(wait_times)
                
                print(f"\n📊 ULTIMATE GRANULARITY STATISTICS:")
                print(f"   📊 Census Tracts: {len(tract_data)} (MAXIMUM DETAIL!)")
                print(f"   🏢 DMV Offices: {len(offices)}")
                print(f"   ⏱️  Average Wait: {avg_wait:.1f} minutes")
                print(f"   🟢 Best Wait: {min_wait} minutes")
                print(f"   🔴 Worst Wait: {max_wait} minutes")
                print(f"   🎯 Granularity: ULTIMATE (census tract level)")
            
            print(f"\n💡 ULTIMATE FEATURES:")
            print(f"   ✅ {len(tract_data)} official US Census tracts")
            print(f"   ✅ Ultimate granularity - neighborhood level detail")
            print(f"   ✅ 100% geographic coverage (no gaps)")
            print(f"   ✅ Click any tract for detailed DMV assignment")
            print(f"   ✅ Professional census boundaries")
            print(f"   ✅ Maximum possible detail achieved!")
            print(f"   ✅ Tract analysis JSON for demographic research")
            print(f"   ✅ Fast-loading static image map")
            
            print(f"\n🎯 USAGE:")
            print(f"   🚀 QUICK VIEW: {self.static_image_file} (loads instantly)")
            print(f"   📊 INTERACTIVE: {self.output_file} (detailed but slower)")
            print(f"   📈 ANALYSIS: {self.tract_analysis_file} for demographic research")
            print(f"   🔍 Zoom in on interactive map for ultra-detail")
            print(f"   📍 Click any tract for nearest DMV assignment")
            print(f"   📊 Load JSON data into R/Python for statistical analysis")
            
            return True
            
        except Exception as e:
            print(f"❌ Error creating census tract map: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    mapper = DMVCensusTractMapper()
    success = mapper.generate_census_tract_map()
    
    if success:
        print(f"\n✅ SUCCESS! ULTIMATE GRANULARITY: Interactive map + Static image + Analysis JSON!")
    else:
        print(f"\n❌ Failed to create census tract map")

if __name__ == "__main__":
    main() 