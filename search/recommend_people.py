import json
import os
from typing import List, Dict, Any, Optional, Union
import time
from server.llm.gateway import openrouter_chat
from pathlib import Path
import re
from bs4 import BeautifulSoup
from crawlbase import CrawlingAPI
import random

def tag_generation(title: str, authors: List[str], openrouter_key: str) -> str:
    # Create a prompt for tag generation
    system_prompt = """You are a research paper tag generator. Given a paper title and authors, generate relevant research area tags.
        Focus on high-level research areas and trending AI topics from ONLY these options:
        CV, NLP, LLM, RAG, ML, RL, 3D, GAN, Agent, Vision, Audio, Graph, Diffusion, HCI, Robotics, Security

        Rules:
        1. Return EXACTLY 3 tags from the options above
        2. Each tag MUST be a single word/abbreviation
        3. Tags MUST be separated by semicolons
        4. Return ONLY the tags, no other text
        5. If unsure, use broader category tags (ML, CV, NLP)

        Example outputs:
        "CV;3D;GAN"
        "LLM;RAG;NLP"
        "ML;Vision;Graph"
    """

    try:
        tags = openrouter_chat(
            task="recommend.tags",
            model="google/gemini-2.5-flash-preview:online",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Paper Title: {title}\nAuthors: {';'.join(authors)}"},
            ],
            temperature=0.2,
            max_tokens=80,
        )
        tags = str(tags).strip() if tags else ""
        
        # Clean up tags (remove any extra whitespace, quotes, etc.)
        tags = re.sub(r'["\']', '', tags)  # Remove quotes
        tags = re.sub(r'\s*;\s*', ';', tags)  # Normalize semicolon spacing
        
        return tags.strip()
        
    except Exception as e:
        print(f"Error generating tags: {e}")
        return ""  # Return empty string if tag generation fails

