#!/usr/bin/env python3
"""
Single Camera GUI Runner
Run this script to start the single camera detection system
"""

import sys
import os

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gui_single_camera import main

if __name__ == "__main__":
    print("Starting ScanAI Single Camera Detection System...")
    main() 