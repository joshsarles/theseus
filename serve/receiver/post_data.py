#!/usr/bin/env python3
"""
Script to post JSON sensor data files to the receiver.py streaming API endpoint.

Usage:
    python post_data.py [--url URL] [--batch-size SIZE] [--delay SECONDS]

Example:
    python post_data.py --url http://localhost:8000 --batch-size 10 --delay 0.1
"""

import os
import json
import argparse
import time
import sys
from pathlib import Path
import requests
from typing import List, Dict, Any


def load_json_file(filepath: str) -> List[Dict[str, Any]]:
    """Load and parse a JSON file containing sensor records."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        print(f"✓ Loaded {len(data)} records from {filepath}")
        return data
    except Exception as e:
        print(f"✗ Error loading {filepath}: {e}")
        return []


def post_batch(url: str, topic_id: str, batch: List[Dict[str, Any]]) -> bool:
    """
    Post a batch of records to the streaming API endpoint.
    
    Args:
        url: The full API endpoint URL (e.g., http://localhost:8000/stream-item)
        topic_id: The topic identifier (e.g., "sensor")
        batch: List of sensor record dictionaries
    
    Returns:
        True if successful, False otherwise
    """
    payload = {
        "topic_id": topic_id,
        "data": batch
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()
        print(f"  ✓ Batch posted successfully. Status: {result.get('status')}, "
              f"Buffer depth: {result.get('current_buffer_depth')}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Error posting batch: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"    Response: {e.response.text}")
        return False


def process_file(filepath: str, api_url: str, topic_id: str, 
                batch_size: int, delay: float) -> tuple:
    """
    Process a single JSON file by posting its contents in batches.
    
    Returns:
        Tuple of (total_records, successful_batches, failed_batches)
    """
    records = load_json_file(filepath)
    if not records:
        return 0, 0, 0
    
    total_records = len(records)
    successful_batches = 0
    failed_batches = 0
    
    print(f"\nProcessing {Path(filepath).name} ({total_records} records):")
    print(f"  Posting in batches of {batch_size}...")
    
    # Split into batches and post
    for i in range(0, total_records, batch_size):
        batch = records[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_records + batch_size - 1) // batch_size
        
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} records)...", end=" ")
        
        if post_batch(api_url, topic_id, batch):
            successful_batches += 1
        else:
            failed_batches += 1
        
        # Add delay between batches to avoid overwhelming the API
        if delay > 0 and i + batch_size < total_records:
            time.sleep(delay)
    
    return total_records, successful_batches, failed_batches


def main():
    parser = argparse.ArgumentParser(
        description="Post JSON sensor data files to the streaming API endpoint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Post all JSON files with default settings
  python post_data.py
  
  # Use custom API URL and batch size
  python post_data.py --url http://localhost:8000 --batch-size 50
  
  # Add delay between batches (useful for rate limiting)
  python post_data.py --batch-size 10 --delay 0.5
  
  # Post specific files
  python post_data.py --files uuv1-sensors-anom.json uuv1-c2-anom.json
        """
    )
    
    parser.add_argument(
        '--url',
        default='http://localhost:8000',
        help='Base URL of the API service (default: http://localhost:8000)'
    )
    
    parser.add_argument(
        '--topic',
        default='sensor',
        help='Topic ID to send with the data (default: sensor)'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=25,
        help='Number of records to send per batch (default: 25)'
    )
    
    parser.add_argument(
        '--delay',
        type=float,
        default=0.1,
        help='Delay in seconds between batches (default: 0.1)'
    )
    
    parser.add_argument(
        '--files',
        nargs='+',
        help='Specific JSON files to post (default: all .json files in current directory)'
    )
    
    args = parser.parse_args()
    
    # Build full API endpoint URL
    api_url = f"{args.url.rstrip('/')}/stream-item"
    
    # Get list of files to process
    if args.files:
        json_files = args.files
    else:
        # Find all JSON files in current directory
        json_files = sorted([f for f in os.listdir('.') if f.endswith('.json')])
    
    if not json_files:
        print("No JSON files found to process.")
        sys.exit(1)
    
    print(f"{'='*70}")
    print(f"Streaming Data Uploader")
    print(f"{'='*70}")
    print(f"API Endpoint:  {api_url}")
    print(f"Topic ID:      {args.topic}")
    print(f"Batch Size:    {args.batch_size}")
    print(f"Batch Delay:   {args.delay}s")
    print(f"Files to post: {len(json_files)}")
    print(f"{'='*70}")
    
    # Process each file
    total_records_all = 0
    total_successful_batches = 0
    total_failed_batches = 0
    
    start_time = time.time()
    
    for json_file in json_files:
        if not os.path.exists(json_file):
            print(f"\n✗ File not found: {json_file}")
            continue
        
        records, success, failed = process_file(
            json_file, api_url, args.topic, args.batch_size, args.delay
        )
        
        total_records_all += records
        total_successful_batches += success
        total_failed_batches += failed
    
    elapsed_time = time.time() - start_time
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"Summary")
    print(f"{'='*70}")
    print(f"Total records processed:  {total_records_all}")
    print(f"Successful batches:       {total_successful_batches}")
    print(f"Failed batches:           {total_failed_batches}")
    print(f"Time elapsed:             {elapsed_time:.2f}s")
    print(f"Records per second:       {total_records_all / elapsed_time:.2f}")
    print(f"{'='*70}")
    
    # Exit with error code if any batches failed
    if total_failed_batches > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
