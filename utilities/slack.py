import os
import logging
import requests
import shutil
from dotenv import load_dotenv
import pandas as pd
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from googleapiclient.discovery import build
from google.oauth2 import service_account
from openai import OpenAI

load_dotenv()

client = OpenAI(
  api_key=os.environ.get("OPENAI_API_KEY"),
)

service_account_file = 'data/hr-test-project-422816-8532d5dd2659.json'

def translate_text_with_llm(text):
    response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Who won the world series in 2020?"},
        {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
        {"role": "user", "content": "Where was it played?"}
    ]
    )

def contains_russian_or_english(text):
    try:
        language = detect(text)
        return language in ["ru", "en"]
    except:
        return False

def upload_file(channel_id, file_path):
    client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
    filename = os.path.basename(file_path)
    print(file_path, "file_path")
    try:
        # Upload the file to a specific channel
        response = client.files_upload_v2(
            channel=channel_id,
            file=file_path,
            title="File Upload",
        )
        clear_directory('./temp_downloads')
        assert response["file"]  # The response contains information about the uploaded file
        return f"File uploaded successfully: {response['file']['name']}"
    except SlackApiError as e:
        return f"Error uploading file: {e.response['error']}"
    
def clear_directory(directory_path):
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.remove(file_path)
                print(f"Deleted {file_path}")
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
                print(f"Deleted directory {file_path}")
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')

def parse_and_style(text):
    lines = text.split('\n')
    requests = []
    index = 1  # Google Docs starts indexing from 1
    bullet_ranges = []

    for line in lines:
        if line.startswith('# '):
            content = line[2:].strip() + '\n'
            end_index = index + len(content)
            requests.append({
                'insertText': {
                    'location': {'index': index},
                    'text': content
                }
            })
            requests.append({
                'updateParagraphStyle': {
                    'range': {'startIndex': index, 'endIndex': end_index},
                    'paragraphStyle': {
                        'alignment': 'CENTER',
                        'namedStyleType': 'HEADING_1'
                    },
                    'fields': 'namedStyleType,alignment'
                }
            })
            index = end_index

        elif line.startswith('## '):
            content = line[3:].strip() + '\n'
            end_index = index + len(content)
            requests.append({
                'insertText': {
                    'location': {'index': index},
                    'text': content
                }
            })
            requests.append({
                'updateParagraphStyle': {
                    'range': {'startIndex': index, 'endIndex': end_index},
                    'paragraphStyle': {'namedStyleType': 'HEADING_3'},
                    'fields': 'namedStyleType'
                }
            })
            index = end_index

        elif line.startswith('- '):
            content = line[2:].strip() + '\n'
            end_index = index + len(content)
            requests.append({
                'insertText': {
                    'location': {'index': index},
                    'text': content
                }
            })
            # Record the range for bullet styling
            bullet_ranges.append((index, end_index))
            index = end_index

    # Apply bullet points to recorded ranges
    for start, end in bullet_ranges:
        requests.append({
            'createParagraphBullets': {
                'range': {'startIndex': start, 'endIndex': end},
                'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE'
            }
        })

    return requests

def create_google_doc(processed_data, service_account_file, is_anonymous=False):
    # Load the service account credentials
    creds = service_account.Credentials.from_service_account_file(
        service_account_file, scopes=['https://www.googleapis.com/auth/drive']
    )

    # Create a Drive API client
    drive_service = build('drive', 'v3', credentials=creds)

    # Create a Docs API client
    docs_service = build('docs', 'v1', credentials=creds)

    # Create a new Google Docs file
    doc_title = 'Processed Data (Anonymous)' if is_anonymous else 'Processed Data'
    doc_body = {
        'name': doc_title,
        'mimeType': 'application/vnd.google-apps.document',
        'parents': ["1Y7EcA6z21vuNB0PGL28QlkyrWpRMEV0G"],
    }
    doc = drive_service.files().create(body=doc_body).execute()
    doc_id = doc['id']

    print(doc_id, "===========doc_id============")

    requests = parse_and_style(processed_data)

    print(requests, "=========requests============")
    result = docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()

    # set_permissions(drive_service, doc_id, 'iwahtelt@gmail.com')

    print(f"Google Docs file created: {doc_title}")
    print(f"File ID: {doc_id}")
    print(f"File URL: https://docs.google.com/document/d/{doc_id}")

def set_permissions(service, file_id, user_email):
    permissions = {
        'type': 'user',
        'role': 'writer',
        'emailAddress': user_email
    }
    service.permissions().create(
        fileId=file_id,
        body=permissions,
        fields='id'
    ).execute()

def process_files(file_paths, is_anonymous=False):
    data = ""
    excluded_columns = ["Respondent number", "Timestamp", "Email Address", "Respondent signature"]
    processed_columns = set()

    for file_path in file_paths:
        # Get the file name without the extension
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        
        # Read the CSV file using pandas
        df = pd.read_csv(file_path)
        
        # Add the section marker and file name
        data += f"# {file_name}\n\n"
        
        # Iterate over the columns
        for column in df.columns:
            if column not in excluded_columns:
                # Check if the column is repetitive
                base_column = column.split("[")[0].strip()
                if base_column in processed_columns:
                    continue
                
                processed_columns.add(base_column)
                
                # Add the paragraph marker and column name (without brackets)
                data += f"## {base_column}\n"
                
                # Iterate over the rows in the current column
                for index, value in enumerate(df[column]):
                    if pd.isna(value):
                        # Add an empty string for NaN values
                        data += "\n"
                    else:
                        # Check if the column is repetitive
                        if "[" in column and "]" in column:
                            data += "- [Chart_Placeholder]\n"
                        else:
                            # Add the row value and respondent signature (if available and not anonymous)
                            if not is_anonymous and "Respondent signature" in df.columns:
                                signature = df.loc[index, "Respondent signature"]
                                if pd.isna(signature):
                                    data += f"- {value}\n"
                                else:
                                    data += f"- {value} {signature}\n"
                            else:
                                data += f"- {value}\n"
                
                data += "\n"  # Add a newline after each paragraph
        
        data += "\n"  # Add a newline after each section
    
    create_google_doc(data, service_account_file, is_anonymous)

def download_files(files, files_data):
    file_paths = []
    download_dir = "./temp_downloads"
    os.makedirs(download_dir, exist_ok=True)
    
    for file_info in files:
        # Check the file type for security
        logging.info(f"Received file type: {file_info['filetype']}")
        file_url = file_info["url_private"]
        file_name = file_info["name"]
        
        local_file_path = os.path.join(download_dir, file_name)
        file_paths.append(local_file_path)
        
        # Download the file
        headers = {"Authorization": f"Bearer {os.environ.get('SLACK_BOT_TOKEN')}"}
        response = requests.get(file_url, headers=headers, stream=True)
        
        if response.status_code == 200:
            with open(local_file_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            logging.info(f"File downloaded: {local_file_path}")
        else:
            logging.error(f"Failed to download file: {file_url}")
    
    # Process and send the non-anonymous version of the document
    process_files(file_paths, is_anonymous=False)

    # Process and send the anonymous version of the document
    process_files(file_paths, is_anonymous=True)

    # Delete the temporary downloaded files
    clear_directory('./temp_downloads')