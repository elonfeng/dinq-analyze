import requests
from bs4 import BeautifulSoup
import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

@dataclass
class Position:
    position: str
    institution: str
    timeframe: str
    location: Optional[str] = None

@dataclass
class Relation:
    relation_type: str
    name: str
    timeframe: str
    profile_link: Optional[str] = None

@dataclass
class Expertise:
    area: str
    timeframe: str

@dataclass
class ProfileData:
    name: str
    current_institution: str
    career_history: List[Position]
    relations: List[Relation]
    expertise: List[Expertise]
    coauthor_links: Dict[str, str]

def parse_timeframe(timeframe_text: str) -> tuple:
    """Parse timeframe text into start and end years."""
    if not timeframe_text:
        return None, None
    
    parts = timeframe_text.strip().split('–')
    start = parts[0].strip()
    end = parts[1].strip() if len(parts) > 1 else 'Present'
    return start, end

def scrape_openreview_profile(profile_id: str) -> Optional[ProfileData]:
    """
    Scrapes information from an OpenReview profile page
    
    Args:
        profile_id (str): The OpenReview profile ID (e.g., "~Jiaxiang_Tang1")
        
    Returns:
        ProfileData: Structured profile information
    """
    url = f"https://openreview.net/profile?id={profile_id}"
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in headless mode
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    try:
        # Initialize the driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        
        # Wait for dynamic content to load (max 10 seconds)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "loading-message")))
        
        # Get the page source after content is loaded
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Extract basic information from the correct title container
        title_container = soup.find('div', class_='profile-container').find('div', class_='title-container')
        analysis_name = title_container.find('h1').text.strip() if title_container and title_container.find('h1') else "Unknown"
        print("Extracted name:", analysis_name)  # Debug print
        current_institution = title_container.find('h3').text.strip() if title_container and title_container.find('h3') else "Unknown"
        
        # Extract Career History
        career_history = []
        history_section = soup.find('section', class_='history')
        if history_section:
            for row in history_section.find_all('div', class_='table-row'):
                position = row.find('div', class_='position').find('strong').text.strip()
                institution = row.find('div', class_='institution').get_text(strip=True)
                timeframe = row.find('div', class_='timeframe').find('em').text.strip()
                location = row.find('span', class_='geolocation')
                location_text = location['title'] if location else None
                
                career_history.append(Position(
                    position=position,
                    institution=institution,
                    timeframe=timeframe,
                    location=location_text
                ))
        
        # Extract Relations
        relations = []
        relations_section = soup.find('section', class_='relations')
        if relations_section:
            for row in relations_section.find_all('div', class_='table-row'):
                relation_type = row.find('div').find('strong').text.strip()
                name_elem = row.find_all('div')[1].find('a')
                name = name_elem.text.strip() if name_elem else row.find_all('div')[1].text.strip()
                profile_link = name_elem['href'] if name_elem else None
                timeframe = row.find('em').text.strip() if row.find('em') else ""
                
                relations.append(Relation(
                    relation_type=relation_type,
                    name=name,
                    timeframe=timeframe,
                    profile_link=profile_link
                ))
        
        # Extract Expertise
        expertise = []
        expertise_section = soup.find('section', class_='expertise')
        if expertise_section:
            for row in expertise_section.find_all('div', class_='table-row'):
                area = row.find('div').find('span').text.strip()
                timeframe = row.find('div', class_='start-end-year').find('em').text.strip()
                
                expertise.append(Expertise(
                    area=area,
                    timeframe=timeframe
                ))
        
        # Wait for dynamic content to load and click the View all co-authors link
        try:
            # Wait for the coauthors section to load
            coauthors_section = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "coauthors")))
            # Wait for the loading message to disappear
            wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "loading-message")))
            time.sleep(2)  # Give extra time for content to load
            
            # Find all links in the coauthors section and look for the View all link
            links = coauthors_section.find_elements(By.TAG_NAME, "a")
            view_all_link = None
            for link in links:
                if "View all" in link.text and "co-authors" in link.text:
                    view_all_link = link
                    break
            
            if view_all_link:
                view_all_link.click()
                # Wait for modal to appear and content to load
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "modal-content")))
                time.sleep(2)  # Give time for the content to fully load
                
                # Get updated page source after modal loads
                page_source = driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
            else:
                print("Note: Could not find View all co-authors link")
        except Exception as e:
            print(f"Note: Could not load full co-authors list: {e}")

        # Extract Co-Authors from modal if available
        coauthors = []
        coauthor_links = {}  # Add a dictionary to store name -> profile_id mapping
        modal_content = soup.find('div', class_='modal-content')
        if modal_content:
            coauthor_list = modal_content.find('ul', class_='list-unstyled')
            if coauthor_list:
                for li in coauthor_list.find_all('li'):
                    author_link = li.find('a')
                    if author_link:
                        name = author_link.text.strip()
                        profile_id = author_link.get('href')  # Get the href attribute
                        coauthors.append(name)
                        if profile_id and '/profile?id=' in profile_id:
                            coauthor_links[name] = profile_id
        
        # If modal extraction failed, try getting from the main section
        if not coauthors:
            coauthors_section = soup.find('section', class_='coauthors')
            if coauthors_section:
                section_content = coauthors_section.find('div', class_='section-content')
                if section_content:
                    coauthor_list = section_content.find('ul', class_='list-unstyled')
                    if coauthor_list:
                        for li in coauthor_list.find_all('li'):
                            author_link = li.find('a')
                            if author_link:
                                name = author_link.text.strip()
                                profile_id = author_link.get('href')  # Get the href attribute
                                coauthors.append(name)
                                if profile_id and '/profile?id=' in profile_id:
                                    coauthor_links[name] = profile_id
        
        return ProfileData(
            name=analysis_name,
            current_institution=current_institution,
            career_history=career_history,
            relations=relations,
            expertise=expertise,
            coauthor_links=coauthor_links
        )
    
    except Exception as e:
        print(f"Error fetching profile: {e}")
        return None
    finally:
        if 'driver' in locals():
            driver.quit()

