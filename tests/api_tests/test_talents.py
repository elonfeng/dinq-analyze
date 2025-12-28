#!/usr/bin/env python
# coding: UTF-8
"""
Test script for the talents_handler module.
"""

import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from server.api.talents_handler import get_top_talents, get_csv_path

def main():
    """
    Test the talents_handler module.
    """
    print("Testing talents_handler module...")
    
    # Print the CSV path
    csv_path = get_csv_path()
    print(f"CSV path: {csv_path}")
    print(f"CSV exists: {os.path.exists(csv_path)}")
    
    # Get top talents
    talents = get_top_talents(5)
    print(f"Talents: {talents}")
    
    print("Test completed.")

if __name__ == "__main__":
    main()
