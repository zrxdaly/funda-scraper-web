import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import quote
import io
from datetime import datetime
import base64

# Configure page
st.set_page_config(
    page_title="Funda Property Scraper",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .property-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
        background-color: #f9f9f9;
    }
    .success-message {
        color: #28a745;
        font-weight: bold;
    }
    .error-message {
        color: #dc3545;
        font-weight: bold;
    }
    .info-box {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 5px;
        border-left: 4px solid #2196f3;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

class OnlineFundaScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
    
    def extract_property_data(self, url: str) -> dict:
        """Extract property data from Funda URL using requests/BeautifulSoup"""
        try:
            # Debug: Show what we found
            if data['address']:
                st.success(f"✅ Found address: {data['address']}")
            else:
                st.warning("⚠️ Could not extract address")
                
            if data['asking_price']:
                st.success(f"✅ Found price: {data['asking_price']}")
            else:
                st.warning("⚠️ Could not extract price")
                
            if data['area_m2']:
                st.success(f"✅ Found area: {data['area_m2']} m²")
            else:
                st.warning("⚠️ Could not extract area")
                
            if data['energy_label']:
                st.success(f"✅ Found energy label: {data['energy_label']}")
            else:
                st.warning("⚠️ Could not extract energy label")
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            data = {
                'address': None,
                'link': url,
                'asking_price': None,
                'area_m2': None,
                'energy_label': None,
                'status': 'Success'
            }
            
            # Extract address with multiple methods
            # Method 1: Try common selectors
            address_selectors = [
                'h1',
                '[data-test-id="street-name-house-number"]', 
                '.object-header__title',
                '.fd-color-dark-1',
                'h1[class*="object"]',
                '.object-address'
            ]
            
            for selector in address_selectors:
                try:
                    element = soup.select_one(selector)
                    if element and element.get_text(strip=True):
                        address_text = element.get_text(strip=True)
                        # Filter out non-address text
                        if len(address_text) > 10 and any(char.isdigit() for char in address_text):
                            data['address'] = address_text
                            break
                except:
                    continue
            
            # Method 2: Extract from page title if not found
            if not data['address']:
                try:
                    title = soup.find('title')
                    if title:
                        title_text = title.get_text()
                        # Extract address from title like "Wageningseberg 4, 3524 LR Utrecht - Funda"
                        address_match = re.search(r'^([^-]+)', title_text)
                        if address_match:
                            potential_address = address_match.group(1).strip()
                            if len(potential_address) > 10:
                                data['address'] = potential_address
                except:
                    pass
            
            # Method 3: Look for address patterns in text
            if not data['address']:
                try:
                    # Look for address patterns in all text
                    page_text = soup.get_text()
                    # Pattern for Dutch addresses: Street + number + postal code + city
                    address_patterns = [
                        r'([A-Za-z\s]+\s+\d+[A-Za-z]?[,\s]+\d{4}\s*[A-Z]{2}[,\s]+[A-Za-z\s]+)',
                        r'([A-Za-z\s]+\s+\d+[A-Za-z]?[,\s\n]+[A-Za-z\s]+)'
                    ]
                    
                    for pattern in address_patterns:
                        matches = re.findall(pattern, page_text)
                        for match in matches:
                            if len(match) > 15 and len(match) < 100:  # Reasonable address length
                                data['address'] = match.strip()
                                break
                        if data['address']:
                            break
                except:
                    pass
            
            # Extract price with improved method
            # Method 1: Look for span elements with € and numbers
            price_found = False
            try:
                # Find all text containing € and .000
                all_text = soup.get_text()
                price_patterns = [
                    r'€\s*(\d{2,3}(?:\.\d{3})+)\s*k\.k\.',  # € 395.000 k.k.
                    r'€\s*(\d{2,3}(?:\.\d{3})+)\s*kk',      # € 395.000 kk
                    r'€\s*(\d{2,3}(?:\.\d{3})+)\s*kosten koper',  # € 395.000 kosten koper
                    r'€\s*(\d{2,3}(?:\.\d{3})+)\s*vk',      # € 395.000 vk
                    r'€\s*(\d{2,3}(?:\.\d{3})+)',           # € 395.000 (fallback)
                ]
                
                for pattern in price_patterns:
                    matches = re.findall(pattern, all_text, re.IGNORECASE)
                    if matches:
                        # Check if it's not monthly rent
                        context_start = max(0, all_text.find(f"€ {matches[0]}") - 50)
                        context_end = min(len(all_text), all_text.find(f"€ {matches[0]}") + 100)
                        context = all_text[context_start:context_end].lower()
                        
                        if 'per maand' not in context and 'maandlasten' not in context:
                            if 'k.k.' in pattern or 'kk' in pattern or 'kosten koper' in pattern:
                                data['asking_price'] = f"€ {matches[0]} k.k."
                            elif 'vk' in pattern:
                                data['asking_price'] = f"€ {matches[0]} vk"
                            else:
                                data['asking_price'] = f"€ {matches[0]}"
                            price_found = True
                            break
            except:
                pass
            
            # Method 2: Look in structured data (JSON-LD)
            if not price_found:
                try:
                    scripts = soup.find_all('script', type='application/ld+json')
                    for script in scripts:
                        try:
                            import json
                            data_json = json.loads(script.string)
                            if isinstance(data_json, dict) and 'offers' in data_json:
                                price = data_json['offers'].get('price')
                                if price:
                                    data['asking_price'] = f"€ {price:,.0f}".replace(',', '.')
                                    price_found = True
                                    break
                        except:
                            continue
                except:
                    pass
            
            # Enhanced area extraction
            # Method 1: Look in dt/dd pairs
            dt_elements = soup.find_all('dt')
            for dt in dt_elements:
                try:
                    dt_text = dt.get_text(strip=True).lower()
                    if any(keyword in dt_text for keyword in ['woonoppervlakte', 'oppervlakte', 'gebruiksoppervlakte']):
                        dd = dt.find_next_sibling('dd')
                        if dd:
                            dd_text = dd.get_text(strip=True)
                            area_match = re.search(r'(\d+(?:[,\.]\d+)?)\s*m[²2]?', dd_text)
                            if area_match:
                                data['area_m2'] = area_match.group(1).replace(',', '.')
                                break
                    
                    elif 'energielabel' in dt_text or 'energie' in dt_text:
                        dd = dt.find_next_sibling('dd')
                        if dd:
                            dd_text = dd.get_text(strip=True)
                            energy_match = re.search(r'([A-G])', dd_text)
                            if energy_match:
                                data['energy_label'] = energy_match.group(1)
                except:
                    continue
            
            # Method 2: Look for area in all text if not found
            if not data['area_m2']:
                try:
                    all_text = soup.get_text()
                    # Look for patterns like "71 m²" or "71m2"
                    area_matches = re.findall(r'(\d+(?:[,\.]\d+)?)\s*m[²2]', all_text)
                    for match in area_matches:
                        area_value = float(match.replace(',', '.'))
                        if 10 <= area_value <= 1000:  # Reasonable house size
                            data['area_m2'] = match.replace(',', '.')
                            break
                except:
                    pass
            
            # Method 3: Look for energy label in all text if not found
            if not data['energy_label']:
                try:
                    all_text = soup.get_text()
                    # Look for "Energielabel A" or similar
                    energy_matches = re.findall(r'[Ee]nergielabel[:\s]*([A-G])', all_text)
                    if energy_matches:
                        data['energy_label'] = energy_matches[0].upper()
                except:
                    pass
            
            return data
            
        except Exception as e:
            return {
                'address': None,
                'link': url,
                'asking_price': None,
                'area_m2': None,
                'energy_label': None,
                'status': f'Error: {str(e)}'
            }
    
    def get_commute_time_url(self, home_address: str, work_address: str) -> str:
        """Generate Google Maps URL for commute checking"""
        home_clean = home_address.replace('\n', ' ').strip()
        work_clean = work_address.replace('\n', ' ').strip()
        return f"https://www.google.com/maps/dir/{quote(home_clean)}/{quote(work_clean)}/data=!3m1!4b1!4m2!4m1!3e3"

def create_download_link(df, filename):
    """Create a download link for the DataFrame"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Properties', index=False)
    
    b64 = base64.b64encode(output.getvalue()).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">📥 Download Excel File</a>'
    return href

def main():
    # Header
    st.markdown('<h1 class="main-header">🏠 Funda Property Scraper</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-box">
        <strong>📌 How it works:</strong><br>
        1. Add Funda property URLs<br>
        2. Enter your work addresses<br>
        3. Click "Scrape Properties"<br>
        4. Get Google Maps links for manual commute checking<br>
        5. Download Excel with all data
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar for inputs
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # URLs Section
        st.subheader("🔗 Property URLs")
        url_input = st.text_input("Add Funda URL:", placeholder="https://www.funda.nl/detail/koop/...")
        
        # Initialize session state for URLs
        if 'urls_list' not in st.session_state:
            st.session_state.urls_list = []
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Add URL"):
                if url_input.strip() and "funda.nl" in url_input:
                    st.session_state.urls_list.append(url_input.strip())
                    st.success("URL added!")
                elif url_input.strip():
                    st.error("Please enter a valid Funda URL")
        
        with col2:
            if st.button("🗑️ Clear All"):
                st.session_state.urls_list = []
                st.success("URLs cleared!")
        
        # Display current URLs
        if st.session_state.urls_list:
            st.write("**Added URLs:**")
            for i, url in enumerate(st.session_state.urls_list):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.text(f"{i+1}. {url[:50]}...")
                with col2:
                    if st.button("❌", key=f"remove_{i}"):
                        st.session_state.urls_list.pop(i)
                        st.rerun()
        
        st.divider()
        
        # Work Addresses Section
        st.subheader("🏢 Work Addresses")
        work_address_1 = st.text_input("Work Address 1:", placeholder="Amsterdam Centraal Station, Amsterdam")
        
        use_second_address = st.checkbox("Add second work address")
        work_address_2 = ""
        if use_second_address:
            work_address_2 = st.text_input("Work Address 2:", placeholder="Rotterdam Centraal, Rotterdam")
        
        st.divider()
        
        # Output Settings
        st.subheader("📊 Output Settings")
        output_filename = st.text_input("Output filename:", value="funda_properties.xlsx")
        
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        if st.button("🚀 Scrape Properties", type="primary", use_container_width=True):
            if not st.session_state.urls_list:
                st.error("❌ Please add at least one Funda URL")
            elif not work_address_1.strip():
                st.error("❌ Please enter at least one work address")
            else:
                # Initialize scraper
                scraper = OnlineFundaScraper()
                
                # Progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                properties_data = []
                
                for i, url in enumerate(st.session_state.urls_list):
                    progress = (i + 1) / len(st.session_state.urls_list)
                    progress_bar.progress(progress)
                    status_text.text(f"Scraping property {i+1}/{len(st.session_state.urls_list)}")
                    
                    # Scrape property data
                    property_data = scraper.extract_property_data(url)
                    
                    # Debug mode: show raw HTML snippet
                    if st.session_state.get('debug_mode', False):
                        with st.expander(f"🐛 Debug info for {property_data.get('address', 'Unknown')}"):
                            try:
                                response = scraper.session.get(url, timeout=10)
                                soup = BeautifulSoup(response.content, 'html.parser')
                                
                                # Show page title
                                title = soup.find('title')
                                if title:
                                    st.write(f"**Page Title:** {title.get_text()}")
                                
                                # Show first few h1 elements
                                h1_elements = soup.find_all('h1')[:3]
                                if h1_elements:
                                    st.write("**H1 elements found:**")
                                    for i, h1 in enumerate(h1_elements):
                                        st.write(f"{i+1}. {h1.get_text(strip=True)}")
                                
                                # Show some text containing € or address patterns
                                text_snippet = soup.get_text()[:2000]
                                st.text_area("Raw text (first 2000 chars):", text_snippet, height=200)
                                
                            except Exception as e:
                                st.error(f"Debug error: {e}")
                    
                    # Add commute URLs
                    if property_data['address'] and work_address_1:
                        property_data['commute_url_1'] = scraper.get_commute_time_url(
                            property_data['address'], work_address_1
                        )
                    
                    if property_data['address'] and work_address_2:
                        property_data['commute_url_2'] = scraper.get_commute_time_url(
                            property_data['address'], work_address_2
                        )
                    
                    properties_data.append(property_data)
                    time.sleep(1)  # Be respectful to the server
                
                # Create DataFrame
                df = pd.DataFrame(properties_data)
                
                # Reorder columns
                base_columns = ['address', 'link', 'asking_price', 'area_m2', 'energy_label', 'status']
                commute_columns = []
                if work_address_1:
                    commute_columns.append('commute_url_1')
                if work_address_2:
                    commute_columns.append('commute_url_2')
                
                df = df.reindex(columns=base_columns + commute_columns)
                
                # Store in session state
                st.session_state.scraped_data = df
                st.session_state.output_filename = output_filename
                
                progress_bar.progress(1.0)
                status_text.text("✅ Scraping completed!")
                st.success("🎉 Scraping completed successfully!")
    
    with col2:
        if st.button("📋 Example URLs", use_container_width=True):
            st.info("""
            **Example Funda URLs:**
            - https://www.funda.nl/detail/koop/utrecht/...
            - https://www.funda.nl/detail/koop/amsterdam/...
            """)
        
        if st.button("🔍 Debug Mode", use_container_width=True):
            st.session_state.debug_mode = not st.session_state.get('debug_mode', False)
            if st.session_state.debug_mode:
                st.success("Debug mode ON")
            else:
                st.success("Debug mode OFF")
    
    # Display results
    if 'scraped_data' in st.session_state:
        st.header("📊 Results")
        
        df = st.session_state.scraped_data
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Properties", len(df))
        with col2:
            successful = len(df[df['status'] == 'Success'])
            st.metric("Successfully Scraped", successful)
        with col3:
            errors = len(df[df['status'] != 'Success'])
            st.metric("Errors", errors)
        with col4:
            if successful > 0:
                avg_price = df[df['asking_price'].notna()]['asking_price'].str.extract(r'(\d+)').astype(float).mean().iloc[0]
                st.metric("Avg Price (k€)", f"{avg_price:.0f}")
        
        # Display data table
        st.subheader("Property Details")
        st.dataframe(df, use_container_width=True)
        
        # Commute time instructions
        if 'commute_url_1' in df.columns or 'commute_url_2' in df.columns:
            st.subheader("🚗 Commute Time Checking")
            
            for index, row in df.iterrows():
                if row['address']:
                    with st.expander(f"📍 {row['address']}"):
                        col1, col2 = st.columns(2)
                        
                        if 'commute_url_1' in row and pd.notna(row['commute_url_1']):
                            with col1:
                                st.markdown(f"**To Work Address 1:**")
                                st.markdown(f"[🗺️ Check Commute Time]({row['commute_url_1']})")
                                commute_1 = st.text_input(f"Enter commute time:", key=f"commute1_{index}", placeholder="e.g., 45min or 1h 30min")
                        
                        if 'commute_url_2' in row and pd.notna(row['commute_url_2']):
                            with col2:
                                st.markdown(f"**To Work Address 2:**")
                                st.markdown(f"[🗺️ Check Commute Time]({row['commute_url_2']})")
                                commute_2 = st.text_input(f"Enter commute time:", key=f"commute2_{index}", placeholder="e.g., 45min or 1h 30min")
        
        # Update DataFrame with commute times and create download
        if st.button("💾 Prepare Download", type="secondary"):
            # Add manually entered commute times to DataFrame
            for index, row in df.iterrows():
                if f"commute1_{index}" in st.session_state:
                    df.at[index, 'commute_time_1'] = st.session_state[f"commute1_{index}"]
                if f"commute2_{index}" in st.session_state:
                    df.at[index, 'commute_time_2'] = st.session_state[f"commute2_{index}"]
            
            # Remove URL columns for cleaner export
            export_df = df.drop(columns=[col for col in df.columns if col.startswith('commute_url')])
            
            # Create download link
            download_link = create_download_link(export_df, st.session_state.output_filename)
            st.markdown(download_link, unsafe_allow_html=True)
            st.success("📁 File prepared for download!")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666;'>
        <p>🏠 Funda Property Scraper | Built with ❤️ using Streamlit</p>
        <p><small>⚠️ Please respect Funda's terms of service and use responsibly</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
