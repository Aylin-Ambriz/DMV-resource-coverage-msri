#!/usr/bin/env python3
"""
DMV Comprehensive Data Scraper & Mapper
Scrapes DMV data, geocodes addresses, creates interactive map

CLEAN DATA ARCHITECTURE:
• Single source of truth: data/dmv_offices_complete.json (all data + coordinates)
• Organized output: /data (JSON files) | /dashboard (HTML files)  
• All analysis builds from the main JSON file

FEATURES:
• HTML table parsing (no hardcoded lists)
• Retry logic with exponential backoff
• Address geocoding with free Nominatim service
• Interactive map with color-coded wait times
• Comprehensive error handling and progress tracking
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
import random
from typing import List, Dict, Tuple, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

class ImprovedDMVScraper:
    def __init__(self):
        self.main_url = "https://www.dmvwaittimes.live"
        self.base_api_url = "https://www.dmvwaittimes.live/api/wait_times_daily_averages"
        
        # Create session with retry strategy
        self.session = requests.Session()
        
        # Initialize geocoder for mapping
        self.geolocator = Nominatim(user_agent="dmv_office_mapper")
        self.geocoded_cache = {}
        
        # Set up retry strategy
        retry_strategy = Retry(
            total=3,  # Total number of retries
            status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry
            allowed_methods=["HEAD", "GET", "OPTIONS"],  # Fixed deprecated parameter
            backoff_factor=2  # Wait 2, 4, 8 seconds between retries
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set headers to look more like a real browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def scrape_main_table(self) -> List[Dict]:
        """Scrape the main table to get the actual list of offices"""
        print("Scraping main table from https://www.dmvwaittimes.live...")
        
        try:
            response = self.session.get(self.main_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            offices = []
            office_links = soup.find_all('a', href=re.compile(r'^/office/[^"]+'))
            
            for link in office_links:
                href = link.get('href')
                if href and href.startswith('/office/'):
                    slug = href.replace('/office/', '').strip()
                    office_name = link.get_text(strip=True)
                    
                    row = link.find_parent('tr')
                    appt_wait = None
                    non_appt_wait = None
                    address = None
                    
                    if row:
                        cells = row.find_all('td')
                        if len(cells) >= 3:
                            try:
                                appt_wait = cells[1].get_text(strip=True)
                                non_appt_wait = cells[2].get_text(strip=True)
                                address = cells[3].get_text(strip=True) if len(cells) > 3 else None
                            except:
                                pass
                    
                    offices.append({
                        'name': office_name,
                        'slug': slug,
                        'current_appt_wait': appt_wait,
                        'current_non_appt_wait': non_appt_wait,
                        'address': address,
                        'url': f"https://www.dmvwaittimes.live{href}"
                    })
            
            # Remove duplicates
            unique_offices = {}
            for office in offices:
                if office['slug'] not in unique_offices:
                    unique_offices[office['slug']] = office
            
            offices_list = list(unique_offices.values())
            offices_list.sort(key=lambda x: x['name'])
            
            print(f"Found {len(offices_list)} unique offices in the main table")
            return offices_list
            
        except Exception as e:
            print(f"Error scraping main table: {e}")
            return []
    
    def fetch_office_api_data_with_retry(self, slug: str, max_retries: int = 3) -> Dict:
        """Fetch API data for a specific office with retry logic"""
        url = f"{self.base_api_url}?slug={slug}"
        
        for attempt in range(max_retries):
            try:
                # Add random delay to avoid being detected as bot
                delay = random.uniform(1.0, 3.0)  # Random delay between 1-3 seconds
                time.sleep(delay)
                
                print(f"  Attempt {attempt + 1}/{max_retries} for {slug}...")
                
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                try:
                    data = response.json()
                    print(f"  ✅ Success for {slug}")
                    return {
                        'slug': slug,
                        'success': True,
                        'data': data,
                        'api_url': url,
                        'attempts_needed': attempt + 1
                    }
                except json.JSONDecodeError:
                    print(f"  ✅ Success (non-JSON) for {slug}")
                    return {
                        'slug': slug,
                        'success': True,
                        'data': response.text,
                        'api_url': url,
                        'content_type': response.headers.get('content-type', 'unknown'),
                        'attempts_needed': attempt + 1
                    }
                    
            except Exception as e:
                print(f"  ❌ Attempt {attempt + 1} failed for {slug}: {str(e)[:100]}...")
                
                if attempt < max_retries - 1:
                    # Exponential backoff: wait longer for each retry
                    backoff_delay = (2 ** attempt) + random.uniform(0, 1)
                    print(f"  ⏳ Waiting {backoff_delay:.1f}s before retry...")
                    time.sleep(backoff_delay)
                else:
                    print(f"  💀 All attempts failed for {slug}")
        
        return {
            'slug': slug,
            'success': False,
            'error': str(e),
            'api_url': url,
            'attempts_made': max_retries
        }
    
    def scrape_with_improved_reliability(self, offices: List[Dict], save_checkpoints: bool = True) -> List[Dict]:
        """Scrape API data with improved reliability"""
        results = []
        total_offices = len(offices)
        successful = 0
        
        print(f"\nFetching API data for {total_offices} offices with improved reliability...")
        print("Using longer delays and retry logic...")
        if save_checkpoints:
            print("💾 Saving checkpoints every 25 offices (in case of interruption)")
        print("-" * 80)
        
        for i, office in enumerate(offices, 1):
            slug = office['slug']
            print(f"\nProgress: {i}/{total_offices} - Processing {slug}...")
            
            api_result = self.fetch_office_api_data_with_retry(slug, max_retries=3)
            
            if api_result['success']:
                successful += 1
            
            combined_result = {
                'table_data': office,
                'api_data': api_result
            }
            
            results.append(combined_result)
            
            # Progress update
            success_rate = (successful / i) * 100
            print(f"  Current success rate: {success_rate:.1f}% ({successful}/{i})")
            
            # Save intermediate results every 25 offices
            if save_checkpoints and i % 25 == 0:
                self.save_results(results, f"data/dmv_offices_partial_{i}.json")
                print(f"  💾 Saved checkpoint at {i} offices")
        
        final_success_rate = (successful / total_offices) * 100
        print(f"\n🎯 Final success rate: {final_success_rate:.1f}% ({successful}/{total_offices})")
        
        return results
    
    def save_results(self, results: List[Dict], filename: str):
        """Save results to JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving results: {e}")
    
    def geocode_address(self, address: str, max_retries: int = 3) -> Optional[Tuple[float, float]]:
        """Geocode a single address to lat/long coordinates"""
        
        # Check cache first
        if address in self.geocoded_cache:
            return self.geocoded_cache[address]
        
        for attempt in range(max_retries):
            try:
                print(f"    🌍 Geocoding: {address[:40]}...")
                
                # Add "California, USA" if not already present
                search_address = address
                if "CA" in address and "USA" not in address:
                    search_address = f"{address}, USA"
                
                location = self.geolocator.geocode(search_address, timeout=10)
                
                if location:
                    coords = (location.latitude, location.longitude)
                    self.geocoded_cache[address] = coords
                    print(f"      ✅ Found: {coords[0]:.4f}, {coords[1]:.4f}")
                    
                    # Be respectful to free service
                    time.sleep(1)
                    return coords
                else:
                    print(f"      ❌ Not found")
                    
            except (GeocoderTimedOut, GeocoderServiceError) as e:
                print(f"      ⏳ Geocoding attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        print(f"      💀 Failed to geocode after {max_retries} attempts")
        self.geocoded_cache[address] = None
        return None
    
    def geocode_offices(self, results: List[Dict], save_checkpoints: bool = True) -> List[Dict]:
        """Add geocoding to scraped office data - MODIFIES EXISTING DATA IN PLACE"""
        print(f"\n🌍 Geocoding office addresses...")
        print("Using free Nominatim service...")
        print("🎯 ADDING COORDINATES TO EXISTING DATA (single source of truth)")
        if save_checkpoints:
            print("💾 Updating existing partial files with coordinates every 25 offices")
        print("-" * 60)
        
        successful_geocoding = 0
        
        for i, result in enumerate(results, 1):
            office_data = result['table_data']
            office_name = office_data['name']
            address = office_data.get('address', '')
            
            print(f"\nProgress: {i}/{len(results)} - {office_name}")
            
            if address and address.strip():
                coords = self.geocode_address(address)
                
                # ADD coordinates DIRECTLY to the existing result (modify in place)
                result['table_data']['latitude'] = coords[0] if coords else None
                result['table_data']['longitude'] = coords[1] if coords else None
                result['table_data']['geocoded'] = coords is not None
                
                if coords:
                    successful_geocoding += 1
                    print(f"    ✅ Added coordinates: {coords[0]:.4f}, {coords[1]:.4f}")
            else:
                print(f"    ❌ No address available")
                result['table_data']['latitude'] = None
                result['table_data']['longitude'] = None
                result['table_data']['geocoded'] = False
            
            # Save progress every 25 offices - OVERWRITE THE SAME FILES WITH COORDINATES NOW
            if save_checkpoints and i % 25 == 0:
                self.save_results(results, f"data/dmv_offices_partial_{i}.json")
                print(f"    💾 Updated checkpoint file with coordinates at {i} offices")
        
        geocoding_success_rate = (successful_geocoding / len(results)) * 100
        print(f"\n🎯 Geocoding success rate: {geocoding_success_rate:.1f}% ({successful_geocoding}/{len(results)})")
        print(f"📊 ALL DATA NOW INCLUDES COORDINATES - single source of truth maintained!")
        
        return results  # Return the SAME objects, now with coordinates added
    
    def get_wait_time_color(self, wait_time_str: str) -> str:
        """Get color based on wait time"""
        try:
            wait_time = int(wait_time_str) if wait_time_str.isdigit() else 0
        except:
            return 'gray'
        
        if wait_time == 0:
            return 'green'
        elif wait_time <= 30:
            return 'lightgreen'
        elif wait_time <= 60:
            return 'orange'
        elif wait_time <= 120:
            return 'red'
        else:
            return 'darkred'
    
    def create_interactive_map(self, results: List[Dict]) -> Optional[folium.Map]:
        """Create interactive map with DMV offices"""
        
        # Filter to only geocoded offices
        geocoded_offices = []
        for result in results:
            office_data = result['table_data']
            if office_data.get('geocoded', False) and office_data.get('latitude') and office_data.get('longitude'):
                geocoded_offices.append(result)
        
        if not geocoded_offices:
            print("❌ No geocoded offices to map!")
            return None
        
        print(f"\n🗺️  Creating interactive map with {len(geocoded_offices)} offices...")
        
        # Calculate center of California (approximate)
        center_lat = sum(result['table_data']['latitude'] for result in geocoded_offices) / len(geocoded_offices)
        center_lon = sum(result['table_data']['longitude'] for result in geocoded_offices) / len(geocoded_offices)
        
        # Create base map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=6,
            tiles='OpenStreetMap'
        )
        
        # Add markers for each office
        for result in geocoded_offices:
            office_data = result['table_data']
            api_data = result['api_data']
            
            # Create popup content
            popup_html = f"""
            <div style="width: 280px;">
                <h4>{office_data['name']}</h4>
                <p><strong>Address:</strong><br>{office_data['address']}</p>
                <p><strong>Current Wait Times:</strong><br>
                   📅 Appointment: {office_data['current_appt_wait']} min<br>
                   🚶 Walk-in: {office_data['current_non_appt_wait']} min
                </p>
                <p><strong>Historical API Data:</strong> {'✅ Available' if api_data['success'] else '❌ Not Available'}</p>
                <p><strong>Coordinates:</strong> {office_data['latitude']:.4f}, {office_data['longitude']:.4f}</p>
                <p><a href="{office_data['url']}" target="_blank">View Details on DMV Site</a></p>
            </div>
            """
            
            # Color based on non-appointment wait time
            color = self.get_wait_time_color(office_data['current_non_appt_wait'])
            
            folium.Marker(
                location=[office_data['latitude'], office_data['longitude']],
                popup=folium.Popup(popup_html, max_width=320),
                tooltip=f"{office_data['name']} - {office_data['current_non_appt_wait']} min wait",
                icon=folium.Icon(color=color, icon='info-sign')
            ).add_to(m)
        
        # Add legend
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 220px; height: 140px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:12px; padding: 10px; border-radius: 5px;">
        <h4 style="margin-top: 0;">Wait Time Legend</h4>
        <p><i class="fa fa-circle" style="color:green"></i> 0 minutes (No wait)</p>
        <p><i class="fa fa-circle" style="color:lightgreen"></i> 1-30 minutes (Short)</p>
        <p><i class="fa fa-circle" style="color:orange"></i> 31-60 minutes (Medium)</p>
        <p><i class="fa fa-circle" style="color:red"></i> 61-120 minutes (Long)</p>
        <p><i class="fa fa-circle" style="color:darkred"></i> 120+ minutes (Very Long)</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        return m

