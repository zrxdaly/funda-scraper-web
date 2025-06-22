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
            st.info(f"🔍 Scraping: {url}")
            
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
            
            # Extract address
            address_selectors = ['h1', '[data-test-id="street-name-house-number"]', '.object-header__title']
            for selector in address_selectors:
                try:
                    element = soup.select_one(selector)
                    if element:
                        data['address'] = element.get_text(strip=True)
                        break
                except:
                    continue
            
            # Extract price
            price_patterns = [
                ('€', '.000', 'k.k.'),
                ('€', '.000', 'kosten koper'),
                ('€', '.000', 'vk')
            ]
            
            for pattern in price_patterns:
                price_elements = soup.find_all(text=re.compile(r'€.*\.000.*(?:k\.k\.|kosten koper|vk)', re.IGNORECASE))
                if price_elements:
                    for price_text in price_elements:
                        if 'per maand' not in price_text.lower():
                            data['asking_price'] = price_text.strip()
                            break
                    if data['asking_price']:
                        break
            
            # Extract area from characteristics
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
                    
                    elif 'energielabel' in dt_text or 'energie' in dt_text:
                        dd = dt.find_next_sibling('dd')
                        if dd:
                            dd_text = dd.get_text(strip=True)
                            energy_match = re.search(r'([A-G])', dd_text)
                            if energy_match:
                                data['energy_label'] = energy_match.group(1)
                except:
                    continue
            
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
