#!/usr/bin/env python3
import json
import os

def check_json_files(directory):
    """Check all JSON files in a directory for corruption"""
    corrupted_files = []
    
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, 'r') as f:
                    json.load(f)
                print(f"✓ {filename} - OK")
            except json.JSONDecodeError as e:
                print(f"✗ {filename} - CORRUPTED: {e}")
                corrupted_files.append(filename)
            except Exception as e:
                print(f"✗ {filename} - ERROR: {e}")
                corrupted_files.append(filename)
    
    return corrupted_files

if __name__ == "__main__":
    predictions_dir = "validation_data/predictions"
    sessions_dir = "validation_data/sessions"
    
    print("Checking predictions directory...")
    corrupted_predictions = check_json_files(predictions_dir)
    
    print("\nChecking sessions directory...")
    corrupted_sessions = check_json_files(sessions_dir)
    
    print(f"\nSummary:")
    print(f"Corrupted prediction files: {len(corrupted_predictions)}")
    print(f"Corrupted session files: {len(corrupted_sessions)}")
    
    if corrupted_predictions or corrupted_sessions:
        print("\nCorrupted files found:")
        for f in corrupted_predictions + corrupted_sessions:
            print(f"  - {f}")