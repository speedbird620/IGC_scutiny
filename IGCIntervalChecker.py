# Script to analyze IGC files and check their logging intervals
#
# Copyright (C) 2025 Skyracer.net
# 
# This software is a GNU General Public License (GPL) project.
#
# Rev 1.0 - Initial version
#
# Reference: https://xp-soaring.github.io/igc_file_format/igc_format_2008.html#link_3.1

import os
import sys
from datetime import datetime, timedelta
import argparse
import statistics

def format_timedelta(td):
    """Format a timedelta object as HH:MM:SS"""
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def parse_b_record_time(b_record):
    """
    Parse the time from a B record line.
    Format: BHHMMSSLLLLLLLLoooooooA
    Where HHMMSS is the time (hour, minute, second)
    """
    if len(b_record) < 7:
        return None
        
    try:
        hour = int(b_record[1:3])
        minute = int(b_record[3:5])
        second = int(b_record[5:7])
        
        # Create a time object without date (we only care about time intervals)
        time_obj = timedelta(hours=hour, minutes=minute, seconds=second)
        return time_obj
    except (ValueError, IndexError):
        return None

def parse_igc_header(file_path):
    """
    Parse the header information from an IGC file to extract flight recorder details.
    
    IGC headers typically include:
    - A record: Flight recorder manufacturer and identification
    - H records: Various header information including FR type, pilot, etc.
    
    Returns:
        dict: A dictionary containing manufacturer, device model and device ID
    """
    header_info = {
        'manufacturer': 'Unknown',
        'device_model': 'Unknown',
        'device_id': 'Unknown',
        'dateYY': 'Unknown',
        'dateMM': 'Unknown',
        'dateDD': 'Unknown',
        'device_FW': 'Unknown',
        'device_HW': 'Unknown'
    }
    
    try:
        with open(file_path, 'r', errors='replace') as f:
            for line in f:
                line = line.strip()
                
                # Parse A record (FR manufacturer and identification)
                if line.startswith('A'):
                    if len(line) >= 4:
                        mfr_code = line[1:4]                        # Map manufacturer codes to full names (from IGC approval table)
                        manufacturers = {
                            'ACT': 'Aircotec Flight Instruments',
                            'CAM': 'Cambridge Aero Instruments',
                            'CNI': 'ClearNav Instruments',
                            'DSX': 'DataSwan',
                            'EWA': 'EW Avionics',
                            'FIL': 'Filser',
                            'FLA': 'Flarm Technology GmbH',
                            'XFL': 'Flarm Technology GmbH',
                            'GCS': 'Garrecht Avionik GmbH',
                            'IMI': 'IMI Gliding Equipment',
                            'LGS': 'Logstream SP',
                            'LXN': 'LX Navigation',
                            'LXV': 'LXNAV ',
                            'NAV': 'Naviter',
                            'NKL': 'Nielsen-Kellerman',
                            'NTE': 'New Technologies',
                            'PFE': 'PressFinish Electronics',
                            'RCE': 'RC Electronics',
                            'SCH': 'Scheffel Automation',
                            'SDI': 'Streamline Digital Instruments',
                            'TRI': 'Triadis Engineering GmbH',
                            'ZAN': 'Zander Segelflugrechner'
                        }
                        header_info['manufacturer'] = manufacturers.get(mfr_code, mfr_code)
                        
                        # Extract device ID if available in the A record
                        if len(line) > 4:
                            header_info['device_id'] = line[4:7]
                
                # Parse H records for device info
                if line.startswith('HFFTYFRTYPE:'):
                    parts = line[12:].split(',')
                    if parts and parts[0].strip():
                        header_info['device_model'] = parts[0].strip()

                # Parse H records for device info
                if line.startswith('HFRFWFIRMWAREVERSION:'):
                    parts = line[12:].split(':')
                    if parts and parts[0].strip():
                        header_info['device_FW'] = parts[1].strip()

                # Parse H records for device info
                if line.startswith('HFRHWHARDWAREVERSION:'):
                    parts = line[12:].split(':')
                    if parts and parts[0].strip():
                        header_info['device_HW'] = parts[1].strip()

                # Parse H records for device info
                if line.startswith('HFDTEDATE:'):
                    #print(line)
                    header_info['dateDD'] = line[10:12]
                    header_info['dateMM'] = line[12:14]
                    header_info['dateYY'] = line[14:]

                # Break after we've read past the header section (when B records start)
                if line.startswith('B'):
                    break
    
    except Exception as e:
        print(f"Error reading header from {file_path}: {e}")
    
    return header_info

def format_time(seconds):
    """Format seconds into a human-readable string (MM:SS)"""
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours > 0:
        return f"{int(hours)}h {int(minutes)}m {seconds:.1f}s"
    elif minutes > 0:
        return f"{int(minutes)}m {seconds:.1f}s"
    else:
        return f"{seconds:.1f}s"

