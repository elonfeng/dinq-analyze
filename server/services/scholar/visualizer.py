# coding: UTF-8
"""
Visualizer module for Scholar API service.
Handles visualization of publication trends and co-author networks.
"""

import os
import sys
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
import numpy as np

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

class ScholarVisualizer:
    """
    Handles visualization of publication trends and co-author networks.
    """
    
    def __init__(self):
        """
        Initialize the visualizer with default settings.
        """
        # Set default style
        sns.set_style("whitegrid")
        
    def visualize_publication_trends(self, pub_stats):
        """
        Create visualizations for publication trends.
        
        Args:
            pub_stats (dict): Publication statistics
            
        Returns:
            matplotlib.figure.Figure: Figure containing visualizations
        """
        if not pub_stats:
            return None
            
        # Create a figure with multiple subplots
        fig = plt.figure(figsize=(15, 12))
        
        # 1. Publications by year
        ax1 = fig.add_subplot(2, 2, 1)
        year_data = pub_stats.get('year_distribution', {})
        years = list(year_data.keys())
        counts = list(year_data.values())
        
        if years and counts:
            ax1.bar(years, counts, color='skyblue')
            ax1.set_title('Publications by Year')
            ax1.set_xlabel('Year')
            ax1.set_ylabel('Number of Publications')
            ax1.tick_params(axis='x', rotation=45)
        else:
            ax1.text(0.5, 0.5, 'No year data available', ha='center', va='center')
        
        # 2. Top conferences
        ax2 = fig.add_subplot(2, 2, 2)
        conf_data = pub_stats.get('conference_distribution', {})
        
        if conf_data:
            # Sort by count (descending)
            sorted_confs = sorted(conf_data.items(), key=lambda x: x[1], reverse=True)
            confs = [x[0] for x in sorted_confs]
            counts = [x[1] for x in sorted_confs]
            
            # Limit to top 10 for readability
            if len(confs) > 10:
                confs = confs[:10]
                counts = counts[:10]
                
            # Create horizontal bar chart
            ax2.barh(confs, counts, color='lightgreen')
            ax2.set_title('Top Conference Venues')
            ax2.set_xlabel('Number of Publications')
            ax2.invert_yaxis()  # Highest count at the top
        else:
            ax2.text(0.5, 0.5, 'No conference data available', ha='center', va='center')
        
        # 3. Citation distribution
        ax3 = fig.add_subplot(2, 2, 3)
        citation_stats = pub_stats.get('citation_stats', {})
        
        if citation_stats:
            # Create a pie chart for author position
            labels = ['First Author', 'Last Author', 'Other Position']
            first_author = pub_stats.get('first_author_papers', 0)
            last_author = pub_stats.get('last_author_papers', 0)
            other_author = pub_stats.get('total_papers', 0) - first_author - last_author
            
            sizes = [first_author, last_author, other_author]
            colors = ['#ff9999', '#66b3ff', '#99ff99']
            
            if sum(sizes) > 0:
                ax3.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
                ax3.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
                ax3.set_title('Author Position Distribution')
            else:
                ax3.text(0.5, 0.5, 'No author position data available', ha='center', va='center')
        else:
            ax3.text(0.5, 0.5, 'No citation data available', ha='center', va='center')
        
        # 4. Top-tier vs. Other Publications
        ax4 = fig.add_subplot(2, 2, 4)
        top_tier = pub_stats.get('top_tier_papers', 0)
        total = pub_stats.get('total_papers', 0)
        
        if total > 0:
            other = total - top_tier
            labels = ['Top-tier Venues', 'Other Venues']
            sizes = [top_tier, other]
            colors = ['#ff9999', '#66b3ff']
            
            ax4.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
            ax4.axis('equal')
            ax4.set_title('Publication Venue Quality')
        else:
            ax4.text(0.5, 0.5, 'No publication data available', ha='center', va='center')
        
        # Adjust layout
        plt.tight_layout()
        
        return fig
    
    def visualize_coauthor_network(self, G):
        """
        Visualize the co-author network.
        
        Args:
            G (networkx.Graph): Co-author network graph
            
        Returns:
            matplotlib.figure.Figure: Figure containing visualization
        """
        if not G or len(G.nodes()) <= 1:
            return None
            
        # Create figure
        fig = plt.figure(figsize=(12, 10))
        ax = fig.add_subplot(111)
        
        # Get node attributes
        node_sizes = [G.nodes[node].get('size', 10) * 20 for node in G.nodes()]
        node_colors = [G.nodes[node].get('color', 'blue') for node in G.nodes()]
        
        # Get edge attributes
        edge_weights = [G[u][v].get('weight', 1) for u, v in G.edges()]
        
        # Calculate layout
        if len(G.nodes()) < 50:
            # For smaller networks, use force-directed layout
            pos = nx.spring_layout(G, k=0.3, iterations=50)
        else:
            # For larger networks, use faster layout
            pos = nx.kamada_kawai_layout(G)
        
        # Draw the network
        nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors, alpha=0.8, ax=ax)
        nx.draw_networkx_edges(G, pos, width=edge_weights, alpha=0.5, edge_color='gray', ax=ax)
        
        # Add labels only to main nodes and top collaborators
        main_nodes = [node for node in G.nodes() if G.nodes[node].get('main', False)]
        top_collaborators = [node for node in G.nodes() 
                            if not G.nodes[node].get('main', False) 
                            and G.nodes[node].get('collaborations', 0) >= 3]
        
        label_nodes = main_nodes + top_collaborators
        labels = {node: node for node in label_nodes}
        
        nx.draw_networkx_labels(G, pos, labels=labels, font_size=10, font_weight='bold', ax=ax)
        
        # Set title and remove axis
        ax.set_title('Co-authorship Network', fontsize=16)
        ax.axis('off')
        
        return fig
