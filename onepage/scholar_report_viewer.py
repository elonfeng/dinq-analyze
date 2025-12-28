#!/usr/bin/env python3
"""
Scholar Report Viewer - Generate HTML page from JSON report file
"""

import json
import os
import sys
import argparse
from datetime import datetime

def generate_html(json_file_path):
    """Generate HTML page from JSON report file"""
    
    # Read the JSON file
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return None
    
    # Extract researcher name for the title
    researcher_name = data.get('researcher', {}).get('name', 'Unknown Researcher')
    
    # Generate HTML content
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{researcher_name} - Scholar Report</title>
    <style>
        :root {{
            --primary-color: #4285f4;
            --secondary-color: #fbbc05;
            --accent-color: #34a853;
            --text-color: #333;
            --light-bg: #f5f5f5;
            --card-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            background-color: var(--light-bg);
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: var(--card-shadow);
            padding: 20px;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }}
        
        h1 {{
            color: var(--primary-color);
            margin-bottom: 10px;
        }}
        
        .subtitle {{
            color: #666;
            font-size: 1.1rem;
        }}
        
        .search-bar {{
            display: flex;
            justify-content: center;
            margin-bottom: 20px;
        }}
        
        .search-bar input {{
            width: 50%;
            padding: 10px 15px;
            border: 1px solid #ddd;
            border-radius: 30px;
            font-size: 1rem;
        }}
        
        .search-bar button {{
            background: var(--primary-color);
            color: white;
            border: none;
            border-radius: 30px;
            padding: 10px 20px;
            margin-left: 10px;
            cursor: pointer;
        }}
        
        .grid-container {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .card {{
            background: white;
            border-radius: 8px;
            box-shadow: var(--card-shadow);
            padding: 20px;
            transition: transform 0.3s ease;
        }}
        
        .card:hover {{
            transform: translateY(-5px);
        }}
        
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #eee;
        }}
        
        .card-title {{
            font-size: 1.2rem;
            font-weight: 600;
            color: var(--primary-color);
            display: flex;
            align-items: center;
        }}
        
        .card-title i {{
            margin-right: 10px;
        }}
        
        .card-actions {{
            display: flex;
        }}
        
        .card-actions button {{
            background: none;
            border: none;
            color: #666;
            cursor: pointer;
            margin-left: 5px;
            font-size: 0.9rem;
            padding: 2px 5px;
            border-radius: 3px;
        }}
        
        .card-actions button:hover {{
            background: #f0f0f0;
        }}
        
        .card-content {{
            font-size: 0.95rem;
        }}
        
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-top: 15px;
        }}
        
        .stat-item {{
            text-align: center;
            padding: 10px;
        }}
        
        .stat-value {{
            font-size: 1.8rem;
            font-weight: bold;
            color: var(--primary-color);
            margin-bottom: 5px;
        }}
        
        .stat-label {{
            font-size: 0.8rem;
            color: #666;
        }}
        
        .profile-card {{
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
        }}
        
        .profile-image {{
            width: 100px;
            height: 100px;
            border-radius: 50%;
            background-color: #e0e0e0;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2.5rem;
            color: white;
            background: var(--primary-color);
        }}
        
        .profile-name {{
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 5px;
        }}
        
        .profile-affiliation {{
            color: #666;
            margin-bottom: 15px;
        }}
        
        .profile-stats {{
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 15px;
        }}
        
        .profile-stat {{
            text-align: center;
        }}
        
        .profile-stat-value {{
            font-size: 1.3rem;
            font-weight: bold;
            color: var(--primary-color);
        }}
        
        .profile-stat-label {{
            font-size: 0.8rem;
            color: #666;
        }}
        
        .tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 15px;
        }}
        
        .tag {{
            background: #f0f0f0;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.8rem;
            color: #666;
        }}
        
        .chart-container {{
            height: 200px;
            margin-top: 15px;
        }}
        
        .bar-chart {{
            display: flex;
            height: 150px;
            align-items: flex-end;
            gap: 15px;
            margin-top: 15px;
        }}
        
        .bar {{
            flex: 1;
            background: var(--primary-color);
            min-width: 20px;
            border-radius: 5px 5px 0 0;
            position: relative;
            transition: height 0.5s ease;
        }}
        
        .bar-label {{
            position: absolute;
            bottom: -25px;
            left: 0;
            right: 0;
            text-align: center;
            font-size: 0.8rem;
            color: #666;
        }}
        
        .bar-value {{
            position: absolute;
            top: -25px;
            left: 0;
            right: 0;
            text-align: center;
            font-size: 0.8rem;
            color: #666;
        }}
        
        .collaborator-card {{
            display: flex;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid #eee;
        }}
        
        .collaborator-image {{
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: var(--secondary-color);
            margin-right: 15px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }}
        
        .collaborator-info {{
            flex: 1;
        }}
        
        .collaborator-name {{
            font-weight: 600;
            margin-bottom: 3px;
        }}
        
        .collaborator-papers {{
            font-size: 0.8rem;
            color: #666;
        }}
        
        .paper-list {{
            margin-top: 15px;
        }}
        
        .paper-item {{
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid #eee;
        }}
        
        .paper-title {{
            font-weight: 600;
            margin-bottom: 5px;
        }}
        
        .paper-venue {{
            font-size: 0.8rem;
            color: #666;
            margin-bottom: 5px;
        }}
        
        .paper-citations {{
            font-size: 0.8rem;
            color: var(--accent-color);
        }}
        
        .progress-bar {{
            height: 10px;
            background: #e0e0e0;
            border-radius: 5px;
            margin-top: 10px;
            overflow: hidden;
        }}
        
        .progress {{
            height: 100%;
            background: var(--primary-color);
            border-radius: 5px;
        }}
        
        footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #666;
            font-size: 0.9rem;
        }}
        
        @media (max-width: 768px) {{
            .grid-container {{
                grid-template-columns: 1fr;
            }}
            
            .stat-grid {{
                grid-template-columns: 1fr 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>学者分析报告</h1>
            <p class="subtitle">AI-powered analysis of scholar academic contributions</p>
            
            <div class="search-bar">
                <input type="text" placeholder="Search for a scholar..." value="{researcher_name}">
                <button>Search</button>
            </div>
        </header>
        
        <!-- Profile Section -->
        <div class="card profile-card">
            <div class="profile-image">{researcher_name[0]}</div>
            <h2 class="profile-name">{researcher_name}</h2>
            <p class="profile-affiliation">{data.get('researcher', {}).get('affiliation', 'Unknown Affiliation')}</p>
            
            <div class="tags">
"""

    # Add research fields as tags
    research_fields = data.get('researcher', {}).get('research_fields', [])
    for field in research_fields:
        html += f'                <span class="tag">{field}</span>\n'
    
    html += """            </div>
            
            <div class="profile-stats">
                <div class="profile-stat">
                    <div class="profile-stat-value">{h_index}</div>
                    <div class="profile-stat-label">H-Index</div>
                </div>
                <div class="profile-stat">
                    <div class="profile-stat-value">{citations}</div>
                    <div class="profile-stat-label">Citations</div>
                </div>
                <div class="profile-stat">
                    <div class="profile-stat-value">{papers}</div>
                    <div class="profile-stat-label">Papers</div>
                </div>
            </div>
        </div>
        
        <div class="grid-container">
            <!-- Papers Section -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">📄 Papers</div>
                    <div class="card-actions">
                        <button>View More</button>
                    </div>
                </div>
                <div class="card-content">
                    <div class="stat-grid">
                        <div class="stat-item">
                            <div class="stat-value">{total_papers}</div>
                            <div class="stat-label">Total Papers</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">{first_author}</div>
                            <div class="stat-label">First Author</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">{top_tier}%</div>
                            <div class="stat-label">Top Tier</div>
                        </div>
                    </div>
                    
                    <div class="bar-chart">
""".format(
        h_index=data.get('researcher', {}).get('h_index', 'N/A'),
        citations=data.get('researcher', {}).get('total_citations', 'N/A'),
        papers=data.get('publication_stats', {}).get('total_papers', 'N/A'),
        total_papers=data.get('publication_stats', {}).get('total_papers', 'N/A'),
        first_author=data.get('publication_stats', {}).get('first_author_papers', 'N/A'),
        top_tier=round(data.get('publication_stats', {}).get('top_tier_percentage', 0))
    )
    
    # Add publication bars by year
    year_distribution = data.get('publication_stats', {}).get('year_distribution', {})
    max_papers = max(year_distribution.values()) if year_distribution else 1
    
    for year, count in sorted(year_distribution.items())[:5]:  # Show last 5 years
        height_percentage = (count / max_papers) * 100
        html += f"""                        <div class="bar" style="height: {height_percentage}%">
                            <div class="bar-value">{count}</div>
                            <div class="bar-label">{year}</div>
                        </div>
"""
    
    html += """                    </div>
                </div>
            </div>
            
            <!-- Insights Section -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">🔍 Insights</div>
                    <div class="card-actions">
                        <button>View More</button>
                    </div>
                </div>
                <div class="card-content">
                    <div class="stat-grid">
"""
    
    # Citation stats
    citation_stats = data.get('publication_stats', {}).get('citation_stats', {})
    html += f"""                        <div class="stat-item">
                            <div class="stat-value">{citation_stats.get('total_citations', 'N/A')}</div>
                            <div class="stat-label">Citations</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">{citation_stats.get('avg_citations', 'N/A'):.1f}</div>
                            <div class="stat-label">Avg. Citations</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">{citation_stats.get('max_citations', 'N/A')}</div>
                            <div class="stat-label">Max Citations</div>
                        </div>
"""
    
    html += """                    </div>
                    
                    <div class="chart-container">
                        <!-- Citation trend chart would go here -->
                    </div>
                </div>
            </div>
            
            <!-- Role Model Section -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">👨‍🏫 Role Model</div>
                    <div class="card-actions">
                        <button>View More</button>
                    </div>
                </div>
                <div class="card-content">
"""
    
    # Most frequent collaborator as role model
    collaborator = data.get('most_frequent_collaborator', {})
    if collaborator:
        initials = ''.join([name[0] for name in collaborator.get('full_name', 'Unknown').split() if name])
        html += f"""                    <div class="collaborator-card">
                        <div class="collaborator-image">{initials}</div>
                        <div class="collaborator-info">
                            <div class="collaborator-name">{collaborator.get('full_name', 'Unknown')}</div>
                            <div class="collaborator-papers">{collaborator.get('affiliation', 'Unknown Affiliation')}</div>
                        </div>
                    </div>
                    
                    <div>
                        <div>Coauthored papers: <strong>{collaborator.get('coauthored_papers', 'N/A')}</strong></div>
                        <div class="paper-title">{collaborator.get('best_paper', {}).get('title', 'N/A')}</div>
                        <div class="paper-venue">{collaborator.get('best_paper', {}).get('venue', 'N/A')}</div>
                        <div class="paper-citations">Citations: {collaborator.get('best_paper', {}).get('citations', 'N/A')}</div>
                    </div>
"""
    
    html += """                </div>
            </div>
            
            <!-- Closest Collaborator Section -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">👥 Closest Collaborator</div>
                    <div class="card-actions">
                        <button>View More</button>
                    </div>
                </div>
                <div class="card-content">
"""
    
    # Top coauthors
    top_coauthors = data.get('coauthor_stats', {}).get('top_coauthors', [])
    if top_coauthors and len(top_coauthors) > 0:
        coauthor = top_coauthors[0]
        initials = ''.join([name[0] for name in coauthor.get('name', 'Unknown').split() if name])
        html += f"""                    <div class="collaborator-card">
                        <div class="collaborator-image">{initials}</div>
                        <div class="collaborator-info">
                            <div class="collaborator-name">{coauthor.get('name', 'Unknown')}</div>
                            <div class="collaborator-papers">{coauthor.get('coauthored_papers', 'N/A')} coauthored papers</div>
                        </div>
                    </div>
                    
                    <div>
                        <div class="paper-title">{coauthor.get('best_paper', {}).get('title', 'N/A')}</div>
                        <div class="paper-venue">{coauthor.get('best_paper', {}).get('venue', 'N/A')}</div>
                        <div class="paper-citations">Citations: {coauthor.get('best_paper', {}).get('citations', 'N/A')}</div>
                    </div>
"""
    
    html += """                </div>
            </div>
            
            <!-- Research Character Section -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">🔬 Research Character</div>
                    <div class="card-actions">
                        <button>View More</button>
                    </div>
                </div>
                <div class="card-content">
                    <div>
                        <div>Theoretical Research</div>
                        <div class="progress-bar">
                            <div class="progress" style="width: 65%"></div>
                        </div>
                    </div>
                    <div style="margin-top: 15px;">
                        <div>Applied Research</div>
                        <div class="progress-bar">
                            <div class="progress" style="width: 35%"></div>
                        </div>
                    </div>
                    <div style="margin-top: 15px;">
                        <div>Academic Depth</div>
                        <div class="progress-bar">
                            <div class="progress" style="width: 70%"></div>
                        </div>
                    </div>
                    <div style="margin-top: 15px;">
                        <div>Industry Breadth</div>
                        <div class="progress-bar">
                            <div class="progress" style="width: 30%"></div>
                        </div>
                    </div>
                    <div style="margin-top: 15px;">
                        <div>Team Collaboration</div>
                        <div class="progress-bar">
                            <div class="progress" style="width: 85%"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Signature Papers Section -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">📝 Signature papers</div>
                    <div class="card-actions">
                        <button>View More</button>
                    </div>
                </div>
                <div class="card-content">
                    <div class="paper-list">
"""
    
    # Most cited paper
    most_cited = data.get('publication_stats', {}).get('most_cited_paper', {})
    if most_cited:
        html += f"""                        <div class="paper-item">
                            <div class="paper-title">{most_cited.get('title', 'N/A')}</div>
                            <div class="paper-venue">{most_cited.get('venue', 'N/A')}</div>
                            <div class="paper-citations">Citations: {most_cited.get('citations', 'N/A')}</div>
                        </div>
"""
    
    # First author papers (top 2)
    first_author_papers = data.get('publication_stats', {}).get('first_author_papers_list', [])
    for paper in first_author_papers[:2]:
        html += f"""                        <div class="paper-item">
                            <div class="paper-title">{paper.get('title', 'N/A')}</div>
                            <div class="paper-venue">{paper.get('venue', 'N/A')}</div>
                            <div class="paper-citations">Citations: {paper.get('citations', 'N/A')}</div>
                        </div>
"""
    
    html += """                    </div>
                </div>
            </div>
        </div>
        
        <footer>
            <p>Copyright © 2025 DINQ · All rights reserved</p>
        </footer>
    </div>
    
    <script>
        // JavaScript to handle interactions
        document.addEventListener('DOMContentLoaded', function() {
            // Make the JSON data available to the page
            window.scholarData = {json_data};
            
            // Handle search button click
            const searchButton = document.querySelector('.search-bar button');
            searchButton.addEventListener('click', function() {
                alert('Search functionality would be implemented here');
            });
            
            // Handle "View More" buttons
            const viewMoreButtons = document.querySelectorAll('.card-actions button');
            viewMoreButtons.forEach(button => {
                button.addEventListener('click', function() {
                    const cardTitle = this.closest('.card-header').querySelector('.card-title').textContent.trim();
                    alert(`View more details about ${cardTitle}`);
                });
            });
        });
    </script>
</body>
</html>
""".replace('{json_data}', json.dumps(data))
    
    return html

def save_html(html_content, output_path):
    """Save HTML content to a file"""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"HTML file saved to: {output_path}")
        return True
    except Exception as e:
        print(f"Error saving HTML file: {e}")
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Generate HTML report from scholar JSON file')
    parser.add_argument('json_file', help='Path to the JSON file')
    parser.add_argument('-o', '--output', help='Output HTML file path')
    
    args = parser.parse_args()
    
    # Generate HTML from JSON
    html_content = generate_html(args.json_file)
    if not html_content:
        sys.exit(1)
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        # Extract filename without extension
        base_name = os.path.splitext(os.path.basename(args.json_file))[0]
        output_path = f"{os.path.dirname(args.json_file)}/{base_name}.html"
    
    # Save HTML to file
    if save_html(html_content, output_path):
        print(f"Report generated successfully. Open {output_path} in a web browser to view.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
