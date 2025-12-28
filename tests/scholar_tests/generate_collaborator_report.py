#!/usr/bin/env python
# coding: UTF-8
"""
Generate a readable text report from batch collaborator test results
"""

import os
import sys
import json
import argparse
from datetime import datetime

def generate_text_report(input_file, output_file=None):
    """
    Generate a readable text report from batch collaborator test results.
    
    Args:
        input_file (str): Path to JSON results file
        output_file (str): Path to save text report (default: auto-generated)
        
    Returns:
        str: Path to the generated report
    """
    # Load JSON results
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Generate report filename if not provided
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.splitext(input_file)[0] + f"_report_{timestamp}.txt"
    
    # Generate report content
    lines = []
    lines.append("=" * 80)
    lines.append("SCHOLAR BEST COLLABORATORS REPORT")
    lines.append("=" * 80)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Source: {input_file}")
    lines.append(f"Total scholars: {data.get('total_scholars', 'N/A')}")
    lines.append(f"Successfully processed: {data.get('successful', 'N/A')}")
    lines.append(f"Failed: {data.get('failed', 'N/A')}")
    lines.append("=" * 80)
    lines.append("")
    
    # Add details for each scholar
    results = data.get('results', {})
    for scholar_id, scholar_data in results.items():
        scholar_name = scholar_data.get('scholar_name', 'Unknown')
        lines.append(f"SCHOLAR: {scholar_name}")
        lines.append(f"ID: {scholar_id}")
        lines.append("-" * 80)
        
        collaborator = scholar_data.get('best_collaborator', {})
        if collaborator:
            lines.append("BEST COLLABORATOR:")
            lines.append(f"  Name: {collaborator.get('full_name', 'N/A')}")
            lines.append(f"  Affiliation: {collaborator.get('affiliation', 'N/A')}")
            
            # Research interests
            interests = collaborator.get('research_interests', [])
            if interests:
                lines.append(f"  Research Interests: {', '.join(interests)}")
            else:
                lines.append(f"  Research Interests: None specified")
            
            # Collaboration stats
            lines.append(f"  Scholar ID: {collaborator.get('scholar_id', 'N/A')}")
            lines.append(f"  Co-authored Papers: {collaborator.get('coauthored_papers', 'N/A')}")
            lines.append(f"  H-index: {collaborator.get('h_index', 'N/A')}")
            lines.append(f"  Total Citations: {collaborator.get('total_citations', 'N/A')}")
            
            # Best paper
            best_paper = collaborator.get('best_paper', {})
            if best_paper:
                lines.append("  BEST COLLABORATIVE PAPER:")
                lines.append(f"    Title: {best_paper.get('title', 'N/A')}")
                lines.append(f"    Year: {best_paper.get('year', 'N/A')}")
                lines.append(f"    Venue: {best_paper.get('venue', 'N/A')}")
                lines.append(f"    Citations: {best_paper.get('citations', 'N/A')}")
        else:
            lines.append("No best collaborator information available")
        
        lines.append("")
        lines.append("=" * 80)
        lines.append("")
    
    # Write report to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"Text report generated: {output_file}")
    return output_file

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Generate text report from batch collaborator results')
    parser.add_argument('--input-file', type=str, required=True, 
                        help='Path to JSON results file')
    parser.add_argument('--output-file', type=str, 
                        help='Path to save text report (default: auto-generated)')
    
    args = parser.parse_args()
    
    generate_text_report(args.input_file, args.output_file)

if __name__ == "__main__":
    main()
