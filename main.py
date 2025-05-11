#!/usr/bin/env python3

import os
import sys
import json
import base64
import subprocess
from datetime import datetime
from dotenv import load_dotenv
import requests
import re # For filename parsing

# Script to convert Supernote .note files to PDF and use Gemini API for handwriting recognition.
# Processes .note files from a specified input directory, generates markdown,
# saves to an Obsidian daily notes structure, and tracks processed files in a log.
# Finally, commits changes to the Obsidian directory using Git.

# Before first use (especially for systemd):
# 1. Ensure supernote-tool is installed and accessible.
# 2. Set SUPERNOTE_TOOL_PATH environment variable (system-wide or in .env).
# 3. Store Gemini API key in ~/.api_keys/gemini_key.
# 4. Initialize ../notas/Diarias as a Git repository.
# 5. CRITICAL FOR SYSTEMD/NON-INTERACTIVE GIT PUSH:
#    Configure SSH key-based authentication for Git with your remote repository (e.g., GitHub).
#    The script CANNOT handle password prompts.
#    - Generate SSH key for the user the service runs as.
#    - Add public key to your Git provider.
#    - Ensure Git remote URL is SSH (git@github.com:user/repo.git).
#    See: https://docs.github.com/en/authentication
# 6. A '.processed_supernotes.log' file will be created in PROJECT_ROOT to track processed files.

# Load environment variables from the .env file
# .env file can be in the script's directory or PROJECT_ROOT
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR) # Assumes script is in a subfolder of project root

env_path_script_dir = os.path.join(SCRIPT_DIR, '.env')
env_path_project_root = os.path.join(PROJECT_ROOT, '.env')

if os.path.exists(env_path_script_dir):
    load_dotenv(dotenv_path=env_path_script_dir)
    print(f"Loaded .env from script directory: {env_path_script_dir}")
elif os.path.exists(env_path_project_root):
    load_dotenv(dotenv_path=env_path_project_root)
    print(f"Loaded .env from project root: {env_path_project_root}")
else:
    load_dotenv() # Tries default locations
    print("Attempting to load .env from default locations (if any).")


# --- Configuration ---
SUPERNOTE_TOOL_PATH = os.getenv("SUPERNOTE_TOOL_PATH")
if SUPERNOTE_TOOL_PATH:
    if SUPERNOTE_TOOL_PATH not in os.environ["PATH"]:
      os.environ["PATH"] = f"{SUPERNOTE_TOOL_PATH}:{os.environ['PATH']}"
    print(f"Using SUPERNOTE_TOOL_PATH: {SUPERNOTE_TOOL_PATH}")
else:
    print("Warning: SUPERNOTE_TOOL_PATH environment variable is not set.")
    print("The script will attempt to use 'supernote-tool' from the system PATH.")

try:
    GOOGLE_API_KEY = open(os.path.expanduser("~/.api_keys/gemini_key")).read().strip()
except FileNotFoundError:
    print("Error: API key file ~/.api_keys/gemini_key not found.")
    sys.exit(1)
if not GOOGLE_API_KEY:
    print("Error: GOOGLE_API_KEY is empty. Check ~/.api_keys/gemini_key.")
    sys.exit(1)

GEMINI_MODEL = "gemini-2.0-flash" # As per user request
GEMINI_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GOOGLE_API_KEY}"

SUPERNOTE_INPUT_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "Drive", "Supernote", "Note"))
OBSIDIAN_OUTPUT_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "notas", "Diarias"))
OBSIDIAN_ATTACHMENTS_SUBDIR_NAME = "attachments" # PDFs will be saved here but not linked
PROCESSED_LOG_FILE = os.path.join(PROJECT_ROOT, ".processed_supernotes.log")


# --- Helper Functions ---
def load_processed_files(log_file_path):
    """Loads the set of already processed filenames from the log file."""
    processed = set()
    try:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                processed.add(line.strip())
        print(f"Loaded {len(processed)} processed file entries from {log_file_path}")
    except FileNotFoundError:
        print(f"Processed log file not found: {log_file_path}. Will create a new one.")
    except Exception as e:
        print(f"Error loading processed log file {log_file_path}: {e}")
    return processed

