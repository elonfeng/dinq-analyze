import requests
from bs4 import BeautifulSoup
import re
import unicodedata

def clean_author_name(name):
    """Clean and validate an author name."""
    if not name:
        return None

    # 过滤掉 "..." 这样的占位符
    if name == "..." or name.strip() == "":
        return None

    # 过滤掉包含 "et al" 的名字
    if "et al" in name.lower():
        return None

    # Normalize unicode characters
    name = unicodedata.normalize('NFKC', name)

    # Remove special characters except letters, spaces, dots and hyphens
    name = re.sub(r'[^a-zA-Z\s.\-]', '', name)

    # Remove extra whitespace
    name = ' '.join(name.split())

    # Validate the name:
    # - Must contain at least one letter
    # - Must be between 2 and 50 characters
    # - Must not be just numbers or special characters
    if not re.search(r'[a-zA-Z]', name) or len(name) < 2 or len(name) > 50:
        return None

    return name.strip()

def filter_full_names(authors_list):
    """
    Filter out partial names and keep only full names.

    Args:
        authors_list (list): List of author names

    Returns:
        list: List containing only full names
    """
    if not authors_list:
        return []

    # Create a set of all individual words from names
    all_words = set()
    for name in authors_list:
        all_words.update(name.split())

    # Filter names that contain at least two parts and aren't substrings of other names
    full_names = []
    for name in authors_list:
        name_parts = name.split()
        # Check if name has at least two parts
        if len(name_parts) >= 2:
            # Check if this name is not a subset of any other name
            is_subset = False
            for other_name in authors_list:
                if name != other_name and name in other_name:
                    is_subset = True
                    break
            if not is_subset:
                full_names.append(name)

    return sorted(full_names)

def find_authors_from_title(paper_title):
    """
    Find authors of an academic paper using its title.
    Returns a clean, deduplicated list of author names.
    """
    # 检查输入
    if not paper_title or len(paper_title.strip()) < 5:
        print(f"Paper title is too short or empty: '{paper_title}'")
        return []

    try:
        from googlesearch import search
    except ImportError:
        print("Error: The 'googlesearch-python' library is not installed.")
        print("Please install it using: pip install googlesearch-python")
        return []

    potential_authors = set()

    try:
        # First try arXiv specific search
        arxiv_query = f"{paper_title} site:arxiv.org"
        # arxiv_results = search(arxiv_query, num_results=2)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        arxiv_results = list(search(arxiv_query, num_results=2))
        for url in arxiv_results:
            if 'arxiv.org' in url:
                try:
                    response = requests.get(url, timeout=10, headers=headers)
                    response.encoding = response.apparent_encoding
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # ArXiv specific author extraction
                    authors_div = soup.find('div', class_='authors')
                    if authors_div:
                        author_links = authors_div.find_all('a')
                        for author_link in author_links:
                            clean_name = clean_author_name(author_link.text)
                            if clean_name:
                                potential_authors.add(clean_name)

                except Exception as e:
                    continue

        # If no authors found from arXiv, try Google Scholar
        if not potential_authors:
            scholar_query = f"{paper_title} site:scholar.google.com"
            scholar_results = search(scholar_query, num_results=2)

            for url in scholar_results:
                try:
                    response = requests.get(url, timeout=10, headers=headers)
                    response.encoding = response.apparent_encoding
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Look for meta tags
                    meta_authors = soup.find_all('meta', attrs={'name': ['author', 'citation_author']})
                    for meta in meta_authors:
                        content = meta.get('content', '')
                        if content:
                            for author in re.split(r'[,;]|\band\b', content):
                                clean_name = clean_author_name(author)
                                if clean_name:
                                    potential_authors.add(clean_name)

                    # Look for author divs
                    author_divs = soup.find_all(['div', 'span'],
                                              class_=lambda x: x and any(term in x.lower()
                                                                       for term in ['author', 'contrib']))
                    for div in author_divs:
                        text = div.get_text()
                        for author in re.split(r'[,;]|\band\b', text):
                            clean_name = clean_author_name(author)
                            if clean_name:
                                potential_authors.add(clean_name)

                except Exception as e:
                    continue

        # Filter out noise and clean the list
        filtered_authors = []
        for author in potential_authors:
            if (author and
                len(author.split()) >= 1 and
                not any(char.isdigit() for char in author) and
                not any(word.lower() in author.lower()
                       for word in ['author', 'copyright', 'university', 'institute',
                                  'correspondence', 'submitted', 'received']) and
                not author.isupper()):
                filtered_authors.append(author)

        # Remove duplicates and get full names
        unique_authors = sorted(list(set(filtered_authors)))
        full_names = filter_full_names(unique_authors)

        # 最后一次过滤，确保没有 "..." 这样的占位符
        if full_names:
            full_names = [name for name in full_names if name != "..." and name.strip() != "" and "et al" not in name.lower()]

        return full_names if full_names else []

    except Exception as e:
        print(f"An error occurred in find_authors_from_title: {e}")
        return []


def find_authors_from_title_new(paper_title):
    """用 OpenAlex，没有限流问题"""
    try:
        url = "https://api.openalex.org/works"
        params = {
            'filter': f'title.search:{paper_title}',
            'per-page': 1
        }

        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()
            if data.get('results'):
                work = data['results'][0]
                authors = [a['author']['display_name']
                           for a in work.get('authorships', [])]
                return authors

        return []
    except Exception as e:
        print(f"OpenAlex failed: {e}")
        return []

if __name__ == "__main__":
    paper_title = "Multi-view consistent generative adversarial networks for 3d-aware image synthesis"
    authors = find_authors_from_title_new(paper_title)

    if authors:
        print(authors)
    else:
        print(f"Could not find author information for '{paper_title}'.")