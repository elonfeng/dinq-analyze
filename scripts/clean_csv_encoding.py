#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CSV Encoding Cleaner

This script cleans encoding issues in the top_ai_talents.csv file.
It handles:
1. Special character encoding problems
2. Replaces Chinese punctuation with standard ASCII punctuation
3. Fixes other encoding artifacts

Usage:
    python clean_csv_encoding.py
"""

import csv
import os
import sys
import re
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def clean_text(text):
    """
    Clean text by fixing encoding issues and replacing problematic characters.
    
    Args:
        text (str): The text to clean
        
    Returns:
        str: Cleaned text
    """
    if not isinstance(text, str):
        return text
    
    # Replace Chinese punctuation with standard ASCII punctuation
    text = text.replace('，', ',')
    text = text.replace('；', ';')
    text = text.replace('：', ':')
    text = text.replace('"', '"')
    text = text.replace('"', '"')
    text = text.replace(''', "'")
    text = text.replace(''', "'")
    text = text.replace('。', '.')
    text = text.replace('！', '!')
    text = text.replace('？', '?')
    
    # Fix common encoding artifacts
    text = text.replace('��', 'è')  # Common issue with French characters
    text = text.replace('Ã©', 'é')
    text = text.replace('Ã¨', 'è')
    text = text.replace('Ã§', 'ç')
    text = text.replace('Ã´', 'ô')
    text = text.replace('Ã¢', 'â')
    text = text.replace('Ã®', 'î')
    text = text.replace('Ã»', 'û')
    
    # Remove any remaining non-printable characters
    text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)
    
    return text

def clean_csv_file(input_file, output_file=None):
    """
    Clean encoding issues in a CSV file.
    
    Args:
        input_file (str): Path to the input CSV file
        output_file (str, optional): Path to the output CSV file. If None, overwrites the input file.
    """
    if output_file is None:
        output_file = input_file + '.tmp'
    
    # Try different encodings
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
    
    for encoding in encodings:
        try:
            # Read the CSV file
            with open(input_file, 'r', encoding=encoding, errors='replace') as f:
                print(f"Reading file with {encoding} encoding...")
                reader = csv.reader(f)
                rows = list(reader)
                break
        except Exception as e:
            print(f"Failed with {encoding} encoding: {e}")
    else:
        raise ValueError("Could not read the CSV file with any of the attempted encodings")
    
    # Clean each cell in the CSV
    cleaned_rows = []
    for row in rows:
        cleaned_row = [clean_text(cell) for cell in row]
        cleaned_rows.append(cleaned_row)
    
    # Write the cleaned data to the output file
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(cleaned_rows)
    
    # If we're overwriting the input file, replace it with the temporary file
    if output_file == input_file + '.tmp':
        os.replace(output_file, input_file)
        print(f"Cleaned file saved to {input_file}")
    else:
        print(f"Cleaned file saved to {output_file}")

if __name__ == "__main__":
    # Path to the CSV file
    csv_file = os.path.join(project_root, "top_ai_talents.csv")
    
    if not os.path.exists(csv_file):
        print(f"Error: File not found at '{csv_file}'")
        sys.exit(1)
    
    print(f"Cleaning encoding issues in {csv_file}...")
    clean_csv_file(csv_file)
    print("Done!")