def add_to_processed_log(filename, log_file_path):
    """Appends a successfully processed filename to the log file."""
    try:
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(f"{filename}\n")
        print(f"Added '{filename}' to processed log: {log_file_path}")
        return True
    except Exception as e:
        print(f"Error writing to processed log file {log_file_path} for {filename}: {e}")
        return False

def run_git_command(command, cwd):
    """Runs a Git command and handles errors."""
    try:
        print(f"Running Git command: {' '.join(command)} in {cwd}")
        process = subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)
        print(f"Git command successful. Output:\n{process.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running Git command {' '.join(command)}:")
        print(f"Return code: {e.returncode}")
        if e.stdout: print(f"Stdout: {e.stdout}")
        if e.stderr: print(f"Stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"Error: Git command not found. Ensure Git is installed and in PATH.")
        return False

# --- Main Processing Logic ---
def main():
    print(f"Input Supernote directory: {SUPERNOTE_INPUT_DIR}")
    print(f"Output Obsidian directory: {OBSIDIAN_OUTPUT_DIR}")
    print(f"Processed files log: {PROCESSED_LOG_FILE}")
    print(f"Gemini Model: {GEMINI_MODEL}")
    print("Note: PDFs will be saved to the attachments folder but NOT linked in markdown.")
    print("Note: Original .note files will NOT be moved.")

    already_processed_files = load_processed_files(PROCESSED_LOG_FILE)

    if not os.path.isdir(SUPERNOTE_INPUT_DIR):
        print(f"Error: Supernote input directory does not exist: {SUPERNOTE_INPUT_DIR}")
        sys.exit(1)

    os.makedirs(OBSIDIAN_OUTPUT_DIR, exist_ok=True)
    obsidian_attachments_dir_path = os.path.join(OBSIDIAN_OUTPUT_DIR, OBSIDIAN_ATTACHMENTS_SUBDIR_NAME)
    os.makedirs(obsidian_attachments_dir_path, exist_ok=True)

    all_note_files_in_dir = []
    for filename_in_dir in os.listdir(SUPERNOTE_INPUT_DIR):
        if os.path.isfile(os.path.join(SUPERNOTE_INPUT_DIR, filename_in_dir)):
            match = re.match(r"(\d{8})_(\d{6})\.note", filename_in_dir)
            if match:
                all_note_files_in_dir.append(filename_in_dir)
    
    files_to_process = [
        f for f in all_note_files_in_dir if f not in already_processed_files
    ]
    
    if not files_to_process:
        print("No new .note files found to process (or all found files already processed).")
        sys.exit(0)

    print(f"Found {len(files_to_process)} new .note file(s) to process.")

    processed_dates_for_commit = set()
    any_file_processed_successfully_this_run = False
    newly_processed_count = 0

    for filename in files_to_process:
        try:
            print(f"\nProcessing file: {filename}...")
            input_file_path = os.path.join(SUPERNOTE_INPUT_DIR, filename)
            
            match = re.match(r"(\d{8})_(\d{6})\.note", filename)
            if not match: continue # Should be caught by initial filter

            date_part_str = match.group(1)
            time_part_str = match.group(2)

            date_obj = datetime.strptime(date_part_str, "%Y%m%d")
            year_str = date_obj.strftime("%Y")
            month_str = date_obj.strftime("%m")
            day_str = date_obj.strftime("%d")

            obsidian_md_filename = f"{year_str}-{month_str}-{day_str}.md"
            obsidian_md_file_path = os.path.join(OBSIDIAN_OUTPUT_DIR, obsidian_md_filename)

            pdf_filename = f"{year_str}-{month_str}-{day_str}_supernote_{time_part_str}.pdf"
            pdf_path = os.path.join(obsidian_attachments_dir_path, pdf_filename)

            print(f"Date detected: {year_str}-{month_str}-{day_str}")
            print(f"Target Obsidian file: {obsidian_md_file_path}")
            print(f"Target PDF file (will be saved but not linked): {pdf_path}")
            
            print(f"Converting {filename} to PDF...")
            subprocess.run(
                ["supernote-tool", "convert", "-t", "pdf", "-a", input_file_path, pdf_path], 
                check=True, capture_output=True
            )
            print("✓ PDF conversion successful.")

            print("Sending PDF to Gemini API for handwriting recognition...")
            with open(pdf_path, "rb") as pdf_file:
                pdf_base64 = base64.b64encode(pdf_file.read()).decode('utf-8')

            json_request = {
                "contents": [{
                    "parts": [
                        {
                            "text": (
                                "- Recognize the handwriting and other content in this image.\n"
                                "- Convert it to organized markdown format. The markdown output itself should NOT be enclosed in triple backticks (```markdown ... ``` or ``` ... ```).\n"
                                "- Preserve headings, lists, list indentation, horizontal rules, tables, blockquotes, and other structures.\n"
                                "- Underlined text on its own line should be a H3 header in markdown, prefixed with: ### \n"
                                "- For text written in ALL CAPS, convert to traditional capitalization (sentence case or proper nouns as appropriate).\n"
                                "- A task is text in the image that has 'AI' in a circle to the left of it. Represent this as a markdown task: - [ ] task text. For example: - [ ] action item text\n"
                                "- For any text that is highlighted in the image, add == before and after the highlighted text, with no space between the == and the highlighted text on either end. For example: ==highlighted text==\n"
                                "- Text with one asterisk before and after it should be maintained as markdown italic. For example: *italic text here*\n"
                                "- Text with two asterisks before and after it should be maintained as markdown bold. For example: **bold text here**\n"
                                "- Text with three asterisks before and after it should be maintained as markdown bold italics. For example ***very important text***\n"
                                "- Blockquotes in the image will have a > symbol to the left and should be maintained as markdown blockquote. For example: > blockquote text"
                            )
                        },
                        {
                            "inline_data": {
                                "mime_type": "application/pdf",
                                "data": pdf_base64
                            }
                        }
                    ]
                }]
            }
            
            response = requests.post(GEMINI_ENDPOINT, json=json_request, timeout=180)
            response.raise_for_status()
            response_json = response.json()

            if not response_json.get('candidates') or \
               not response_json['candidates'][0].get('content') or \
               not response_json['candidates'][0]['content'].get('parts') or \
               not response_json['candidates'][0]['content']['parts'][0].get('text'):
                print(f"Error: Could not extract text from Gemini API response for {filename}.")
                print(f"API Response: {json.dumps(response_json, indent=2)}")
                raise ValueError("Invalid API response structure")

            markdown_content = response_json['candidates'][0]['content']['parts'][0]['text']
            print("✓ Text extracted successfully from API.")

            entry_block = f"\n{markdown_content.strip()}\n"
            supernote_header_text = "## ✨ Supernote"

            os.makedirs(os.path.dirname(obsidian_md_file_path), exist_ok=True)

            if not os.path.isfile(obsidian_md_file_path):
                with open(obsidian_md_file_path, 'w', encoding='utf-8') as f:
                    f.write(f"{supernote_header_text}\n")
                    f.write(entry_block.lstrip('\n'))
                print(f"✓ Created new Obsidian file with Supernote entry: {obsidian_md_file_path}")
            else:
                with open(obsidian_md_file_path, 'r+', encoding='utf-8') as f:
                    content = f.read()
                    f.seek(0, 2) 
                    if supernote_header_text not in content:
                        separator = "\n\n" if content and not content.endswith('\n') else "\n"
                        if not content.endswith('\n\n') and content.endswith('\n'): separator = "\n"
                        if not content: separator = ""

                        f.write(separator)
                        f.write(f"{supernote_header_text}\n")
                        f.write(entry_block.lstrip('\n'))
                        print(f"✓ Added Supernote header and entry to: {obsidian_md_file_path}")
                    else:
                        if content and not content.endswith('\n'):
                            f.write('\n')
                        f.write(entry_block.lstrip('\n'))
                        print(f"✓ Appended entry to Supernote section in {obsidian_md_file_path}")
            
            # Log as processed *after* successful Obsidian update
            if add_to_processed_log(filename, PROCESSED_LOG_FILE):
                already_processed_files.add(filename) # Update in-memory set
            else:
                # If logging fails, it's a problem, but we might have already modified Obsidian.
                # Decide on rollback or just warning. For now, a strong warning.
                print(f"CRITICAL WARNING: Failed to log {filename} as processed. It might be reprocessed next run.")

            processed_dates_for_commit.add(f"{year_str}-{month_str}-{day_str}")
            any_file_processed_successfully_this_run = True
            newly_processed_count += 1
            print(f"✅ Successfully processed {filename}")

        except subprocess.CalledProcessError as e:
            print(f"❌ Error during PDF conversion for {filename}: {e.stderr.decode(errors='ignore') if e.stderr else e}")
        except requests.exceptions.RequestException as e:
            print(f"❌ HTTP/Network Error during API call for {filename}: {e}")
            if e.response is not None:
                print(f"API Response Status: {e.response.status_code}")
                try:
                    print(f"API Response Body: {e.response.json()}")
                except json.JSONDecodeError:
                    print(f"API Response Body: {e.response.text}")
        except (KeyError, IndexError, ValueError) as e:
            print(f"❌ Error parsing API response or invalid data for {filename}: {e}")
        except Exception as e:
            print(f"❌ An unexpected error occurred while processing {filename}: {e}")
            import traceback
            traceback.print_exc()
    
    if processed_dates_for_commit: # Only attempt Git if new content was added
        print("\nPerforming Git operations...")
        commit_message = f"Update daily notes from Supernote for dates: {', '.join(sorted(list(processed_dates_for_commit)))}"
        
        git_check_command = ["git", "rev-parse", "--is-inside-work-tree"]
        is_git_repo = False
        try:
            result = subprocess.run(git_check_command, cwd=OBSIDIAN_OUTPUT_DIR, check=True, capture_output=True, text=True)
            if result.stdout.strip() == "true":
                is_git_repo = True
                print(f"{OBSIDIAN_OUTPUT_DIR} is a Git repository.")
        except (subprocess.CalledProcessError, FileNotFoundError):
             print(f"Warning: {OBSIDIAN_OUTPUT_DIR} is not a Git repository or git command failed. Skipping Git operations.")

        if is_git_repo:
            if run_git_command(["git", "add", "."], cwd=OBSIDIAN_OUTPUT_DIR):
                status_result = subprocess.run(["git", "status", "--porcelain"], cwd=OBSIDIAN_OUTPUT_DIR, capture_output=True, text=True)
                if status_result.stdout.strip():
                    if run_git_command(["git", "commit", "-m", commit_message], cwd=OBSIDIAN_OUTPUT_DIR):
                        run_git_command(["git", "push"], cwd=OBSIDIAN_OUTPUT_DIR)
                else:
                    print("No changes to commit in the Git repository.")
    elif files_to_process: # Files were found, but none successfully processed
         print("\nNo files were successfully processed this run to trigger Git operations.")

    print("\n--- Script Summary ---")
    print(f"Total .note files found in directory: {len(all_note_files_in_dir)}")
    print(f"Files already processed (from log): {len(already_processed_files) - newly_processed_count}") # Adjust for those processed this run
    print(f"New files attempted this run: {len(files_to_process)}")
    print(f"Successfully processed this run: {newly_processed_count}")
    print(f"Failed to process this run: {len(files_to_process) - newly_processed_count}")

    if not any_file_processed_successfully_this_run and files_to_process:
        print("Script finished with errors: No new files were successfully processed this run.")
        sys.exit(1)
    elif newly_processed_count < len(files_to_process) and files_to_process:
        print("Script finished with partial success: Some new files could not be processed this run.")
        sys.exit(0) 
    else:
        print("✅ Script finished successfully.")
        sys.exit(0)

if __name__ == "__main__":
    main()

