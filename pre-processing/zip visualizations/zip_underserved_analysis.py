#!/usr/bin/env python3
"""
ZIP Code Underserved Analysis
Maps every California ZIP code to UNDERSERVED/NOT UNDERSERVED based on 
intersection with death simplex triangles from 1D persistent homology analysis.

Output: zip_underserved_mapping.csv
"""

import pandas as pd
import geopandas as gpd
import numpy as np
import json
from shapely.geometry import Polygon, Point
import gudhi as gd
import gudhi.weighted_rips_complex
from typing import List, Dict, Tuple
import os

class ZipUnderservedAnalyzer:
    def __init__(self):
        self.dmv_offices_file = "output/dmv_offices_details.csv"
        self.distance_matrix_file = "../dmv_Symmetric_Distance_Matrix.csv"
        self.wait_vector_file = "../dmv_waits.csv"
        self.zip_codes_file = "data/zip_data/zip_poly.shp"
        self.output_file = "output/zip_underserved_mapping.csv"
        
    def load_dmv_data(self):
        """Load DMV office data with coordinates"""
        print("📍 Loading DMV office data...")
        try:
            dmv_df = pd.read_csv(self.dmv_offices_file)
            print(f"✅ Loaded {len(dmv_df)} DMV offices")
            return dmv_df
        except Exception as e:
            print(f"❌ Error loading DMV data: {e}")
            return None
    
    def load_distance_and_wait_data(self):
        """Load distance matrix and wait vector for persistent homology"""
        print("📊 Loading distance matrix and wait times...")
        try:
            distance_matrix = pd.read_csv(self.distance_matrix_file, index_col=0).values
            wait_vector = np.genfromtxt(self.wait_vector_file, delimiter=",")
            print(f"✅ Loaded {len(distance_matrix)} x {len(distance_matrix[0])} distance matrix")
            print(f"✅ Loaded {len(wait_vector)} wait times")
            return distance_matrix, wait_vector
        except Exception as e:
            print(f"❌ Error loading distance/wait data: {e}")
            return None, None
    
    def compute_death_simplices(self, distance_matrix, wait_vector):
        """Compute 1D death simplices using persistent homology"""
        print("🔬 Computing persistent homology...")
        try:
            # Create weighted Vietoris-Rips complex
            weighted_cpx = gd.weighted_rips_complex.WeightedRipsComplex(
                distance_matrix=distance_matrix,
                weights=wait_vector
            ).create_simplex_tree(max_dimension=2)
            
            # Compute persistence
            weighted_cpx.compute_persistence()
            all_pairs = weighted_cpx.persistence_pairs()
            
            # Extract 1D death simplices (triangles)
            pairs_1d = [pair for pair in all_pairs if len(pair[1]) == 3]
            
            if pairs_1d:
                feature_data = [[pair[1], weighted_cpx.filtration(pair[1])] for pair in pairs_1d]
                feature_data.sort(key=lambda x: x[1], reverse=True)
                
                death_simplices = [simplex for simplex, _ in feature_data]
                print(f"✅ Found {len(death_simplices)} death simplices (1D features)")
                return death_simplices
            else:
                print("❌ No 1D death simplices found")
                return []
                
        except Exception as e:
            print(f"❌ Error computing persistent homology: {e}")
            return []
    
    def create_death_simplex_triangles(self, death_simplices, dmv_df):
        """Create triangle polygons from death simplices coordinates"""
        print("🔺 Creating triangle polygons from death simplices...")
        triangles = []
        
        for i, simplex in enumerate(death_simplices):
            try:
                # Get coordinates for the three offices in this simplex
                coords = []
                office_names = []
                
                for vertex in simplex:
                    lat = dmv_df.iloc[vertex]['latitude']
                    lon = dmv_df.iloc[vertex]['longitude']
                    name = dmv_df.iloc[vertex]['office_name']
                    coords.append((lon, lat))  # Note: (lon, lat) for Shapely
                    office_names.append(name)
                
                # Create triangle polygon
                if len(coords) == 3:
                    triangle = Polygon(coords)
                    triangles.append({
                        'geometry': triangle,
                        'simplex_id': i,
                        'office_names': office_names,
                        'vertices': list(simplex)  # Convert to list here instead
                    })
                    
            except Exception as e:
                print(f"   ⚠️ Error creating triangle for simplex {i}: {e}")
                continue
        
        print(f"✅ Created {len(triangles)} triangle polygons")
        return triangles
    
    def load_california_zip_codes(self):
        """Load California ZIP code polygons"""
        print("🗺️ Loading California ZIP codes...")
        
        if not os.path.exists(self.zip_codes_file):
            print(f"❌ ZIP codes file not found: {self.zip_codes_file}")
            return None
        
        try:
            # Load shapefile
            gdf = gpd.read_file(self.zip_codes_file)
            
            # Convert to WGS84 if needed
            if gdf.crs != 'EPSG:4326':
                print("🔄 Converting to WGS84...")
                gdf = gdf.to_crs('EPSG:4326')
            
            # Filter for California ZIP codes
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
    
    def analyze_zip_underservice(self, zip_gdf, triangles):
        """Analyze each ZIP code for intersection with death simplex triangles"""
        print("🔍 Analyzing ZIP codes for underservice...")
        
        results = []
        underserved_count = 0
        
        for idx, zip_row in zip_gdf.iterrows():
            try:
                zip_code = zip_row['ZIP_CODE']
                zip_name = zip_row.get('PO_NAME', f'ZIP {zip_code}')
                zip_geom = zip_row.geometry
                
                # Check intersection with any death simplex triangle
                is_underserved = False
                intersecting_triangles = []
                
                for triangle_info in triangles:
                    triangle_geom = triangle_info['geometry']
                    
                    # Check if ZIP polygon intersects with triangle
                    if zip_geom.intersects(triangle_geom):
                        is_underserved = True
                        intersecting_triangles.append({
                            'simplex_id': triangle_info['simplex_id'],
                            'office_names': triangle_info['office_names']
                        })
                
                # Determine status
                status = "UNDERSERVED" if is_underserved else "NOT UNDERSERVED"
                if is_underserved:
                    underserved_count += 1
                
                # Store result
                result = {
                    'ZIP_CODE': zip_code,
                    'ZIP_NAME': zip_name,
                    'STATUS': status,
                    'INTERSECTING_TRIANGLES_COUNT': len(intersecting_triangles),
                    'INTERSECTING_SIMPLICES': str(intersecting_triangles) if intersecting_triangles else "None"
                }
                
                results.append(result)
                
                if (idx + 1) % 100 == 0:
                    print(f"   Processed {idx + 1}/{len(zip_gdf)} ZIP codes...")
                    
            except Exception as e:
                print(f"   ⚠️ Error processing ZIP {zip_row.get('ZIP_CODE', 'Unknown')}: {e}")
                continue
        
        print(f"✅ Analysis complete!")
        print(f"📊 Results: {underserved_count} UNDERSERVED, {len(results) - underserved_count} NOT UNDERSERVED")
        print(f"📈 Underserved percentage: {underserved_count/len(results)*100:.1f}%")
        
        return results
    
    def save_results(self, results):
        """Save results to CSV"""
        print(f"💾 Saving results to {self.output_file}...")
        
        try:
            # Create DataFrame
            df = pd.DataFrame(results)
            
            # Create output directory if needed
            os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
            
            # Save to CSV
            df.to_csv(self.output_file, index=False)
            
            print(f"✅ Saved {len(results)} ZIP code mappings to {self.output_file}")
            
            # Show summary statistics
            print("\n📊 SUMMARY STATISTICS:")
            status_counts = df['STATUS'].value_counts()
            for status, count in status_counts.items():
                percentage = count / len(df) * 100
                print(f"   {status}: {count} ({percentage:.1f}%)")
            
            # Show sample of underserved ZIP codes
            underserved = df[df['STATUS'] == 'UNDERSERVED']
            if len(underserved) > 0:
                print(f"\n🔺 Sample UNDERSERVED ZIP codes:")
                for i in range(min(5, len(underserved))):
                    row = underserved.iloc[i]
                    print(f"   {row['ZIP_CODE']} - {row['ZIP_NAME']} ({row['INTERSECTING_TRIANGLES_COUNT']} triangles)")
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving results: {e}")
            return False
    
    def run_analysis(self):
        """Run the complete analysis"""
        print("🎯 ZIP CODE UNDERSERVED ANALYSIS")
        print("=" * 50)
        
        # Step 1: Load DMV data
        dmv_df = self.load_dmv_data()
        if dmv_df is None:
            return False
        
        # Step 2: Load distance matrix and wait data
        distance_matrix, wait_vector = self.load_distance_and_wait_data()
        if distance_matrix is None or wait_vector is None:
            return False
        
        # Step 3: Compute death simplices
        death_simplices = self.compute_death_simplices(distance_matrix, wait_vector)
        if not death_simplices:
            return False
        
        # Step 4: Create triangle polygons
        triangles = self.create_death_simplex_triangles(death_simplices, dmv_df)
        if not triangles:
            return False
        
        # Step 5: Load ZIP codes
        zip_gdf = self.load_california_zip_codes()
        if zip_gdf is None:
            return False
        
        # Step 6: Analyze underservice
        results = self.analyze_zip_underservice(zip_gdf, triangles)
        if not results:
            return False
        
        # Step 7: Save results
        success = self.save_results(results)
        
        if success:
            print("\n🎉 Analysis completed successfully!")
            print(f"📄 Results saved to: {self.output_file}")
        
        return success

def main():
    analyzer = ZipUnderservedAnalyzer()
    analyzer.run_analysis()

if __name__ == "__main__":
    main() 