def analyze_igc_file(file_path):
    """
    Analyze an IGC file to determine the logging interval.
    
    Args:
        file_path: Path to the IGC file
        
    Returns:
        tuple: (
            is_fixed_interval: bool, 
            avg_interval_seconds: float, 
            min_interval_seconds: float, 
            max_interval_seconds: float, 
            stddev_seconds: float, 
            total_points: int, 
            intervals: list of intervals in seconds,
            timestamp_list: list of timestamps (as timedelta objects)
        )
    """
    times = []
    intervals = []
    
    try:
        with open(file_path, 'r', errors='replace') as f:
            for line in f:
                line = line.strip()
                if line.startswith('B'):
                    time = parse_b_record_time(line)
                    if time:
                        times.append(time)
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return False, 0, 0, 0, 0, 0, []
    
    if len(times) < 2:
        return False, 0, 0, 0, 0, len(times), []
    
    # Calculate intervals between consecutive timestamps
    for i in range(1, len(times)):
        # Calculate time difference in seconds
        diff = (times[i] - times[i-1]).total_seconds()
        
        # Only add if positive (handles day crossover more safely)
        if diff > 0:
            intervals.append(diff)
    
    if not intervals:
        return False, 0, 0, 0, 0, len(times), []
    
    avg_interval = sum(intervals) / len(intervals)
    min_interval = min(intervals)
    max_interval = max(intervals)
    
    # Calculate standard deviation if we have more than one interval
    stddev = statistics.stdev(intervals) if len(intervals) > 1 else 0
      # Determine if the interval is fixed (allowing for small variations)
    # Consider interval fixed if standard deviation is less than 1 second
    is_fixed_interval = stddev < 1.0
    
    return (is_fixed_interval, avg_interval, min_interval, max_interval, 
            stddev, len(times), intervals, times)

def analyze_directory(dir_path):
    """
    Analyze all IGC files in a directory and report their logging intervals
    
    Args:
        dir_path: Path to the directory containing IGC files
    """
    print(f"\nAnalyzing IGC files in: {dir_path}\n")
    print("=" * 80)
    
    # Get all IGC files (case insensitive)
    igc_files = [f for f in os.listdir(dir_path) 
                if os.path.isfile(os.path.join(dir_path, f)) 
                and f.lower().endswith(('.igc', '.IGC'))]
    
    if not igc_files:
        print(f"No IGC files found in {dir_path}")
        return
    
    print(f"Found {len(igc_files)} IGC files\n")
    
    # Sort files by name
    igc_files.sort()
    for filename in igc_files:
        file_path = os.path.join(dir_path, filename)
        
        # Parse the header information first
        header_info = parse_igc_header(file_path)
        
        # Analyze the file
        (is_fixed, avg_interval, min_interval, max_interval, 
         stddev, total_points, intervals, times) = analyze_igc_file(file_path)
        
        print(f"File: {filename}, date: {header_info['dateYY']}-{header_info['dateMM']}-{header_info['dateDD']}")
        print(f"  Flight Recorder: {header_info['manufacturer']}, {header_info['device_model']}, {header_info['device_id']}")
        print(f"  Firmware: {header_info['device_FW']}")
        print(f"  Hardware: {header_info['device_HW']}")
        print(f"  Points logged: {total_points}")
        
        if total_points < 2:
            print("  Not enough points to determine interval")
            print("-" * 80)
            continue
            
        print(f"  Average interval: {format_time(avg_interval)}")
        if is_fixed:
            print(f"  Interval type: FIXED")
        else:
            print(f"  Interval type: VARIABLE")
            print(f"  Min interval: {format_time(min_interval)}")
            print(f"  Max interval: {format_time(max_interval)}")
              # Find significant variations
            if len(intervals) > 2 and 'times' in locals() and len(times) > 1:
                significant_variations = []
                prev_interval = intervals[0]
                prev_time = times[0]
                
                for i, interval in enumerate(intervals[1:], 1):
                    # If interval changes by more than 50% or 5 seconds (whichever is less)
                    change_threshold = min(prev_interval * 0.5, 5.0)
                    if abs(interval - prev_interval) > change_threshold and i < len(times):
                        current_time = times[i] if i < len(times) else times[-1]
                        significant_variations.append((i, prev_time, current_time, prev_interval, interval))
                    prev_interval = interval
                    if i < len(times):
                        prev_time = times[i]
                
                if significant_variations:
                    print("\n  Significant interval changes:")
                    for i, prev_time, current_time, prev, current in significant_variations[:5]:  # Show up to 5 changes
                        prev_time_str = f"{prev_time.seconds//3600:02d}:{(prev_time.seconds//60)%60:02d}:{prev_time.seconds%60:02d}"
                        curr_time_str = f"{current_time.seconds//3600:02d}:{(current_time.seconds//60)%60:02d}:{current_time.seconds%60:02d}"
                        print(f"    {prev_time_str}-{curr_time_str}: {format_time(prev)} → {format_time(current)}")
                    
                    if len(significant_variations) > 5:
                        print(f"    ... and {len(significant_variations) - 5} more changes")
        
        print("-" * 80)

def main():
    parser = argparse.ArgumentParser(
        description="Analyze IGC files to determine logging intervals")
    parser.add_argument("path", nargs="?", help="Path to directory containing IGC files")
    
    args = parser.parse_args()
    
    # If no path provided as command-line argument, prompt the user
    if args.path is None:
        dir_path = input("Enter the directory path containing IGC files: ").strip()
    else:
        dir_path = args.path
    
    # Remove quotes if present
    dir_path = dir_path.strip('"\'')
    
    if not os.path.exists(dir_path):
        print(f"Error: Directory '{dir_path}' does not exist")
        sys.exit(1)
    
    if not os.path.isdir(dir_path):
        print(f"Error: '{dir_path}' is not a directory")
        sys.exit(1)
        
    analyze_directory(dir_path)
    
    # Check if user wants to analyze subdirectories
    subdirs = [d for d in os.listdir(dir_path) 
              if os.path.isdir(os.path.join(dir_path, d))]
                
    print("\nAnalysis complete!")
    sys.exit(0)

if __name__ == "__main__":
    main()
