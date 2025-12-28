import json
import os
from typing import List, Dict, Any, Optional, Union, Tuple
import time
import requests
from pathlib import Path
import re
from bs4 import BeautifulSoup
from crawlbase import CrawlingAPI
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import torch
import faiss
import random
from firecrawl import FirecrawlApp
from server.llm.gateway import openrouter_chat

def tag_generation(title: str, authors: List[str], openrouter_key: str) -> str:
    """Generate research area tags for a paper."""
    # Define valid tags
    VALID_TAGS = {
        'CV', 'NLP', 'LLM', 'RAG', 'ML', 'RL', '3D', 'GAN', 
        'Agent', 'Vision', 'Audio', 'Graph', 'XAI', 'HCI', 
        'Robotics', 'Security'
    }
    
    # Create a prompt for tag generation
    system_prompt = """You are a research paper tag generator. Given a paper title and authors, generate relevant research area tags.
        Focus on high-level research areas and trending AI topics from ONLY these options:
        CV, NLP, LLM, RAG, ML, RL, 3D, GAN, Agent, Vision, Audio, Graph, XAI, HCI, Robotics, Security

        Rules:
        1. Return EXACTLY 3 tags from the options above
        2. Each tag MUST be a single word/abbreviation from the provided options
        3. Tags MUST be separated by semicolons
        4. Return ONLY the tags, no other text or URLs
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
        
        # Clean up tags
        tags = re.sub(r'["\']', '', tags)  # Remove quotes
        tags = re.sub(r'\s*;\s*', ';', tags)  # Normalize semicolon spacing
        tags = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', tags)  # Remove URLs
        
        # Split and validate tags
        tag_list = [tag.strip() for tag in tags.split(';') if tag.strip()]
        valid_tag_list = [tag for tag in tag_list if tag in VALID_TAGS]
        
        # Ensure exactly 3 tags, using default tags if necessary
        while len(valid_tag_list) < 3:
            if 'ML' not in valid_tag_list:
                valid_tag_list.append('ML')
            elif 'NLP' not in valid_tag_list:
                valid_tag_list.append('NLP')
            elif 'CV' not in valid_tag_list:
                valid_tag_list.append('CV')
            else:
                break
        
        # Take only first 3 tags
        valid_tag_list = valid_tag_list[:3]
        
        return ';'.join(valid_tag_list)
        
    except Exception as e:
        print(f"Error generating tags: {e}")
        return "AI;ML;DL"  # Return default tags if generation fails

class SemanticSearchEngine:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize with a sentence transformer model for embeddings."""
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.papers = None
        self.embeddings = None
        
        # Define research intents for zero-shot classification
        self.research_intents = [
            "This is a methodology paper focusing on new techniques or approaches",
            "This is a survey or review paper summarizing existing work",
            "This is an application paper demonstrating practical use",
            "This is a theoretical paper analyzing fundamental concepts",
            "This is an empirical study comparing different methods"
        ]
        # Cache the intent embeddings
        self.intent_embeddings = self.model.encode(self.research_intents, convert_to_tensor=True)

    def build_index(self, papers: List[Dict[str, Any]]):
        """Build FAISS index for fast similarity search."""
        self.papers = papers
        
        # Prepare texts for embedding
        texts = [
            f"{p['title']} {p.get('abstract', '')}" for p in papers
        ]
        
        # Generate embeddings
        print("Generating paper embeddings...")
        self.embeddings = self.model.encode(texts, convert_to_tensor=True)
        
        # Convert PyTorch tensor to numpy array
        embeddings_numpy = self.embeddings.cpu().numpy()
        
        # Build FAISS index
        dimension = embeddings_numpy.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # Inner product index
        self.index.add(embeddings_numpy)
        print(f"Built search index with {len(papers)} papers")

    def analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """Analyze query intent using zero-shot classification with embeddings."""
        # Encode query
        query_embedding = self.model.encode(query, convert_to_tensor=True)
        
        # Calculate similarity with intent embeddings
        similarities = cosine_similarity(
            query_embedding.reshape(1, -1),
            self.intent_embeddings.cpu().numpy()
        )[0]
        
        # Get top intent
        top_intent_idx = np.argmax(similarities)
        intent_score = similarities[top_intent_idx]
        
        return {
            'intent': self.research_intents[top_intent_idx],
            'score': float(intent_score),
            'embedding': query_embedding
        }

    def search(self, query: str, k: int = 100) -> List[Tuple[int, float]]:
        """Perform semantic search using query embedding."""
        # Analyze query intent
        query_analysis = self.analyze_query_intent(query)
        query_embedding = query_analysis['embedding']
        
        # Convert PyTorch tensor to numpy array
        query_embedding_numpy = query_embedding.cpu().numpy()
        
        # Perform FAISS search
        scores, indices = self.index.search(
            query_embedding_numpy.reshape(1, -1), 
            k
        )
        
        # Combine with papers
        results = []
        for idx, score in zip(indices[0], scores[0]):
            if idx < len(self.papers):  # Safety check
                results.append((idx, float(score)))
        
        return results, query_analysis

