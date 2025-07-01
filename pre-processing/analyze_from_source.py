#!/usr/bin/env python3
"""
DMV Data Analysis - Built from Source of Truth
Demonstrates how to build analysis from data/dmv_offices_complete.json
"""

import json
import pandas as pd
from typing import List, Dict
import os

def load_source_data() -> List[Dict]:
    """Load the single source of truth JSON file"""
    source_file = "data/dmv_offices_complete.json"
    
    if not os.path.exists(source_file):
        print(f"❌ Source file not found: {source_file}")
        print("   Run scrape_with_retry.py first to generate the data!")
        return []
    
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ Loaded {len(data)} offices from {source_file}")
        return data
    except Exception as e:
        print(f"❌ Error loading source data: {e}")
        return []

def extract_analysis_data(source_data: List[Dict]) -> pd.DataFrame:
    """Extract data into a pandas DataFrame for analysis"""
    
    rows = []
    for item in source_data:
        table_data = item.get('table_data', {})
        api_data = item.get('api_data', {})
        
        # Extract all the useful fields
        row = {
            # Basic info
            'name': table_data.get('name', 'Unknown'),
            'slug': table_data.get('slug', ''),
            'address': table_data.get('address', ''),
            'url': table_data.get('url', ''),
            
            # Current wait times
            'current_appt_wait': table_data.get('current_appt_wait', 'N/A'),
            'current_non_appt_wait': table_data.get('current_non_appt_wait', 'N/A'),
            
            # Coordinates (from geocoding)
            'latitude': table_data.get('latitude'),
            'longitude': table_data.get('longitude'),
            'geocoded': table_data.get('geocoded', False),
            
            # API data availability
            'api_success': api_data.get('success', False),
            'api_attempts': api_data.get('attempts_needed', 0),
        }
        
        # Convert wait times to numeric (handle non-numeric values)
        try:
            row['appt_wait_numeric'] = int(row['current_appt_wait']) if str(row['current_appt_wait']).isdigit() else None
        except:
            row['appt_wait_numeric'] = None
            
        try:
            row['non_appt_wait_numeric'] = int(row['current_non_appt_wait']) if str(row['current_non_appt_wait']).isdigit() else None
        except:
            row['non_appt_wait_numeric'] = None
        
        rows.append(row)
    
    df = pd.DataFrame(rows)
    print(f"📊 Created DataFrame with {len(df)} rows and {len(df.columns)} columns")
    return df

def generate_insights(df: pd.DataFrame) -> Dict:
    """Generate insights from the DataFrame"""
    
    # Filter to offices with numeric wait times
    df_with_waits = df.dropna(subset=['non_appt_wait_numeric'])
    df_geocoded = df[df['geocoded'] == True]
    
    insights = {
        'overview': {
            'total_offices': len(df),
            'geocoded_offices': len(df_geocoded),
            'offices_with_wait_data': len(df_with_waits),
            'api_success_rate': f"{(df['api_success'].sum() / len(df) * 100):.1f}%"
        },
        
        'wait_times': {},
        'geographic': {},
        'rankings': {}
    }
    
    if len(df_with_waits) > 0:
        # Wait time statistics
        insights['wait_times'] = {
            'non_appointment': {
                'average': round(df_with_waits['non_appt_wait_numeric'].mean(), 1),
                'median': df_with_waits['non_appt_wait_numeric'].median(),
                'min': df_with_waits['non_appt_wait_numeric'].min(),
                'max': df_with_waits['non_appt_wait_numeric'].max(),
                'std': round(df_with_waits['non_appt_wait_numeric'].std(), 1)
            }
        }
        
        # Add appointment wait times if available
        df_with_appt = df.dropna(subset=['appt_wait_numeric'])
        if len(df_with_appt) > 0:
            insights['wait_times']['appointment'] = {
                'average': round(df_with_appt['appt_wait_numeric'].mean(), 1),
                'median': df_with_appt['appt_wait_numeric'].median(),
                'min': df_with_appt['appt_wait_numeric'].min(),
                'max': df_with_appt['appt_wait_numeric'].max(),
                'std': round(df_with_appt['appt_wait_numeric'].std(), 1)
            }
        
        # Rankings
        insights['rankings'] = {
            'shortest_waits': df_with_waits.nsmallest(5, 'non_appt_wait_numeric')[['name', 'non_appt_wait_numeric']].to_dict('records'),
            'longest_waits': df_with_waits.nlargest(5, 'non_appt_wait_numeric')[['name', 'non_appt_wait_numeric']].to_dict('records')
        }
    
    if len(df_geocoded) > 0:
        # Geographic statistics
        insights['geographic'] = {
            'geocoded_count': len(df_geocoded),
            'center_lat': round(df_geocoded['latitude'].mean(), 4),
            'center_lon': round(df_geocoded['longitude'].mean(), 4),
            'lat_range': [df_geocoded['latitude'].min(), df_geocoded['latitude'].max()],
            'lon_range': [df_geocoded['longitude'].min(), df_geocoded['longitude'].max()]
        }
    
    return insights