def save_to_json(data: ProfileData, filename: str):
    """
    Save the scraped data to a JSON file
    
    Args:
        data (ProfileData): The scraped profile data
        filename (str): Output filename
    """
    # Convert dataclasses to dictionary
    data_dict = {
        'name': data.name,
        'current_institution': data.current_institution,
        'career_history': [vars(pos) for pos in data.career_history],
        'relations': [vars(rel) for rel in data.relations],
        'expertise': [vars(exp) for exp in data.expertise],
        'coauthor_links': data.coauthor_links
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data_dict, f, indent=4, ensure_ascii=False)
    print(f"Data saved to {filename}")

def main():
    # Profile ID to scrape
    profile_id = "~Daiheng_Gao3"
    
    # Scrape the profile
    profile_data = scrape_openreview_profile(profile_id)
    
    if profile_data:
        # Generate output filename
        name = profile_data.name.replace(' ', '_').lower()
        filename = f"{name}_openreview_profile.json"
        
        # Save the data
        save_to_json(profile_data, filename)
        
        # Print summary
        print("\nProfile Summary:")
        print(f"Name: {profile_data.name}")
        print(f"Current Institution: {profile_data.current_institution}")
        print(f"Career History: {len(profile_data.career_history)} positions")
        print(profile_data.career_history)
        print(f"Relations: {len(profile_data.relations)} connections")
        print(profile_data.relations)
        print(f"Expertise: {len(profile_data.expertise)} areas")
        print(profile_data.expertise)
        print(f"Co-Authors: {len(profile_data.coauthor_links)} people")
        print(profile_data.coauthor_links)
    else:
        print("Failed to scrape profile data.")

if __name__ == "__main__":
    main()