class PaperRecommender:
    def __init__(self, json_paths: List[str], openrouter_key: str):
        """Initialize the paper recommender system."""
        self.json_paths = json_paths
        self.papers = self._load_papers()
        self.openrouter_key = openrouter_key
        print(f"Loaded {len(self.papers)} papers into the system")

    def _load_papers(self) -> List[Dict[str, Any]]:
        """Load papers from JSON files."""
        all_papers = []
        conference_mappings = {
            'iclr': 'ICLR',
            'nips': 'NeurIPS',
            'neurips': 'NeurIPS',
            'icml': 'ICML'
        }
        
        for json_path in self.json_paths:
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    papers = []
                    
                    # Extract papers from the data structure
                    if isinstance(data, dict):
                        papers = data.get("papers", [])
                        if not papers:
                            for value in data.values():
                                if isinstance(value, list) and len(value) > 0:
                                    papers = value
                                    break
                    elif isinstance(data, list):
                        papers = data
                    
                    # Get conference info from filename - FIXED HERE
                    filename = os.path.basename(json_path)
                    # Remove .json extension and only take alphabetic chars up to first digit
                    conf = re.match(r'([a-zA-Z]+)', filename).group(1).lower()
                    year = ''.join(c for c in filename if c.isdigit())
                    
                    # Process each paper
                    for paper in papers:
                        if paper.get("status", "").lower() in ["reject", "withdraw"]:
                            continue
                        
                        conference = conference_mappings.get(conf, conf.upper())
                        paper_id = paper.get("id", "unknown")
                        
                        # Add paper with enhanced information
                        all_papers.append({
                            **paper,
                            "conference": conference,
                            "year": year,
                            "paper_id": f"{conference}{year}_{paper_id}"
                        })
                    
            except Exception as e:
                print(f"Error loading papers from {json_path}: {e}")
                
        return all_papers

    def get_author_info(self, author_id: str) -> Dict[str, Any]:
        """Get detailed information about an author from OpenReview."""
        try:
            url = f"https://openreview.net/profile?id={author_id}"
            
            # Try direct access first
            try:
                response = requests.get(url, timeout=10)
                html_content = response.text
            except:
                # Fallback to CrawlBase if direct access fails
                api = CrawlingAPI({'token': os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""})
                response = api.get(url)
                html_content = response.get('body', '')
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract Google Scholar ID
            scholar_id = None
            scholar_links = soup.find_all('a', href=lambda x: x and 'scholar.google' in x.lower())
            for link in scholar_links:
                match = re.search(r'user=([^&"\s]+)', link['href'])
                if match:
                    scholar_id = match.group(1)
                    break
            
            # Extract position and affiliation
            position = None
            affiliation = None
            title_container = soup.find('div', class_='title-container')
            if title_container:
                for h3 in title_container.find_all('h3'):
                    text = h3.get_text().strip()
                    if any(pos in text.lower() for pos in ['student', 'professor', 'researcher']):
                        position = text
                    else:
                        affiliation = text
            
            return {
                'scholar_id': scholar_id,
                'position': position,
                'affiliation': affiliation
            }
            
        except Exception as e:
            print(f"Error fetching author info: {e}")
            return {'scholar_id': None, 'position': None, 'affiliation': None}

    def recommend_random_papers(self, num_papers: int = 6, only_first_author: bool = True) -> List[Dict[str, Any]]:
        """Randomly select papers and return first author information."""
        if not self.papers:
            return []
        
        # Randomly select papers
        selected_papers = random.sample(self.papers, min(num_papers, len(self.papers)))

        recommendations = []
        
        for paper in selected_papers:
            try:
                # Get first author information
                authors = paper.get('author', [])
                author_ids = paper.get('authorids', [])
                status = paper.get('status', '')

                if only_first_author:
                # Handle different author formats
                    if isinstance(authors, str):
                        random_author = authors.split(';')[0].strip()
                        random_author_id = author_ids.split(';')[0].strip() if isinstance(author_ids, str) else None
                    elif isinstance(authors, list):
                        random_author = authors[0] if authors else None
                        random_author_id = author_ids[0] if isinstance(author_ids, list) and author_ids else None
                else:
                    if isinstance(authors, str):
                        random_index = random.randint(0, len(authors.split(';')) - 1)
                        random_author = authors.split(';')[random_index].strip()
                        random_author_id = author_ids.split(';')[random_index].strip() if isinstance(author_ids, str) else None
                    elif isinstance(authors, list):
                        random_index = random.randint(0, len(authors) - 1)
                        random_author = authors[random_index] if authors else None
                        random_author_id = author_ids[random_index] if isinstance(author_ids, list) and author_ids else None

                if not random_author or not random_author_id:
                    continue
            
                # Generate paper URL
                conf = paper.get('conference', '').upper()
                year = paper.get('year', '')
                paper_url = paper.get('site', 'URL are not available')

                # Get author details
                author_details = self.get_author_info(random_author_id) if random_author_id.startswith('~') else {}
                
                # Generate tags
                tags = tag_generation(paper['title'], [random_author], self.openrouter_key)
                
                recommendation = {
                    'author': {
                        'name': random_author,
                        'author_id': random_author_id,
                        'scholar_id': author_details.get('scholar_id'),
                        'position': author_details.get('position'),
                        'affiliation': author_details.get('affiliation'),
                        'tags': tags
                    },
                    'paper': {
                        'title': paper['title'],
                        'conference': conf,
                        'status': status,
                        'year': year,
                        'url': paper_url
                    }
                }
                
                recommendations.append(recommendation)
                
            except Exception as e:
                print(f"Error processing paper: {e}")
                continue
    
        return recommendations

def main():
    # Configure paths and API key
    json_paths = [
        "iclr/iclr2025.json",
        "nips/nips2024.json",
        "icml/icml2024.json"
    ]
    
    openrouter_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_KEY") or ""
    
    # Initialize recommender
    recommender = PaperRecommender(json_paths, openrouter_key)
    
    # Get recommendations
    recommendations = recommender.recommend_random_papers(6)
    
    # Display recommendations
    print("\n=== Random Paper Recommendations ===\n")
    for i, rec in enumerate(recommendations, 1):
        print(f"Recommendation #{i}")
        print("Author Information:")
        print(f"  Name: {rec['author']['name']}")
        print(f"  OpenReview: https://openreview.net/profile?id={rec['author']['author_id']}")
        if rec['author']['scholar_id']:
            print(f"  Google Scholar: https://scholar.google.com/citations?user={rec['author']['scholar_id']}")
        if rec['author']['position'] or rec['author']['affiliation']:
            print(f"  Current: {rec['author']['position'] or ''}")
        print(f"  Research Tags: {rec['author']['tags']}")
        
        print("\nPaper Information:")
        print(f"  Title: {rec['paper']['title']}")
        print(f"  Status: {rec['paper']['status']}")
        print(f"  Venue: {rec['paper']['conference']} {rec['paper']['year']}")
        print(f"  URL: {rec['paper']['url']}")
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    main()