def save_analysis_results(df: pd.DataFrame, insights: Dict):
    """Save analysis results"""
    os.makedirs("data", exist_ok=True)
    
    # Save detailed DataFrame as CSV for further analysis
    df.to_csv("data/dmv_offices_analysis.csv", index=False)
    print(f"💾 Saved detailed analysis: data/dmv_offices_analysis.csv")
    
    # Save insights as JSON
    with open("data/dmv_insights.json", 'w', encoding='utf-8') as f:
        json.dump(insights, f, indent=2, ensure_ascii=False)
    print(f"💾 Saved insights: data/dmv_insights.json")

def print_insights(insights: Dict):
    """Print key insights to console"""
    
    print(f"\n" + "="*60)
    print("📈 DMV OFFICES ANALYSIS INSIGHTS")
    print("="*60)
    
    overview = insights['overview']
    print(f"\n📊 OVERVIEW:")
    print(f"   Total offices: {overview['total_offices']}")
    print(f"   Geocoded: {overview['geocoded_offices']}")
    print(f"   With wait data: {overview['offices_with_wait_data']}")
    print(f"   API success rate: {overview['api_success_rate']}")
    
    if 'non_appointment' in insights.get('wait_times', {}):
        wait_stats = insights['wait_times']['non_appointment']
        print(f"\n⏱️  NON-APPOINTMENT WAIT TIMES:")
        print(f"   Average: {wait_stats['average']} minutes")
        print(f"   Median: {wait_stats['median']} minutes")
        print(f"   Range: {wait_stats['min']} - {wait_stats['max']} minutes")
        print(f"   Standard deviation: {wait_stats['std']} minutes")
    
    if 'appointment' in insights.get('wait_times', {}):
        appt_stats = insights['wait_times']['appointment']
        print(f"\n📅 APPOINTMENT WAIT TIMES:")
        print(f"   Average: {appt_stats['average']} minutes")
        print(f"   Median: {appt_stats['median']} minutes")
        print(f"   Range: {appt_stats['min']} - {appt_stats['max']} minutes")
    
    if 'shortest_waits' in insights.get('rankings', {}):
        print(f"\n🥇 SHORTEST WAITS:")
        for i, office in enumerate(insights['rankings']['shortest_waits'], 1):
            print(f"   {i}. {office['name']}: {office['non_appt_wait_numeric']} min")
        
        print(f"\n🥵 LONGEST WAITS:")
        for i, office in enumerate(insights['rankings']['longest_waits'], 1):
            print(f"   {i}. {office['name']}: {office['non_appt_wait_numeric']} min")
    
    if insights.get('geographic'):
        geo = insights['geographic']
        print(f"\n🌍 GEOGRAPHIC COVERAGE:")
        print(f"   Geocoded offices: {geo['geocoded_count']}")
        print(f"   Center point: {geo['center_lat']}, {geo['center_lon']}")

def main():
    print("📊 DMV DATA ANALYSIS - Built from Source of Truth")
    print("="*60)
    
    # Step 1: Load the single source of truth
    source_data = load_source_data()
    if not source_data:
        return
    
    # Step 2: Convert to DataFrame for analysis
    print(f"\n🔄 Processing data...")
    df = extract_analysis_data(source_data)
    
    # Step 3: Generate insights
    print(f"\n🧠 Generating insights...")
    insights = generate_insights(df)
    
    # Step 4: Save results
    print(f"\n💾 Saving analysis results...")
    save_analysis_results(df, insights)
    
    # Step 5: Display key insights
    print_insights(insights)
    
    print(f"\n🎯 ANALYSIS COMPLETE!")
    print(f"   • Source data: data/dmv_offices_complete.json")
    print(f"   • CSV export: data/dmv_offices_analysis.csv")
    print(f"   • Insights: data/dmv_insights.json")

if __name__ == "__main__":
    main() 