class AIConferenceAnalyzer:
    def __init__(self, json_paths: Union[str, List[str]], openrouter_key: str):
        """Initialize the conference analyzer with semantic search capabilities."""
        self.json_paths = [json_paths] if isinstance(json_paths, str) else json_paths
        self.papers = self._load_papers()
        self.openrouter_key = openrouter_key
        self.headers = {}
        
        # Initialize semantic search engine
        print("Initializing semantic search engine...")
        self.search_engine = SemanticSearchEngine()
        self.search_engine.build_index(self.papers)
        
        print(f"Loaded {len(self.papers)} papers into the system")

    def _load_papers(self) -> List[Dict[str, Any]]:
        """Load and merge papers from multiple JSON files."""
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
                    conf_info = None
                    
                    # Get papers and conference info from data structure
                    if isinstance(data, dict):
                        conf_info = data.get("venue") or data.get("conference")
                        papers = data.get("papers", [])
                        if not papers:
                            # Find first list that looks like papers
                            for key, value in data.items():
                                if isinstance(value, list) and len(value) > 0:
                                    papers = value
                                    if not conf_info:
                                        conf_info = key
                                    break
                    elif isinstance(data, list):
                        papers = data
                    
                    # Fallback to filename for conference/year
                    filename = Path(json_path).stem.lower()
                    file_conf = ''.join(c for c in filename if c.isalpha())
                    file_year = ''.join(c for c in filename if c.isdigit())
                    
                    filtered_papers = []
                    for paper in papers:
                        if paper.get("status", "").lower() in ["reject", "withdraw"]:
                            continue
                        
                        # Get conference from paper or fallbacks
                        conference = (paper.get("conference") or 
                                   paper.get("venue") or 
                                   conf_info or 
                                   conference_mappings.get(file_conf, file_conf.upper()))
                        
                        # Get year from paper or fallback
                        year = str(paper.get("year") or 
                                 paper.get("conference_year") or 
                                 file_year)
                        
                        paper_id = paper.get("id", "unknown")
                        enhanced_paper = {
                            **paper,
                            "source_file": json_path,
                            "conference": conference.upper(),
                            "year": year,
                            "paper_id": f"{conference.upper()}{year}_{paper_id}"
                        }
                        filtered_papers.append(enhanced_paper)
                    
                    all_papers.extend(filtered_papers)
                    if filtered_papers:
                        conf = filtered_papers[0]["conference"]
                        year = filtered_papers[0]["year"]
                        print(f"Loaded {len(filtered_papers)} papers from {conf} {year}")
                    
            except Exception as e:
                print(f"Error loading papers from {json_path}: {e}")
        return all_papers

    def _fast_prefilter(self, query: str, papers: List[Dict[str, Any]], target_size: int = 200) -> List[Dict[str, Any]]:
        """Enhanced semantic prefiltering."""
        # Perform semantic search
        results, query_analysis = self.search_engine.search(query, k=target_size)
        
        # Get filtered papers with scores
        filtered_papers = []
        seen_titles = set()
        
        for idx, score in results:
            paper = papers[idx]
            if paper['title'] not in seen_titles:
                seen_titles.add(paper['title'])
                
                # Add semantic score to paper
                paper['semantic_score'] = score
                paper['query_intent'] = query_analysis['intent']
                filtered_papers.append(paper)
        
        return filtered_papers

    def _prefilter_papers_with_llm(self, query: str, papers: List[Dict[str, Any]], max_candidates: int = 100) -> List[Dict[str, Any]]:
        """Second-stage filtering using LLM and keyword matching to identify most relevant papers."""
        # First do keyword matching
        query_terms = set(query.lower().split())
        # Add common variations
        expanded_terms = set()
        for term in query_terms:
            expanded_terms.add(term)
            # Add common variations
            if term.endswith('s'):
                expanded_terms.add(term[:-1])  # singular
            if term.endswith('ing'):
                expanded_terms.add(term[:-3])  # root form
                expanded_terms.add(term[:-3] + 'e')  # e.g., make from making
            if term.endswith('ed'):
                expanded_terms.add(term[:-2])  # root form
                expanded_terms.add(term[:-1])  # e.g., used -> use
        
        # Score papers based on keyword matches
        scored_papers = []
        for paper in papers:
            score = 0
            title = paper.get('title', '').lower()
            abstract = paper.get('abstract', '').lower()
            keywords = [k.lower() for k in paper.get('keywords', [])]
            
            # Title matches (weighted heavily)
            for term in expanded_terms:
                if term in title:
                    score += 5  # Higher weight for title matches
                if term in abstract:
                    score += 2  # Medium weight for abstract matches
                if any(term in k for k in keywords):
                    score += 3  # Good weight for keyword matches
            
            if score > 0:
                # Add keyword score to paper
                paper['keyword_score'] = score
                scored_papers.append(paper)
        
        # Sort by combined score (keyword + semantic) and take top papers
        scored_papers.sort(key=lambda x: (x.get('keyword_score', 0) + x.get('relevance_score', 0)), reverse=True)
        filtered_papers = scored_papers[:max_candidates]
        
        print(f"Found {len(filtered_papers)} relevant papers")
        return filtered_papers

    def search_papers(self, query: str, exclude_ethnicities: List[str] = None, max_results: int = 5) -> List[Dict[str, Any]]:
        """Enhanced semantic search with intent recognition."""
        try:
            # Perform semantic search with intent analysis
            initial_papers = self._fast_prefilter(query, self.papers, target_size=200)
            if not initial_papers:
                print("No relevant papers found in initial filtering")
                return []
            
            # Get query intent analysis
            _, query_analysis = self.search_engine.search(query, k=1)
            print(f"Detected intent: {query_analysis['intent']}")
            print(f"Intent confidence: {query_analysis['score']:.2f}")
            
            # Prepare for LLM analysis with semantic scores
            relevant_papers = []
            for paper in initial_papers[:100]:  # Take top 100 for LLM analysis
                paper_with_score = {
                    **paper,
                    'relevance_score': int(paper['semantic_score'] * 100)
                }
                relevant_papers.append(paper_with_score)
            
            # Apply keyword and LLM filtering
            filtered_papers = self._prefilter_papers_with_llm(query, relevant_papers, max_candidates=max_results)
            
            # Sort by relevance score
            filtered_papers.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
            
            # Return top results
            return filtered_papers[:max_results]

        except Exception as e:
            print(f"Error during paper search: {e}")
            return []

    def _get_researcher_details(self, researcher_info: str) -> Dict[str, Any]:
        """Get detailed information about a researcher including photo and background."""
        try:
            content = openrouter_chat(
                task="recommend.researcher_detail",
                model="perplexity/sonar-pro:online",
                messages=[
                    {
                        "role": "user",
                        "content": f"Please provide the photo URL, graduate school, current company/institution, and a one-sentence description in JSON format for this researcher: {researcher_info}",
                    }
                ],
                temperature=0.2,
                max_tokens=600,
            )
            content = str(content) if content else ""
            
            try:
                # Extract and parse JSON
                json_str = re.search(r'({[\s\S]*})', content).group(1)
                details = json.loads(json_str)
                return {
                    'photo_url': details.get('photo'),
                    'education': details.get('graduate_school'),
                    'institution': details.get('company'),
                    'bio': details.get('description')
                }
            except:
                return {}

        except Exception as e:
            print(f"Error getting researcher details: {e}")
            return {}

    def _extract_authors_data(self) -> Dict[str, Any]:
        """Extract author information from paper data."""
        authors_data = {}
        
        for paper in self.papers:
            authors = paper.get("authors", [])
            for author in authors:
                author_id = author.get("id")
                if not author_id:
                    continue
                    
                if author_id not in authors_data:
                    authors_data[author_id] = {
                        "name": author.get("name", "Unknown"),
                        "papers": [],
                        "affiliations": set(),
                        "keywords": set()
                    }
                
                # Add paper information
                authors_data[author_id]["papers"].append({
                    "title": paper.get("title"),
                    "year": paper.get("year"),
                    "conference": paper.get("conference"),
                    "keywords": paper.get("keywords", [])
                })
                
                # Add affiliation
                if "aff" in author:
                    authors_data[author_id]["affiliations"].add(author["aff"])
                
                # Add keywords
                if "keywords" in paper:
                    authors_data[author_id]["keywords"].update(paper["keywords"])
        
        # Convert sets to lists for JSON serialization
        for author_data in authors_data.values():
            author_data["affiliations"] = list(author_data["affiliations"])
            author_data["keywords"] = list(author_data["keywords"])
        
        return authors_data

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response and handle various JSON formats."""
        try:
            # Remove any markdown formatting and clean the response
            response = re.sub(r'```(?:json)?\s*|\s*```', '', response.strip())
            
            # Find the JSON structure
            json_match = re.search(r'(\{[\s\S]*\})', response)
            if not json_match:
                print(f"No JSON-like structure found in response")
                return {"papers": []}
            
            json_str = json_match.group(1)
            
            # Clean the JSON string
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)  # Remove trailing commas
            json_str = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_str)  # Quote unquoted keys
            json_str = json_str.replace("'", '"')  # Replace single quotes with double quotes
            json_str = re.sub(r'\s+', ' ', json_str)  # Normalize whitespace
            json_str = re.sub(r':\s*([\d.]+)\s*([,}])', r': "\1"\2', json_str)  # Quote numeric values
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"Initial JSON parsing failed: {str(e)}")
                
                # More aggressive cleaning
                json_str = re.sub(r'//.*?\n|/\*.*?\*/', '', json_str)  # Remove comments
                json_str = re.sub(r'"\s*\+\s*"', '', json_str)  # Remove string concatenation
                json_str = re.sub(r'undefined', 'null', json_str)  # Replace undefined with null
                json_str = re.sub(r':\s*([^"{}\[\],\s]+)\s*([,}])', r': "\1"\2', json_str)  # Quote unquoted values
                
                # Handle arrays that should be strings
                def fix_array_to_string(match):
                    items = re.findall(r'"([^"]+)"', match.group(1))
                    return f'"{";".join(items)}"'
                
                json_str = re.sub(r'"authors"\s*:\s*\[(.*?)\]', lambda m: f'"authors": {fix_array_to_string(m)}', json_str)
                json_str = re.sub(r'"authorids"\s*:\s*\[(.*?)\]', lambda m: f'"authorids": {fix_array_to_string(m)}', json_str)
                
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    print(f"Failed to parse JSON after cleaning: {str(e)}")
                    print(f"Problematic JSON: {json_str}")
                    return {"papers": []}
                    
        except Exception as e:
            print(f"Error in _parse_llm_response: {str(e)}")
            return {"papers": []}

    @staticmethod
    def get_scholar_id(openreview_id: str) -> Dict[str, str]:
        """
        Extract Google Scholar ID and detailed author information from an OpenReview profile.
        Uses CrawlBase API to bypass anti-crawling measures.
        
        Args:
            openreview_id: The OpenReview ID (e.g., '~First_Last1')
            
        Returns:
            Dict with scholar_id, position, affiliation, and other author info
        """
        try:
            # First try direct OpenReview access
            url = f"https://openreview.net/profile?id={openreview_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
            }
            
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                html_content = response.text
            except:
                # If direct access fails, try using CrawlBase API
                # crawling_api = CrawlingAPI({'token': os.getenv("CRAWLBASE_API_TOKEN") or os.getenv("CRAWLBASE_TOKEN") or ""})
                # response = crawling_api.get(url)
                # if response and isinstance(response, dict):
                #     html_content = response.get('body', '')
                #     if not html_content:
                #         raise Exception("No HTML content returned from CrawlBase API")
                # else:
                #     raise Exception("Invalid response from CrawlBase API")                
                firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY", "")
                if not firecrawl_api_key:
                    raise Exception("Direct OpenReview access failed and FIRECRAWL_API_KEY not set")
                firecrawl_app = FirecrawlApp(api_key=firecrawl_api_key)
                response = firecrawl_app.scrape_url(
                    url,
                    formats=["html"],
                    onlyMainContent=False,
                )
                html_content = response.html if response else ""
                

            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Initialize author info
            author_info = {
                'scholar_id': None,
                'position': None,
                'affiliation': None,
                'homepage': None,
                'email': None
            }
            
            # Extract Google Scholar ID
            scholar_links = soup.find_all('a', href=lambda x: x and 'scholar.google' in x.lower())
            for link in scholar_links:
                href = link['href']
                match = re.search(r'user=([^&"\s]+)', href)
                if match:
                    author_info['scholar_id'] = match.group(1)
                    break
            
            # Extract homepage
            homepage_links = soup.find_all('a', href=lambda x: x and any(term in x.lower() for term in ['homepage', 'website', 'personal']))
            if homepage_links:
                author_info['homepage'] = homepage_links[0]['href']
            
            # Extract email
            email_links = soup.find_all('a', href=lambda x: x and 'mailto:' in x.lower())
            if email_links:
                author_info['email'] = email_links[0]['href'].replace('mailto:', '')
            
            # Extract position and affiliation from title-container
            title_container = soup.find('div', class_='title-container')
            if title_container:
                # Find all h3 tags in title-container
                h3_tags = title_container.find_all('h3')
                
                positions = []
                affiliations = []
                
                # Process each h3 tag
                for h3 in h3_tags:
                    text = h3.get_text().strip()
                    if ',' in text:
                        # Split by comma if present
                        parts = [part.strip() for part in text.split(',')]
                        gagaga = None
                        for part in parts:
                            # Check for position keywords in each part
                            if any(pos in part.lower() for pos in ['student', 'professor', 'researcher', 'intern', 'fellow', 'scientist', 'engineer', 'phd', 'master', 'postdoc']):
                                gagaga = part
                                positions.append(part)
                                continue
                            # Check for affiliation keywords in each part
                            if gagaga is not None:
                                affiliations.append(part)
                    else:
                        # Single part - check for keywords
                        if any(pos in text.lower() for pos in ['student', 'professor', 'researcher', 'intern', 'fellow', 'scientist', 'engineer', 'phd', 'master', 'postdoc']):
                            positions.append(text)
                            continue
                        affiliations.append(text)
                
                # Select the most relevant position (prioritize PhD student, Professor, etc.)
                if positions:
                    # Priority order for positions
                    for pos_type in ['phd student', 'professor', 'postdoc', 'researcher', 'student']:
                        matching_positions = [pos for pos in positions if pos_type in pos.lower()]
                        if matching_positions:
                            author_info['position'] = matching_positions[0]
                            break
                    if not author_info['position']:  # If no priority match found, use the first position
                        author_info['position'] = positions[0]
                
                # Select the most relevant affiliation (prioritize universities over companies)
                if affiliations:
                    # Priority order for affiliations
                    for aff_type in ['university', 'institute', 'college', 'school']:
                        matching_affs = [aff for aff in affiliations if aff_type in aff.lower()]
                        if matching_affs:
                            author_info['affiliation'] = matching_affs[0]
                            break
                    if not author_info['affiliation']:  # If no priority match found, use the first affiliation
                        author_info['affiliation'] = affiliations[0]
            
            # If not found in title-container, try other methods
            if not author_info['position'] or not author_info['affiliation']:
                main_content = soup.find('div', {'id': 'content'}) or soup.find('main')
                if main_content:
                    text_blocks = main_content.find_all(['p', 'div', 'section'])
                    for block in text_blocks:
                        text = block.get_text()
                        # Look for position if not found yet
                        if not author_info['position']:
                            position_match = re.search(r'(?:Position|Role|Title):\s*([^,\n]+)', text, re.I)
                            if position_match:
                                author_info['position'] = position_match.group(1)
                        
                        # Look for affiliation if not found yet
                        if not author_info['affiliation']:
                            aff_match = re.search(r'(?:Affiliation|Institution|Organization|Department):\s*([^,\n]+)', text, re.I)
                            if aff_match:
                                author_info['affiliation'] = aff_match.group(1)
            
            # Clean up extracted information
            for key in author_info:
                if author_info[key]:
                    # Remove extra whitespace and normalize
                    author_info[key] = re.sub(r'\s+', ' ', author_info[key]).strip()
                    # Remove common prefixes
                    author_info[key] = re.sub(r'^(?:Position|Role|Title|Affiliation|Institution|Organization|Department):\s*', '', author_info[key], flags=re.I)
                    # Remove any remaining newlines
                    author_info[key] = author_info[key].replace('\n', ' ').strip()
            
            return author_info
            
        except Exception as e:
            print(f"Error fetching author info for {openreview_id}: {e}")
            return {
                'scholar_id': None,
                'position': None,
                'affiliation': None,
                'homepage': None,
                'email': None
            }

def display_papers(papers: List[Dict[str, Any]], openrouter_key: str, only_first_author: bool = False) -> List[Dict[str, Any]]:
    """
    Process paper information and return a list of formatted paper details.
    
    Args:
        papers: List of paper dictionaries containing paper information
        openrouter_key: OpenRouter API key for tag generation
        only_first_author: If True, return first author; if False, return a random author
    
    Returns:
        List of dictionaries containing formatted paper information
    """
    # Add validation
    if not papers:
        print("No papers provided to display_papers")
        return []
        
    paper_results = []
    seen_titles = set()
    
    for paper in papers:
        try:
            # Skip papers with invalid conference
            conf = paper.get('conference', '')
            if not conf or conf == 'None' or 'None' in conf:
                continue

            # Skip duplicate titles
            title = paper.get('title', '').strip()
            if title in seen_titles:
                continue
            seen_titles.add(title)

            # Generate paper URL based on conference
            conf = conf.upper()
            year = paper.get('year', '')
            paper_id = paper.get('id', '')
            paper_url = paper.get('site', 'URL not available')

            if paper_url == 'URL not available':
                continue

            # Handle different possible author formats
            authors = paper.get('authors') or paper.get('author') or []
            author_ids = paper.get('authorids', [])
            
            if isinstance(authors, str):
                author_list = [author.strip() for author in authors.split(';') if author.strip()]
            elif isinstance(authors, list):
                if all(isinstance(a, str) for a in authors):
                    author_list = [a.strip() for a in authors if a.strip()]
                else:
                    author_text = ''.join(str(a) for a in authors)
                    author_list = [a.strip() for a in author_text.split(';') if a.strip()]
            else:
                author_list = []
                
            # Handle author IDs
            if isinstance(author_ids, str):
                id_list = [aid.strip() for aid in author_ids.split(';') if aid.strip()]
            elif isinstance(author_ids, list):
                if all(isinstance(aid, str) for aid in author_ids):
                    id_list = [aid.strip() for aid in author_ids if aid.strip()]
                else:
                    id_text = ''.join(str(aid) for aid in author_ids)
                    id_list = [aid.strip() for a in id_text.split(';') if aid.strip()]
            else:
                id_list = []

            # Select which authors to process based on only_first_author flag
            if only_first_author:
                if author_list and id_list:
                    author_list = [author_list[0]]
                    id_list = [id_list[0]]
            else:
                # Select a random author if there are multiple authors
                if len(author_list) > 0 and len(id_list) > 0:
                    random_idx = random.randint(0, len(author_list) - 1)
                    author_list = [author_list[random_idx]]
                    id_list = [id_list[random_idx]]

            # Process selected author(s)
            author_info_list = []
            for idx, (author, author_id) in enumerate(zip(author_list, id_list)):
                openreview_url = f"https://openreview.net/profile?id={author_id}"
                tags = tag_generation(paper['title'], [author], openrouter_key)
                author_details = AIConferenceAnalyzer.get_scholar_id(author_id)
                
                author_info = {
                    'name': author,
                    'author_id': author_id,
                    'openreview_url': openreview_url,
                    'tags': tags,
                    'position': author_details.get('position'),
                    'affiliation': author_details.get('affiliation'),
                    'scholar_id': author_details.get('scholar_id'),
                    'homepage': author_details.get('homepage')
                }

                if author_details.get('scholar_id') is None:
                    continue
                    
                author_info_list.append(author_info)
            # Compile paper information
            paper_info = {
                'title': paper['title'],
                'venue': f"{conf} {paper.get('year', 'Unknown')}",
                'url': paper_url,
                'authors': author_info_list,
                'relevance_score': paper.get('relevance_score', 'N/A'),
                'relevance_explanation': paper.get('why_relevant', '')
            }
            
            paper_results.append(paper_info)
                
        except Exception as e:
            print(f"Error processing paper: {str(e)}")
            continue
    
    return paper_results

def main():
    # Example usage
    json_paths = [
        "iclr/iclr2025.json",
        "nips/nips2024.json",
        "icml/icml2024.json"
    ]
    
    # Get API key from environment
    openrouter_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_KEY") or ""
    
    # Initialize analyzer
    analyzer = AIConferenceAnalyzer(json_paths, openrouter_key)
    
    # Paper search example
    papers = analyzer.search_papers(
        query="Agent",
        exclude_ethnicities=[],
        max_results=5
    )
    
    # Check if papers is None or empty
    if not papers:
        print("No papers found matching the search criteria")
        return
    
    # Get the paper results
    # paper_results = display_papers(papers, openrouter_key, only_first_author=True)
    paper_results = display_papers(papers, openrouter_key, only_first_author=True)
    
    if not paper_results:
        print("No paper results to display")
        return

    # Print the results
    for paper in paper_results:
        print("\nTitle:", paper['title'])
        print("Venue:", paper['venue'])
        print("URL:", paper['url'])
        
        print("\nAuthors:")
        for author in paper['authors']:
            print(f"  Name: {author['name']}")
            print(f"  OpenReview: {author['openreview_url']}")
            print(f"  Tags: {author['tags']}")
            if author['position'] or author['affiliation']:
                position = author['position'] or ''
                affiliation = author['affiliation'] or ''
                if position and affiliation:
                    print(f"  Current: {position} at {affiliation}")
                elif position:
                    print(f"  Current: {position}")
                elif affiliation:
                    print(f"  Current: {affiliation}")
            if author['scholar_id']:
                print(f"  Google Scholar: https://scholar.google.com/citations?user={author['scholar_id']}")
            if author['homepage']:
                print(f"  Homepage: {author['homepage']}")
            print()  # Add blank line between authors
        
        print(f"Relevance Score: {paper['relevance_score']}")
        if paper['relevance_explanation']:
            print(f"Relevance: {paper['relevance_explanation']}")
        print("-" * 80)  # Add separator between papers

if __name__ == "__main__":
    main()
