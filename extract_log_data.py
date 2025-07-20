import re
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import os
import glob

class LogExtractor:
    """Generic log file extractor for structured log data"""
    
    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path
        self.timestamps = []
        self.log_entries = []
        
    def extract_timestamps(self) -> List[str]:
        """Extract all timestamps from the log file"""
        timestamp_patterns = [
            r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'         # 2025-07-15 21:09:07
        ]
        
        timestamps = []
        
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as file:
                for line_num, line in enumerate(file, 1):
                    for pattern in timestamp_patterns:
                        matches = re.findall(pattern, line)
                        for match in matches:
                            timestamps.append({
                                'timestamp': match,
                                'line_number': line_num,
                                'full_line': line.strip()
                            })
                            break  
                            
        except FileNotFoundError:
            print(f"Error: File '{self.log_file_path}' not found.")
            return []
        except Exception as e:
            print(f"Error reading file: {e}")
            return []
            
        return timestamps
    
    def get_start_end_times(self) -> Tuple[Optional[str], Optional[str]]:
        """Get the first and last timestamps from the log"""
        timestamps = self.extract_timestamps()
        
        if not timestamps:
            return None, None
            
        start_time = timestamps[0]['timestamp']
        end_time = timestamps[-1]['timestamp']
        
        return start_time, end_time
    
    def extract_log_data(self) -> Dict:
        """Extract comprehensive log data including timestamps and metadata"""
        timestamps = self.extract_timestamps()
        
        if not timestamps:
            return {
                'start_time': None,
                'end_time': None,
                'total_lines': 0,
                'duration': None,
                'build_status': 'fail',
            }
        
        start_time = timestamps[0]['timestamp']
        end_time = timestamps[-1]['timestamp']
        
        duration = self._calculate_duration(start_time, end_time)
        
        app_build_status = 'success' if timestamps[-1]['full_line'].startswith("App is running on") else 'fail'
        
        return {
            'start_time': start_time,
            'end_time': end_time,
            'duration': duration,
            'build_status': app_build_status,
        }
    
    def _calculate_duration(self, start_time: str, end_time: str) -> Optional[str]:
        """Calculate duration between start and end times"""
        try:
            formats = [
                '%Y-%m-%d %H:%M:%S'
            ]
            
            start_dt = None
            end_dt = None
            
            for fmt in formats:
                try:
                    start_dt = datetime.strptime(start_time, fmt)
                    break
                except ValueError:
                    continue
                    
            for fmt in formats:
                try:
                    end_dt = datetime.strptime(end_time, fmt)
                    break
                except ValueError:
                    continue
            
            if start_dt and end_dt:
                duration = end_dt - start_dt
                total_seconds = int(duration.total_seconds())
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                return f"{minutes}min {seconds:02d}sec"
            else:
                return "Could not parse timestamps"
                
        except Exception as e:
            return f"Error calculating duration: {e}"
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert extracted timestamps to pandas DataFrame"""
        timestamps = self.extract_timestamps()
        
        if not timestamps:
            return pd.DataFrame()
            
        df = pd.DataFrame(timestamps)
        
        try:
            df['datetime'] = pd.to_datetime(df['timestamp'], errors='coerce')
        except Exception:
            pass
            
        return df
    
    def save_to_csv(self, output_file: str = None) -> str:
        """Save extracted data to CSV file"""
        if output_file is None:
            base_name = os.path.splitext(os.path.basename(self.log_file_path))[0]
            output_file = f"{base_name}_extracted.csv"
        
        df = self.to_dataframe()
        
        if df.empty:
            print("No data to save.")
            return ""
            
        df.to_csv(output_file, index=False)
        print(f"Data saved to {output_file}")
        return output_file

def process_folder_logs(source_folder: str, destination_folder: str) -> pd.DataFrame:
    """
    Process all log files in a source folder and create a summary CSV in the destination folder.
    
    Args:
        source_folder: Path to folder containing log files
        destination_folder: Path to folder where summary CSV will be saved (defaults to source_folder)
    
    Returns:
        DataFrame with summary of all log files
    """
    
    if not os.path.exists(source_folder):
        print(f"Error: Source folder '{source_folder}' does not exist.")
        return pd.DataFrame()
    
    if destination_folder is None:
        destination_folder = source_folder
    
    if not os.path.exists(destination_folder):
        try:
            os.makedirs(destination_folder)
            print(f"Created destination folder: {destination_folder}")
        except Exception as e:
            print(f"Error creating destination folder '{destination_folder}': {e}")
            return pd.DataFrame()
    
    # Find all log files in the source folder
    log_files = glob.glob(os.path.join(source_folder, "*.log"))
    
    if not log_files:
        print(f"No log files found in {source_folder}")
        return pd.DataFrame()
    
    print(f"Found {len(log_files)} log files in {source_folder}")
    
    results = []
    
    for log_file in sorted(log_files):
        print(f"Processing: {os.path.basename(log_file)}")
        
        extractor = LogExtractor(log_file)
        log_data = extractor.extract_log_data()
        
        filename = os.path.basename(log_file)
    
        prompt_id = os.path.splitext(filename)[0].split('_')[1]   # Assuming filename format is like "prompt_1.log"
        
        result = {
            'prompt_id': prompt_id,
            'log_file': filename,
            'start_time': log_data['start_time'],
            'end_time': log_data['end_time'],
            'gen_time': log_data['duration'],
            'build_status': log_data['build_status'],
        }
        
        results.append(result)

    df = pd.DataFrame(results)
    
    df['prompt_id'] = pd.to_numeric(df['prompt_id'], errors='coerce').astype('Int64')
    
    folder_name = os.path.basename(source_folder.rstrip('/\\'))
    output_csv = f"{folder_name}_summary.csv"
    
    output_path = os.path.join(destination_folder, output_csv)
    
    df.to_csv(output_path, index="False")
    print(f"\nSummary saved to: {output_path}")
    print(f"Processed {len(df)} log files")
    
    return df


def process_logs(source_loc, destination_loc):
    '''
    Process all log folders in the source location and create a summary DataFrame.
    
    Args:
        source_loc: Path to folder containing log files
        destination_loc: Path to folder where summary CSV will be saved (defaults to source_folder)
        
    Returns:
        DataFrame with summary of all log files
    '''
    log_folders = os.listdir(source_loc) if os.path.exists(source_loc) else []
    results = []

    for log_folder in log_folders:

        source_folder_loc = os.path.join(source_loc, log_folder)  # Use the first folder for processing

        print("="*60)
        print(f"PROCESSING FOLDER: {source_folder_loc}")
        print("="*60)

        df_summary = process_folder_logs(source_folder_loc, destination_loc)
        df_summary["config"] = log_folder
        results.append(df_summary)
        
    results = pd.concat(results, ignore_index=True)
    return results