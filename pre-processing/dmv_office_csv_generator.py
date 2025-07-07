#!/usr/bin/env python3
"""
DMV Office CSV Generator
Creates a CSV file with all DMV offices and their details:
- Office name
- Address
- Latitude/Longitude
- ZIP code the office is located in
- Wait times (both appointment and walk-in)
"""

import json
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from typing import List, Dict, Optional
import os
import datetime

class DMVOfficeCSVGenerator:
    def __init__(self):
        self.data_file = "pre-processing/data/dmv_offices_complete.json"
        self.zip_codes_file = "pre-processing/data/zip_data/zip_poly.shp"
        self.output_file = "pre-processing/output/dmv_offices_details.csv"
        
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
        """Extract offices with valid coordinates"""
        geocoded = []
        for item in data:
            table_data = item.get('table_data', {})
            if (table_data.get('geocoded', False) and 
                table_data.get('latitude') is not None and 
                table_data.get('longitude') is not None):
                geocoded.append(table_data)
        
        print(f"📍 Found {len(geocoded)} offices with coordinates")
        return geocoded
    
    def load_california_zip_codes(self):
        """Load California ZIP codes with proper coordinate system"""
        print("🗺️ Loading California ZIP codes...")
        
        if not os.path.exists(self.zip_codes_file):
            print(f"❌ ZIP codes file not found: {self.zip_codes_file}")
            return None
        
        try:
            gdf = gpd.read_file(self.zip_codes_file)
            
            # Convert to WGS84 if needed
            if gdf.crs != 'EPSG:4326':
                gdf = gdf.to_crs('EPSG:4326')
            
            # Filter for California ZIP codes (90000-96999)
            gdf['ZIP_CODE'] = gdf['ZIP_CODE'].astype(str)
            ca_mask = (
                (gdf['ZIP_CODE'].str.startswith('90')) |
                (gdf['ZIP_CODE'].str.startswith('91')) |
                (gdf['ZIP_CODE'].str.startswith('92')) |
                (gdf['ZIP_CODE'].str.startswith('93')) |
                (gdf['ZIP_CODE'].str.startswith('94')) |
                (gdf['ZIP_CODE'].str.startswith('95')) |
                (gdf['ZIP_CODE'].str.startswith('96'))
            )
            
            gdf_ca = gdf[ca_mask].copy()
            print(f"✅ Loaded {len(gdf_ca)} California ZIP codes")
            return gdf_ca
            
        except Exception as e:
            print(f"❌ Error loading ZIP codes: {e}")
            return None
    
    def get_wait_time_numeric(self, wait_str: str) -> Optional[int]:
        """Convert wait time string to numeric value"""
        if not wait_str or wait_str == 'N/A':
            return None
        try:
            return int(wait_str) if str(wait_str).isdigit() else None
        except:
            return None
    
    def find_zip_code_for_office(self, office_lat: float, office_lon: float, zip_gdf):
        """Find which ZIP code contains a DMV office"""
        try:
            # Create point for the office
            office_point = Point(office_lon, office_lat)
            
            # Find which ZIP code contains this point
            for idx, zip_row in zip_gdf.iterrows():
                if zip_row.geometry.contains(office_point):
                    return zip_row['ZIP_CODE'], zip_row.get('PO_NAME', 'Unknown')
            
            # If no exact match, find the nearest ZIP code
            min_distance = float('inf')
            nearest_zip = None
            nearest_name = None
            
            for idx, zip_row in zip_gdf.iterrows():
                # Calculate distance from office to ZIP centroid
                zip_centroid = zip_row.geometry.centroid
                distance = ((office_lat - zip_centroid.y)**2 + (office_lon - zip_centroid.x)**2)**0.5
                
                if distance < min_distance:
                    min_distance = distance
                    nearest_zip = zip_row['ZIP_CODE']
                    nearest_name = zip_row.get('PO_NAME', 'Unknown')
            
            return nearest_zip, nearest_name
            
        except Exception as e:
            print(f"   ⚠️ Error finding ZIP for office at ({office_lat}, {office_lon}): {e}")
            return None, None
    
    def generate_csv(self):
        """Generate CSV file with DMV office details"""
        print("📊 DMV OFFICE CSV GENERATOR")
        print("=" * 40)
        
        # Load data
        dmv_data = self.load_dmv_data()
        if not dmv_data:
            return False
        
        offices = self.extract_geocoded_offices(dmv_data)
        if not offices:
            return False
        
        zip_gdf = self.load_california_zip_codes()
        if zip_gdf is None:
            return False
        
        # Process each office
        print(f"🔄 Processing {len(offices)} DMV offices...")
        
        office_records = []
        processed = 0
        
        for office in offices:
            try:
                # Extract basic info
                name = office.get('name', 'Unknown')
                address = office.get('address', 'Unknown')
                latitude = office.get('latitude')
                longitude = office.get('longitude')
                
                # Extract wait times
                appt_wait_str = office.get('current_appt_wait', 'N/A')
                walkin_wait_str = office.get('current_non_appt_wait', 'N/A')
                
                appt_wait_numeric = self.get_wait_time_numeric(appt_wait_str)
                walkin_wait_numeric = self.get_wait_time_numeric(walkin_wait_str)
                
                # Find ZIP code
                zip_code, zip_name = self.find_zip_code_for_office(latitude, longitude, zip_gdf)
                
                # Create record
                record = {
                    'office_name': name,
                    'address': address,
                    'latitude': latitude,
                    'longitude': longitude,
                    'zip_code': zip_code,
                    'zip_area_name': zip_name,
                    'appointment_wait_minutes': appt_wait_numeric,
                    'walkin_wait_minutes': walkin_wait_numeric,
                    'appointment_wait_str': appt_wait_str,
                    'walkin_wait_str': walkin_wait_str,
                    'has_coordinates': True,
                    'processing_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                office_records.append(record)
                processed += 1
                
                if processed % 20 == 0:
                    print(f"   Processed {processed}/{len(offices)} offices...")
                    
            except Exception as e:
                print(f"   ⚠️ Error processing office {office.get('name', 'Unknown')}: {e}")
                continue
        
        # Create DataFrame and save CSV
        try:
            df = pd.DataFrame(office_records)
            
            # Create output directory
            os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
            
            # Save to CSV
            df.to_csv(self.output_file, index=False)
            
            print(f"\n✅ CSV file created: {self.output_file}")
            print(f"📊 Records: {len(office_records)} DMV offices")
            
            # Show sample data
            print(f"\n📋 Sample data:")
            for i, record in enumerate(office_records[:3]):
                print(f"   {i+1}. {record['office_name']}")
                print(f"      Address: {record['address']}")
                print(f"      Location: ({record['latitude']:.4f}, {record['longitude']:.4f})")
                print(f"      ZIP: {record['zip_code']} ({record['zip_area_name']})")
                print(f"      Wait times: Appt={record['appointment_wait_minutes']}min, Walk-in={record['walkin_wait_minutes']}min")
                print()
            
            # Show statistics
            appt_waits = [r['appointment_wait_minutes'] for r in office_records if r['appointment_wait_minutes'] is not None]
            walkin_waits = [r['walkin_wait_minutes'] for r in office_records if r['walkin_wait_minutes'] is not None]
            
            print(f"📈 Statistics:")
            print(f"   Total offices: {len(office_records)}")
            print(f"   Offices with ZIP codes: {len([r for r in office_records if r['zip_code'] is not None])}")
            print(f"   Offices with appointment wait times: {len(appt_waits)}")
            print(f"   Offices with walk-in wait times: {len(walkin_waits)}")
            
            if appt_waits:
                print(f"   Average appointment wait: {sum(appt_waits)/len(appt_waits):.1f} minutes")
            if walkin_waits:
                print(f"   Average walk-in wait: {sum(walkin_waits)/len(walkin_waits):.1f} minutes")
            
            # Show column info
            print(f"\n📋 CSV Columns:")
            for col in df.columns:
                print(f"   • {col}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error creating CSV: {e}")
            return False

def main():
    generator = DMVOfficeCSVGenerator()
    success = generator.generate_csv()
    
    if success:
        print(f"\n🎉 SUCCESS! DMV office CSV file created!")
        print(f"📁 File: pre-processing/output/dmv_offices_details.csv")
        print(f"💡 Use this file for analysis, reporting, or importing into other tools")
    else:
        print(f"\n❌ Failed to create CSV file")

if __name__ == "__main__":
    main() 