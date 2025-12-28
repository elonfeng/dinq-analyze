#!/usr/bin/env python
# coding: UTF-8
"""
Master script to run all scholar service test scripts in sequence.
This script orchestrates the execution of all the individual test scripts.
"""

import os
import sys
import argparse
import subprocess
from tqdm import tqdm

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

def run_script(script_path, args=None):
    """Run a Python script with optional arguments."""
    cmd = [sys.executable, script_path]
    if args:
        cmd.extend(args)
    
    print(f"\n{'='*80}")
    print(f"Running {os.path.basename(script_path)}")
    print(f"{'='*80}")
    
    result = subprocess.run(cmd, check=False)
    return result.returncode == 0

def main():
    """Main function to run all test scripts."""
    parser = argparse.ArgumentParser(description='Run all scholar service test scripts')
    parser.add_argument('--test-file', type=str, default='tests/scholar_tests/0416测试.txt', help='Path to test file with scholar names and URLs')
    parser.add_argument('--output-dir', type=str, default='reports/tests', help='Base directory to save output')
    parser.add_argument('--skip-main', action='store_true', help='Skip running the main scholar analysis')
    parser.add_argument('--only-step', type=int, help='Run only a specific step (1-7)')
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Define all test scripts
    scripts = [
        {
            'name': 'Main Scholar Analysis',
            'path': 'tests/scholar_tests/run_all_scholars.py',
            'step': 0,
            'skip': args.skip_main
        },
        {
            'name': 'Step 1-2: Researcher Search and Profile',
            'path': 'tests/scholar_tests/test_step1_2_researcher_search.py',
            'args': ['--test-file', args.test_file, '--output-dir', f"{args.output_dir}/step1_2"],
            'step': 1
        },
        {
            'name': 'Step 3: Publication Analysis',
            'path': 'tests/scholar_tests/test_step3_publication_analysis.py',
            'args': ['--input-dir', f"{args.output_dir}/step1_2", '--output-dir', f"{args.output_dir}/step3"],
            'step': 3
        },
        {
            'name': 'Step 4-5: Co-author Analysis and Network',
            'path': 'tests/scholar_tests/test_step4_5_coauthor_analysis.py',
            'args': ['--input-dir', f"{args.output_dir}/step1_2", '--output-dir', f"{args.output_dir}/step4_5"],
            'step': 4
        },
        {
            'name': 'Step 6: Researcher Rating',
            'path': 'tests/scholar_tests/test_step6_researcher_rating.py',
            'args': ['--input-dir', f"{args.output_dir}/step1_2", '--step3-dir', f"{args.output_dir}/step3", 
                    '--step4-5-dir', f"{args.output_dir}/step4_5", '--output-dir', f"{args.output_dir}/step6"],
            'step': 6
        },
        {
            'name': 'Step 7: Collaborator Details',
            'path': 'tests/scholar_tests/test_step7_collaborator_details.py',
            'args': ['--input-dir', f"{args.output_dir}/step4_5", '--output-dir', f"{args.output_dir}/step7"],
            'step': 7
        },
        {
            'name': 'Critical Evaluation',
            'path': 'tests/scholar_tests/test_critical_evaluation.py',
            'args': ['--input-dir', args.output_dir, '--output-dir', f"{args.output_dir}/critical_evaluation"],
            'step': 8
        },
        {
            'name': 'Role Model Information',
            'path': 'tests/scholar_tests/test_role_model_info.py',
            'args': ['--input-dir', args.output_dir, '--output-dir', f"{args.output_dir}/role_model"],
            'step': 9
        },
        {
            'name': 'Career Level Information',
            'path': 'tests/scholar_tests/test_career_level_info.py',
            'args': ['--input-dir', args.output_dir, '--output-dir', f"{args.output_dir}/career_level"],
            'step': 10
        },
        {
            'name': 'Paper News',
            'path': 'tests/scholar_tests/test_paper_news.py',
            'args': ['--input-dir', args.output_dir, '--output-dir', f"{args.output_dir}/paper_news"],
            'step': 11
        },
        {
            'name': 'Arxiv Information',
            'path': 'tests/scholar_tests/test_arxiv_info.py',
            'args': ['--input-dir', args.output_dir, '--output-dir', f"{args.output_dir}/arxiv_info"],
            'step': 12
        }
    ]
    
    # Run each script
    results = []
    for script in tqdm(scripts, desc="Running test scripts"):
        # Skip if specified
        if script.get('skip', False):
            print(f"Skipping {script['name']}")
            continue
        
        # Skip if not the specified step
        if args.only_step is not None and script['step'] != args.only_step:
            continue
        
        # Run the script
        success = run_script(script['path'], script.get('args'))
        results.append((script['name'], success))
    
    # Print summary
    print("\n\n" + "="*80)
    print("Test Summary")
    print("="*80)
    for name, success in results:
        status = "✅ Passed" if success else "❌ Failed"
        print(f"{name}: {status}")
    
    # Count successes
    success_count = sum(1 for _, success in results if success)
    print(f"\n{success_count} out of {len(results)} tests passed")

if __name__ == "__main__":
    main()
