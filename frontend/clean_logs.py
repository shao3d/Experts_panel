#!/usr/bin/env python3
"""
Log cleanup utility for Experts Panel
"""

import os
import glob
import argparse
from datetime import datetime, timedelta

def clean_logs(log_dir, max_days=7, max_files=5):
    """Clean old log files"""
    
    # Находим все .log файлы
    log_files = glob.glob(os.path.join(log_dir, "*.log*"))
    
    # Сортируем по времени модификации
    log_files.sort(key=os.path.getmtime, reverse=True)
    
    print(f"Found {len(log_files)} log files in {log_dir}")
    
    # Удаляем старые файлы
    cutoff_date = datetime.now() - timedelta(days=max_days)
    deleted_count = 0
    
    for log_file in log_files:
        file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
        
        if file_time < cutoff_date or len(log_files) > max_files:
            os.remove(log_file)
            deleted_count += 1
            print(f"Deleted: {log_file} (old: {file_time})")
    
    print(f"Deleted {deleted_count} log files")
    print(f"Keeping recent {min(len(log_files), max_files)} files")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean old log files")
    parser.add_argument("--dir", default=".", help="Log directory")
    parser.add_argument("--days", type=int, default=7, help="Max days to keep")
    parser.add_argument("--files", type=int, default=5, help="Max files to keep")
    
    args = parser.parse_args()
    clean_logs(args.dir, args.days, args.files)
