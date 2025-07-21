#!/usr/bin/env python3
"""
ZIP Code Underserved Map Generator
Creates a simple static image map showing California ZIP codes colored by underserved status.
Red = UNDERSERVED, Green = NOT UNDERSERVED
"""

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import ListedColormap
import numpy as np
import os

def create_underserved_map():
    """Create a static map showing underserved ZIP codes"""
    print("🗺️ Creating ZIP Code Underserved Map...")
    
    # Load the analysis results
    print("📊 Loading analysis results...")
    results_df = pd.read_csv("output/zip_underserved_mapping.csv")
    results_df['ZIP_CODE'] = results_df['ZIP_CODE'].astype(str)  # Ensure string type
    print(f"✅ Loaded {len(results_df)} ZIP code classifications")
    
    # Load ZIP code shapefile
    print("🗺️ Loading ZIP code geometries...")
    zip_gdf = gpd.read_file("data/zip_data/zip_poly.shp")
    
    # Convert to WGS84 if needed
    if zip_gdf.crs != 'EPSG:4326':
        print("🔄 Converting to WGS84...")
        zip_gdf = zip_gdf.to_crs('EPSG:4326')
    
    # Filter for California ZIP codes and ensure string type
    zip_gdf['ZIP_CODE'] = zip_gdf['ZIP_CODE'].astype(str)
    ca_mask = (
        (zip_gdf['ZIP_CODE'].str.startswith('90')) |
        (zip_gdf['ZIP_CODE'].str.startswith('91')) |
        (zip_gdf['ZIP_CODE'].str.startswith('92')) |
        (zip_gdf['ZIP_CODE'].str.startswith('93')) |
        (zip_gdf['ZIP_CODE'].str.startswith('94')) |
        (zip_gdf['ZIP_CODE'].str.startswith('95')) |
        (zip_gdf['ZIP_CODE'].str.startswith('96')) |
        (zip_gdf['ZIP_CODE'].str.startswith('00'))
    )
    zip_gdf = zip_gdf[ca_mask].copy()
    print(f"✅ Filtered to {len(zip_gdf)} California ZIP codes")
    
    # Merge with analysis results
    print("🔗 Merging with underserved classifications...")
    merged_gdf = zip_gdf.merge(results_df[['ZIP_CODE', 'STATUS']], 
                               left_on='ZIP_CODE', right_on='ZIP_CODE', how='left')
    
    # Fill any missing statuses (shouldn't happen but just in case)
    merged_gdf['STATUS'] = merged_gdf['STATUS'].fillna('NOT UNDERSERVED')
    
    print(f"✅ Merged data: {len(merged_gdf)} ZIP codes")
    
    # Create the map
    print("🎨 Creating map visualization...")
    
    # Set up the plot
    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    
    # Color mapping
    colors = {
        'UNDERSERVED': '#FF4444',      # Red
        'NOT UNDERSERVED': '#44AA44'   # Green
    }
    
    # Plot ZIP codes by status
    for status, color in colors.items():
        subset = merged_gdf[merged_gdf['STATUS'] == status]
        if len(subset) > 0:
            subset.plot(ax=ax, color=color, alpha=0.7, edgecolor='white', linewidth=0.1)
            print(f"   Plotted {len(subset)} {status} ZIP codes in {color}")
    
    # Load and plot DMV offices
    print("📍 Adding DMV office markers...")
    try:
        dmv_df = pd.read_csv("output/dmv_offices_details.csv")
        ax.scatter(dmv_df['longitude'], dmv_df['latitude'], 
                  c='darkblue', s=15, marker='o', alpha=0.8, 
                  edgecolors='white', linewidth=0.5, zorder=5)
        print(f"   Added {len(dmv_df)} DMV office markers")
    except Exception as e:
        print(f"   ⚠️ Could not add DMV offices: {e}")
    
    # Set map bounds to California
    ax.set_xlim(-125, -114)
    ax.set_ylim(32.5, 42)
    
    # Styling
    ax.set_title('California ZIP Codes: DMV Service Coverage Analysis\nBased on Persistent Homology Death Simplices', 
                fontsize=18, fontweight='bold', pad=20)
    ax.set_xlabel('Longitude', fontsize=14)
    ax.set_ylabel('Latitude', fontsize=14)
    
    # Remove tick labels for cleaner look
    ax.tick_params(axis='both', which='major', labelsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_facecolor('#E6F3FF')  # Light blue background (ocean)
    
    # Create legend
    legend_elements = [
        patches.Patch(color='#FF4444', label=f'UNDERSERVED ({(results_df["STATUS"] == "UNDERSERVED").sum()} ZIP codes)'),
        patches.Patch(color='#44AA44', label=f'NOT UNDERSERVED ({(results_df["STATUS"] == "NOT UNDERSERVED").sum()} ZIP codes)'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='darkblue', 
                   markersize=8, label=f'DMV Offices ({len(dmv_df) if "dmv_df" in locals() else "N/A"})')
    ]
    
    ax.legend(handles=legend_elements, loc='upper right', fontsize=12, 
              fancybox=True, shadow=True, framealpha=0.9)
    
    # Add summary text
    underserved_count = (results_df['STATUS'] == 'UNDERSERVED').sum()
    total_count = len(results_df)
    underserved_pct = underserved_count / total_count * 100
    
    summary_text = f"""Analysis Summary:
• Total ZIP Codes: {total_count:,}
• Underserved: {underserved_count:,} ({underserved_pct:.1f}%)
• Method: Topological Data Analysis
• Based on: 1D Persistent Homology Death Simplices"""
    
    ax.text(0.02, 0.02, summary_text, transform=ax.transAxes, fontsize=10,
            bbox=dict(boxstyle="round,pad=0.5", facecolor='white', alpha=0.8),
            verticalalignment='bottom')
    
    # Save the map
    output_file = "output/zip_underserved_map.png"
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    
    print(f"✅ Map saved to: {output_file}")
    print(f"📊 Summary: {underserved_count} underserved ZIP codes ({underserved_pct:.1f}%)")
    
    plt.show()
    
    return True

def main():
    print("🎯 ZIP CODE UNDERSERVED MAP GENERATOR")
    print("=" * 50)
    
    # Create output directory if needed
    os.makedirs("output", exist_ok=True)
    
    # Generate the map
    success = create_underserved_map()
    
    if success:
        print("\n🎉 Map generation completed successfully!")
    else:
        print("\n❌ Map generation failed!")

if __name__ == "__main__":
    main() 