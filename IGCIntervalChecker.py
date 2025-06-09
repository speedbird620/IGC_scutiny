# Script to analyze IGC files and check their logging intervals
#
# Copyright (C) 2025 Skyracer.net
# 
# This software is a GNU General Public License (GPL) project.
#
# Rev 1.0 - Initial version
#

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
            total_points: int, 
            intervals: list of (time1, time2, interval) tuples
        )
    """
    times = []
    interval_details = []
    
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
        return False, 0, 0, 0, 0, []
    
    if len(times) < 2:
        return False, 0, 0, 0, len(times), []
    
    # Calculate intervals between consecutive timestamps with their corresponding times
    for i in range(1, len(times)):
        # Calculate time difference in seconds
        diff = (times[i] - times[i-1]).total_seconds()
        
        # Only add if positive (handles day crossover more safely)
        if diff > 0:
            interval_details.append((times[i-1], times[i], diff))
    
    if not interval_details:
        return False, 0, 0, 0, len(times), []
    
    # Extract just the interval values for calculations
    intervals = [item[2] for item in interval_details]
    
    avg_interval = sum(intervals) / len(intervals)
    min_interval = min(intervals)
    max_interval = max(intervals)
    
    # Calculate standard deviation if we have more than one interval
    stddev = statistics.stdev(intervals) if len(intervals) > 1 else 0
    
    # Determine if the interval is fixed (allowing for small variations)
    # Consider interval fixed if standard deviation is less than 1 second
    is_fixed_interval = stddev < 1.0
    
    return is_fixed_interval, avg_interval, min_interval, max_interval, len(times), interval_details

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
        
        # Analyze the file
        (is_fixed, avg_interval, min_interval, max_interval, 
         total_points, interval_details) = analyze_igc_file(file_path)
        
        print(f"File: {filename}")
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
            if len(interval_details) > 2:
                significant_variations = []
                prev_interval = interval_details[0][2]
                
                for i, (time1, time2, interval) in enumerate(interval_details[1:], 1):
                    # If interval changes by more than 50% or 5 seconds (whichever is less)
                    change_threshold = min(prev_interval * 0.5, 5.0)
                    if abs(interval - prev_interval) > change_threshold:
                        significant_variations.append((time1, time2, prev_interval, interval))
                    prev_interval = interval
                
                if significant_variations:
                    print("\n  Significant interval changes:")
                    for time1, time2, prev, current in significant_variations[:5]:  # Show up to 5 changes
                        time1_str = format_timedelta(time1)
                        time2_str = format_timedelta(time2)
                        print(f"    {time1_str}-{time2_str}: {format_time(prev)} → {format_time(current)}")
                    
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
    
    if subdirs:
        analyze_subdirs = input(f"\nFound {len(subdirs)} subdirectories. Analyze them too? (y/n): ")
        if analyze_subdirs.lower() in ('y', 'yes'):
            for subdir in subdirs:
                analyze_directory(os.path.join(dir_path, subdir))
                
    print("\nAnalysis complete!")
    sys.exit(0)

if __name__ == "__main__":
    main()

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
        
        # Analyze the file
        (is_fixed, avg_interval, min_interval, max_interval, 
         stddev, total_points, intervals) = analyze_igc_file(file_path)
        
        print(f"File: {filename}")
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
            if len(intervals) > 2:
                significant_variations = []
                prev_interval = intervals[0]
                prev_time = times[0]
                
                for i, interval in enumerate(intervals[1:], 1):
                    # If interval changes by more than 50% or 5 seconds (whichever is less)
                    change_threshold = min(prev_interval * 0.5, 5.0)
                    if abs(interval - prev_interval) > change_threshold:
                        current_time = times[i] if i < len(times) else times[-1]
                        significant_variations.append((i, prev_time, current_time, prev_interval, interval))
                    prev_interval = interval
                    prev_time = times[i] if i < len(times) else times[-1]
                
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
    
    if subdirs:
        analyze_subdirs = input(f"\nFound {len(subdirs)} subdirectories. Analyze them too? (y/n): ")
        if analyze_subdirs.lower() in ('y', 'yes'):
            for subdir in subdirs:
                analyze_directory(os.path.join(dir_path, subdir))
                
    print("\nAnalysis complete!")
    sys.exit(0)

if __name__ == "__main__":
    main()
