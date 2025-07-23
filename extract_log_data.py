import re
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import os
import glob

class LogExtractor:
    """Extract structured data from log files."""

    TIMESTAMP_PATTERN = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
    TOKEN_PATTERN = re.compile(
        r"Provider: ([^|]+) \| Model: ([^|]+) \| Input tokens: (\d+) \| Output tokens: (\d+) \| Total tokens: (\d+)",
        re.IGNORECASE
    )

    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path
        self.lines = self._read_file()

    def _read_file(self) -> List[str]:
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                return f.readlines()
        except FileNotFoundError:
            print(f"Error: File not found: {self.log_file_path}")
            return []
        except Exception as e:
            print(f"Error reading file {self.log_file_path}: {e}")
            return []

    def extract_timestamps(self) -> Tuple[List[Dict], bool, bool, bool]:
        timestamps = []
        assertion_error = False
        emoji_message = False
        deployed_message = False

        for line_num, line in enumerate(self.lines, 1):
            matches = re.findall(self.TIMESTAMP_PATTERN, line)
            if line.strip().startswith("AssertionError"):
                assertion_error = True
            elif line.strip().startswith("App is running on"):
                deployed_message = True
            if line.strip().endswith("Last user message: [TextRaw(text='Add message with emojis to the app to make it more fun')]"):
                emoji_message = True

            for match in matches:
                timestamps.append({
                    'timestamp': match,
                    'line_number': line_num,
                    'full_line': line.strip()
                })
                break  # Only first timestamp per line

        return timestamps, deployed_message, assertion_error and emoji_message

    def extract_provider_token_data(self) -> Dict[str, int]:
        """Extract token usage data for Anthropic Claude from the log lines."""
        provider_data = {}

        for line in self.lines:
            match = self.TOKEN_PATTERN.search(line)
            if match:
                provider = match.group(1).strip()
                input_tokens = int(match.group(3))
                output_tokens = int(match.group(4))
                total_tokens = int(match.group(5))

                if provider not in provider_data:
                    provider_data[provider] = {
                        'input_tokens': 0,
                        'output_tokens': 0,
                        'total_tokens': 0,
                        'api_calls': 0
                    }

                provider_data[provider]['input_tokens'] += input_tokens
                provider_data[provider]['output_tokens'] += output_tokens
                provider_data[provider]['total_tokens'] += total_tokens
                provider_data[provider]['api_calls'] += 1

        return provider_data

    def _calculate_duration(self, start_time: str, end_time: str) -> Optional[str]:
        try:
            fmt = '%Y-%m-%d %H:%M:%S'
            start_dt = datetime.strptime(start_time, fmt)
            end_dt = datetime.strptime(end_time, fmt)
            duration = end_dt - start_dt
            minutes, seconds = divmod(int(duration.total_seconds()), 60)
            return f"{minutes}min {seconds:02d}sec"
        except Exception as e:
            print(f"Warning: Could not calculate duration: {e}")
            return None

    def extract_log_data(self) -> Dict:
        timestamps, deployed, post_build_error = self.extract_timestamps()
        token_data = self.extract_provider_token_data()

        if not timestamps:
            return {
                'start_time': None,
                'end_time': None,
                'duration': None,
                'build_status': None,
                'post_build_error': None,
                'token_data': None
            }
        
        if 'Stopping Docker containers' in timestamps[-1]['full_line']:
            timestamps.pop()
        
        start_time = timestamps[0]['timestamp']
        end_time = timestamps[-1]['timestamp']
        
        print(end_time)
        
        duration = self._calculate_duration(start_time, end_time)
        build_status = 'success' if deployed and not post_build_error else 'fail'

        return {
            'start_time': start_time,
            'end_time': end_time,
            'duration': duration,
            'build_status': build_status,
            'post_build_error': post_build_error,
            'token_data': token_data
        }

    def to_dataframe(self) -> pd.DataFrame:
        timestamps, _, _ = self.extract_timestamps()
        if not timestamps:
            return pd.DataFrame()
        df = pd.DataFrame(timestamps)
        df['datetime'] = pd.to_datetime(df['timestamp'], errors='coerce')
        return df

    def save_to_csv(self, output_file: Optional[str] = None) -> str:
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


def process_folder_logs(source_folder: str, destination_folder: Optional[str]) -> pd.DataFrame:
    if not os.path.exists(source_folder):
        print(f"Error: Source folder '{source_folder}' does not exist.")
        return pd.DataFrame()

    if destination_folder is None:
        destination_folder = source_folder

    os.makedirs(destination_folder, exist_ok=True)

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
        try:
            prompt_id = int(os.path.splitext(filename)[0].split('_')[1])
        except (IndexError, ValueError):
            prompt_id = None

        result = {
            'prompt_id': prompt_id,
            'log_file': filename,
            'start_time': log_data['start_time'],
            'end_time': log_data['end_time'],
            'gen_time': log_data['duration'],
            'build_status': log_data['build_status'],
            'post_build_error': log_data['post_build_error'],
        }

        # Flatten token data
        token_data = log_data.get('token_data', {})
        total_api_calls = 0

        if isinstance(token_data, dict):
            for key, value in token_data.items():
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        col_name = f"{key.lower().replace(' ', '_')}_{sub_key}"
                        result[col_name] = sub_value
                        if sub_key == 'api_calls':
                            total_api_calls += sub_value
                else:
                    result[key] = value

        result['total_api_calls'] = total_api_calls

        results.append(result)

    df = pd.DataFrame(results)
    df['prompt_id'] = pd.to_numeric(df['prompt_id'], errors='coerce').astype('Int64')

    folder_name = os.path.basename(source_folder.rstrip('/\\'))
    output_csv = f"{folder_name}_summary.csv"
    output_path = os.path.join(destination_folder, output_csv)

    df.to_csv(output_path, index=False)
    print(f"Summary saved to: {output_path}")
    print(f"Processed {len(df)} log files")

    return df


def process_logs(source_loc: str, destination_loc: Optional[str]) -> pd.DataFrame:
    if not os.path.exists(source_loc):
        print(f"Error: Source location '{source_loc}' does not exist.")
        return pd.DataFrame()

    log_folders = [f for f in os.listdir(source_loc) if os.path.isdir(os.path.join(source_loc, f))]
    results = []

    for log_folder in log_folders:
        source_folder_loc = os.path.join(source_loc, log_folder)
        print("="*60)
        print(f"PROCESSING FOLDER: {source_folder_loc}")
        print("="*60)

        df_summary = process_folder_logs(source_folder_loc, destination_loc)
        df_summary["config"] = log_folder
        results.append(df_summary)

    if results:
        return pd.concat(results, ignore_index=True)
    else:
        return pd.DataFrame()