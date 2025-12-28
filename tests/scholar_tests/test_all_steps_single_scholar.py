#!/usr/bin/env python
# coding: UTF-8
"""
Script to run all test steps for a single scholar.
This script processes a single scholar through all the individual steps of the scholar service.
"""

import os
import sys
import re
import json
import argparse
import time

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the necessary components
from server.services.scholar.data_fetcher import ScholarDataFetcher
from server.services.scholar.analyzer import ScholarAnalyzer
from server.services.scholar.visualizer import ScholarVisualizer
from server.utils.find_arxiv import find_arxiv
from onepage.signature_news import get_latest_news
from server.services.scholar.template_figure_kimi import get_template_figure
from account.juris_people import three_card_juris_people
from server.prompts.researcher_evaluator import generate_critical_evaluation
from server.config.api_keys import API_KEYS

def extract_scholar_id(url):
    """Extract scholar ID from Google Scholar URL."""
    match = re.search(r'user=([^&]+)', url)
    if match:
        return match.group(1)
    return None

def test_all_steps(name=None, scholar_id=None, url=None, output_dir='reports/tests/steps'):
    """Run all test steps for a single scholar."""
    # If URL is provided, extract scholar ID
    if url and not scholar_id:
        scholar_id = extract_scholar_id(url)
        if not scholar_id:
            print(f"Could not extract scholar ID from URL: {url}")
            return None

    if not name and not scholar_id:
        print("Either name or scholar_id must be provided")
        return None

    print(f"Processing scholar: {name or ''} (ID: {scholar_id or 'None'})")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Get Crawlbase API token
    api_token = API_KEYS.get('CRAWLBASE_API_TOKEN')

    # Initialize components
    data_fetcher = ScholarDataFetcher(use_crawlbase=True, api_token=api_token)
    analyzer = ScholarAnalyzer()
    visualizer = ScholarVisualizer()

    # Create base filename
    if name:
        base_name = name.replace(' ', '_').replace(',', '').replace('.', '')
    else:
        base_name = "scholar"

    if scholar_id:
        base_name = f"{base_name}_{scholar_id}"

    # Step 1: Search for the researcher
    print("\n=== Step 1: Search for the researcher ===")
    author_info = data_fetcher.search_researcher(name=name, scholar_id=scholar_id)
    if not author_info:
        print(f"Error: Could not find researcher {'ID: ' + scholar_id if scholar_id else 'Name: ' + name}")
        return None

    # Save the author info
    author_info_file = os.path.join(output_dir, f"{base_name}_step1_author_info.json")
    with open(author_info_file, 'w', encoding='utf-8') as f:
        json.dump(author_info, f, ensure_ascii=False, indent=2)

    print(f"Author info saved to {author_info_file}")

    # Step 2: Get full profile with publications
    print("\n=== Step 2: Get full profile with publications ===")
    author_data = data_fetcher.get_full_profile(author_info)
    if not author_data:
        print("Error: Could not retrieve full profile")
        return None

    # Save the author data
    author_data_file = os.path.join(output_dir, f"{base_name}_step2_author_data.json")
    with open(author_data_file, 'w', encoding='utf-8') as f:
        json.dump(author_data, f, ensure_ascii=False, indent=2)

    print(f"Author data saved to {author_data_file}")

    # Step 3: Analyze publications
    print("\n=== Step 3: Analyze publications ===")
    pub_stats = analyzer.analyze_publications(author_data)
    if not pub_stats:
        print("Error: Could not analyze publications")
        return None

    # Save the publication statistics
    pub_stats_file = os.path.join(output_dir, f"{base_name}_step3_pub_stats.json")
    with open(pub_stats_file, 'w', encoding='utf-8') as f:
        json.dump(pub_stats, f, ensure_ascii=False, indent=2)

    print(f"Publication statistics saved to {pub_stats_file}")

    # Step 4: Analyze co-authors
    print("\n=== Step 4: Analyze co-authors ===")
    coauthor_stats = analyzer.analyze_coauthors(author_data)
    if not coauthor_stats:
        print("Error: Could not analyze co-authors")
        return None

    # Save the co-author statistics
    coauthor_stats_file = os.path.join(output_dir, f"{base_name}_step4_coauthor_stats.json")
    with open(coauthor_stats_file, 'w', encoding='utf-8') as f:
        json.dump(coauthor_stats, f, ensure_ascii=False, indent=2)

    print(f"Co-author statistics saved to {coauthor_stats_file}")

    # Step 5: Generate co-author network
    print("\n=== Step 5: Generate co-author network ===")
    try:
        coauthor_network = analyzer.generate_coauthor_network(author_data)
        if not coauthor_network:
            print("Error: Could not generate co-author network")
            coauthor_network_info = {"error": "Could not generate co-author network"}
        else:
            # Convert the network to a serializable format
            coauthor_network_info = {
                "nodes": [str(node) for node in coauthor_network.nodes()],
                "edges": [(str(u), str(v)) for u, v in coauthor_network.edges()]
            }
    except Exception as e:
        print(f"Error generating co-author network: {e}")
        coauthor_network_info = {"error": str(e)}

    # Save the co-author network info
    coauthor_network_file = os.path.join(output_dir, f"{base_name}_step5_coauthor_network.json")
    with open(coauthor_network_file, 'w', encoding='utf-8') as f:
        json.dump(coauthor_network_info, f, ensure_ascii=False, indent=2)

    print(f"Co-author network info saved to {coauthor_network_file}")

    # Step 6: Calculate researcher rating
    print("\n=== Step 6: Calculate researcher rating ===")
    rating = analyzer.calculate_researcher_rating(author_data, pub_stats)
    if not rating:
        print("Error: Could not calculate researcher rating")
        return None

    # Save the researcher rating
    rating_file = os.path.join(output_dir, f"{base_name}_step6_rating.json")
    with open(rating_file, 'w', encoding='utf-8') as f:
        json.dump(rating, f, ensure_ascii=False, indent=2)

    print(f"Researcher rating saved to {rating_file}")

    # Step 7: Find most frequent collaborator details
    print("\n=== Step 7: Find most frequent collaborator details ===")
    most_frequent_collaborator = None
    if coauthor_stats and 'top_coauthors' in coauthor_stats and coauthor_stats['top_coauthors']:
        try:
            top_coauthor = coauthor_stats['top_coauthors'][0]
            coauthor_name = top_coauthor['name']
            best_paper_title = top_coauthor.get('best_paper', {}).get('title', '')

            # Search for this coauthor on Google Scholar using the best paper title to get full name
            coauthor_search_results = data_fetcher.search_author_by_name(coauthor_name, paper_title=best_paper_title)

            if coauthor_search_results:
                # Get the first result (most relevant)
                coauthor_id = coauthor_search_results[0]['scholar_id']
                coauthor_details = data_fetcher.get_author_details_by_id(coauthor_id)

                if coauthor_details:
                    most_frequent_collaborator = {
                        'full_name': coauthor_details.get('full_name', coauthor_name),
                        'affiliation': coauthor_details.get('affiliation', 'Unknown'),
                        'research_interests': coauthor_details.get('research_interests', []),
                        'scholar_id': coauthor_id,
                        'coauthored_papers': top_coauthor['coauthored_papers'],
                        'best_paper': top_coauthor['best_paper'],
                        'h_index': coauthor_details.get('h_index', 'N/A'),
                        'total_citations': coauthor_details.get('total_citations', 'N/A')
                    }
        except Exception as e:
            print(f"Error finding most frequent collaborator: {e}")
            most_frequent_collaborator = None

    # If no most frequent collaborator found, create an empty one
    if most_frequent_collaborator is None:
        print("No most frequent collaborator found or error occurred. Creating empty collaborator object.")
        most_frequent_collaborator = {
            'full_name': 'No frequent collaborator found',
            'affiliation': 'N/A',
            'research_interests': [],
            'scholar_id': '',
            'coauthored_papers': 0,
            'best_paper': {'title': 'N/A', 'year': 'N/A', 'venue': 'N/A', 'citations': 0},
            'h_index': 'N/A',
            'total_citations': 'N/A'
        }

    # Save the most frequent collaborator details
    collaborator_file = os.path.join(output_dir, f"{base_name}_step7_collaborator.json")
    with open(collaborator_file, 'w', encoding='utf-8') as f:
        json.dump(most_frequent_collaborator, f, ensure_ascii=False, indent=2)

    print(f"Most frequent collaborator details saved to {collaborator_file}")

    # Compile the report
    report = {
        'researcher': {
            'name': author_data.get('name', ''),
            'abbreviated_name': author_data.get('abbreviated_name', ''),
            'affiliation': author_data.get('affiliation', ''),
            'email': author_data.get('email', ''),
            'research_fields': author_data.get('research_fields', []),
            'total_citations': author_data.get('total_citations', 0),
            'citations_5y': author_data.get('citations_5y', 0),
            'h_index': author_data.get('h_index', 0),
            'h_index_5y': author_data.get('h_index_5y', 0),
            'yearly_citations': author_data.get('yearly_citations', {}),
            'scholar_id': scholar_id or author_data.get('scholar_id', '')
        },
        'publication_stats': pub_stats,
        'coauthor_stats': coauthor_stats,
        'rating': rating,
        'most_frequent_collaborator': most_frequent_collaborator
    }

    # Save the report
    report_file = os.path.join(output_dir, f"{base_name}_report.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Report saved to {report_file}")

    # Step 8: Generate critical evaluation
    print("\n=== Step 8: Generate critical evaluation ===")
    try:
        print("Generating critical evaluation...")
        critical_evaluation = generate_critical_evaluation(report)
        print(f"Critical evaluation generated: {critical_evaluation[:50]}...")
    except Exception as e:
        print(f"Error generating critical evaluation: {e}")
        critical_evaluation = "Error generating critical evaluation."

    # Save the critical evaluation
    evaluation_file = os.path.join(output_dir, f"{base_name}_step8_evaluation.txt")
    with open(evaluation_file, 'w', encoding='utf-8') as f:
        f.write(critical_evaluation)

    print(f"Critical evaluation saved to {evaluation_file}")

    # Step 9: Find arxiv information
    print("\n=== Step 9: Find arxiv information ===")
    most_cited_paper = pub_stats.get('most_cited_paper', {})
    title = most_cited_paper.get('title', 'Unknown Title')

    try:
        print(f"Finding arxiv information for paper: {title}")
        most_cited_ai_paper = find_arxiv(title)
        print(f"Arxiv information retrieved")
    except Exception as e:
        print(f"Error finding arxiv: {e}")
        most_cited_ai_paper = {"name": title, "arxiv_url": "", "image": ""}

    # Save the arxiv information
    arxiv_file = os.path.join(output_dir, f"{base_name}_step9_arxiv.json")
    with open(arxiv_file, 'w', encoding='utf-8') as f:
        json.dump(most_cited_ai_paper, f, ensure_ascii=False, indent=2)

    print(f"Arxiv information saved to {arxiv_file}")

    # Step 10: Get paper news
    print("\n=== Step 10: Get paper news ===")
    try:
        print(f"Getting news for paper: {title}")
        news_info = get_latest_news(title)
        print(f"Paper news information generated")
    except Exception as e:
        print(f"Error getting news information: {e}")
        news_info = "No related news found."

    # Save the paper news information
    news_file = os.path.join(output_dir, f"{base_name}_step10_news.txt")
    with open(news_file, 'w', encoding='utf-8') as f:
        if isinstance(news_info, str):
            f.write(news_info)
        else:
            json.dump(news_info, f, ensure_ascii=False, indent=2)

    print(f"Paper news information saved to {news_file}")

    # Step 11: Get role model information
    print("\n=== Step 11: Get role model information ===")
    try:
        print("Generating role model information...")
        role_model = get_template_figure(report)
        print(f"Role model information generated")
    except Exception as e:
        print(f"Error getting role model information: {e}")
        role_model = None

    if role_model:
        # Save the role model information
        role_model_file = os.path.join(output_dir, f"{base_name}_step11_role_model.json")
        with open(role_model_file, 'w', encoding='utf-8') as f:
            json.dump(role_model, f, ensure_ascii=False, indent=2)

        print(f"Role model information saved to {role_model_file}")

    # Step 12: Get career level information
    print("\n=== Step 12: Get career level information ===")
    try:
        # Check if the report has publication statistics
        if pub_stats.get('total_papers', 0) > 0:
            print("Generating career level information...")
            level_info = three_card_juris_people(report)
            if not level_info:  # If level_info is None or empty dictionary
                level_info = {}
            print(f"Career level information generated")
        else:
            # If no publication statistics, create a default level_info
            level_info = {
                'level_cn': 'N/A (No papers found)',
                'level_us': 'N/A (No papers found)',
                'earnings': 'N/A',
                'justification': 'Cannot determine career level without publication data'
            }
    except Exception as e:
        print(f"Error getting career level information: {e}")
        level_info = {
            'level_cn': 'N/A (Error)',
            'level_us': 'N/A (Error)',
            'earnings': 'N/A',
            'justification': f'Error: {str(e)}'
        }

    # Save the career level information
    level_info_file = os.path.join(output_dir, f"{base_name}_step12_level_info.json")
    with open(level_info_file, 'w', encoding='utf-8') as f:
        json.dump(level_info, f, ensure_ascii=False, indent=2)

    print(f"Career level information saved to {level_info_file}")

    return report_file

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Run all test steps for a single scholar')
    parser.add_argument('--name', type=str, help='Researcher name')
    parser.add_argument('--id', type=str, help='Google Scholar ID')
    parser.add_argument('--url', type=str, help='Google Scholar URL')
    parser.add_argument('--output-dir', type=str, default='reports/tests/steps', help='Directory to save output')

    args = parser.parse_args()

    # Run all test steps
    test_all_steps(args.name, args.id, args.url, args.output_dir)

if __name__ == "__main__":
    main()