def main():
    import sys
    import os
    
    # Check for --no-checkpoints flag
    save_checkpoints = "--no-checkpoints" not in sys.argv
    
    # Create directories for organized output
    os.makedirs("data", exist_ok=True)
    os.makedirs("dashboard", exist_ok=True)
    
    scraper = ImprovedDMVScraper()
    
    print("🚀 DMV COMPREHENSIVE DATA SCRAPER & MAPPER")
    print("="*80)
    print("📁 Output structure: /data (JSON) | /dashboard (HTML)")
    
    if not save_checkpoints:
        print("🚫 Checkpoint saving disabled (--no-checkpoints flag)")
    else:
        print("💾 Checkpoint saving enabled (use --no-checkpoints to disable)")
    
    # Step 1: Get office list from main table
    print("\n📋 STEP 1: Scraping DMV office table...")
    table_offices = scraper.scrape_main_table()
    
    if not table_offices:
        print("❌ Failed to scrape office list!")
        return
    
    print(f"✅ Found {len(table_offices)} offices to process")
    
    # Step 2: Scrape API data with improved reliability  
    print("\n🔄 STEP 2: Fetching API data with retry logic...")
    all_data = scraper.scrape_with_improved_reliability(table_offices, save_checkpoints)
    
    # Step 3: Geocode addresses to get coordinates
    print("\n🌍 STEP 3: Geocoding office addresses...")
    geocoded_data = scraper.geocode_offices(all_data, save_checkpoints)
    
    # Step 4: Create interactive map
    print("\n🗺️  STEP 4: Creating interactive map...")
    interactive_map = scraper.create_interactive_map(geocoded_data)
    
    # Step 5: Save all results
    print("\n💾 STEP 5: Saving results...")
    
    # Save the SINGLE SOURCE OF TRUTH with all data including coordinates
    main_data_file = "data/dmv_offices_complete.json"
    scraper.save_results(geocoded_data, main_data_file)
    print(f"   📊 Source of truth saved: {main_data_file}")
    
    if interactive_map:
        map_filename = "dashboard/dmv_offices_map.html"
        interactive_map.save(map_filename)
        print(f"   🗺️  Interactive map saved: {map_filename}")
    
    # Step 6: Generate comprehensive summary
    successful_api_calls = sum(1 for item in geocoded_data if item['api_data']['success'])
    successful_geocoding = sum(1 for item in geocoded_data if item['table_data'].get('geocoded', False))
    
    summary = {
        'scraping_results': {
            'total_offices_found': len(table_offices),
            'successful_api_calls': successful_api_calls,
            'failed_api_calls': len(geocoded_data) - successful_api_calls,
            'api_success_rate': f"{(successful_api_calls/len(geocoded_data)*100):.1f}%"
        },
        'geocoding_results': {
            'total_addresses_processed': len(geocoded_data),
            'successfully_geocoded': successful_geocoding,
            'failed_geocoding': len(geocoded_data) - successful_geocoding,
            'geocoding_success_rate': f"{(successful_geocoding/len(geocoded_data)*100):.1f}%"
        },
        'mapping_results': {
            'offices_on_map': successful_geocoding,
            'map_file_created': interactive_map is not None
        },
        'wait_time_stats': {},
        'improvements_used': [
            'HTML table parsing (not hardcoded lists)',
            'Retry logic with exponential backoff',
            'Random delays between requests (1-3 seconds)',
            'Connection pooling and keep-alive',
            'Proper browser headers',
            'Increased timeout (30 seconds)',
            'Address geocoding with Nominatim',
            'Interactive map generation with Folium'
        ]
    }
    
    # Calculate wait time statistics
    geocoded_offices = [item for item in geocoded_data if item['table_data'].get('geocoded', False)]
    if geocoded_offices:
        non_appt_times = []
        appt_times = []
        
        for item in geocoded_offices:
            office_data = item['table_data']
            try:
                if office_data['current_non_appt_wait'].isdigit():
                    non_appt_times.append(int(office_data['current_non_appt_wait']))
                if office_data['current_appt_wait'].isdigit():
                    appt_times.append(int(office_data['current_appt_wait']))
            except:
                pass
        
        summary['wait_time_stats'] = {
            'non_appointment': {
                'count': len(non_appt_times),
                'average': round(sum(non_appt_times) / len(non_appt_times), 1) if non_appt_times else 0,
                'min': min(non_appt_times) if non_appt_times else 0,
                'max': max(non_appt_times) if non_appt_times else 0
            },
            'appointment': {
                'count': len(appt_times),
                'average': round(sum(appt_times) / len(appt_times), 1) if appt_times else 0,
                'min': min(appt_times) if appt_times else 0,
                'max': max(appt_times) if appt_times else 0
            }
        }
    
    scraper.save_results([summary], "data/dmv_summary.json")
    
    # Clean up partial files (only if checkpoints were enabled)
    if save_checkpoints:
        print(f"\n🧹 Cleaning up intermediate checkpoint files...")
        import glob
        import os
        
        partial_files = glob.glob("data/dmv_offices_partial_*.json")
        for file in partial_files:
            try:
                os.remove(file)
                print(f"   🗑️  Removed {file}")
            except:
                pass
        
        if partial_files:
            print(f"   ✅ Cleaned up {len(partial_files)} checkpoint files")
        else:
            print(f"   ℹ️  No checkpoint files to clean up")
    
    # Final results display
    print(f"\n" + "="*80)
    print("🎉 COMPREHENSIVE DMV PROCESSING COMPLETE!")
    print("="*80)
    
    print(f"\n📊 SCRAPING RESULTS:")
    print(f"   Total offices found: {summary['scraping_results']['total_offices_found']}")
    print(f"   API success rate: {summary['scraping_results']['api_success_rate']}")
    
    print(f"\n🌍 GEOCODING RESULTS:")
    print(f"   Successfully geocoded: {summary['geocoding_results']['successfully_geocoded']}")
    print(f"   Geocoding success rate: {summary['geocoding_results']['geocoding_success_rate']}")
    
    print(f"\n🗺️  MAPPING RESULTS:")
    print(f"   Offices plotted on map: {summary['mapping_results']['offices_on_map']}")
    print(f"   Interactive map created: {'✅ Yes' if summary['mapping_results']['map_file_created'] else '❌ No'}")
    
    if summary['wait_time_stats']:
        print(f"\n⏱️  WAIT TIME STATISTICS:")
        print(f"   Average non-appointment wait: {summary['wait_time_stats']['non_appointment']['average']} min")
        print(f"   Average appointment wait: {summary['wait_time_stats']['appointment']['average']} min")
    
    print(f"\n📁 FILES CREATED:")
    print(f"   📊 data/dmv_offices_complete.json ← **SOURCE OF TRUTH** (all data + coordinates)")
    print(f"   📈 data/dmv_summary.json (statistics and success rates)")
    if interactive_map:
        print(f"   🗺️  dashboard/dmv_offices_map.html (interactive visualization)")
    
    print(f"\n🎯 DATA ARCHITECTURE:")
    print(f"   • data/dmv_offices_complete.json = Single source of truth for all analysis")
    print(f"   • dashboard/ = All visualizations built from the source data")
    
    print(f"\n💡 NEXT STEPS:")
    print(f"   1. Open dashboard/dmv_offices_map.html in your browser")
    print(f"   2. Build additional analysis from data/dmv_offices_complete.json")
    print(f"   3. All coordinates are included - no need to re-geocode!")
    print(f"   4. Use the map to plan your DMV visit!")

if __name__ == "__main__":
    main() 