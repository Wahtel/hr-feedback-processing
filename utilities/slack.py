import os
import logging
import requests
import shutil
import pandas as pd
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Mapping the categories
categories = {
    1: "Bounces",
    2: "Open rates complaints",
    3: "Email account block",
    4: "Questions about tracking",
    5: "DNS",
    6: "Other questions",
    7: "Email Validations issues"
}

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

def clean_and_split_tags(cell):
  if pd.isnull(cell):
      return []  # Return an empty list for NaN values
  tags = [tag.strip() for tag in cell.replace(',', '|').split('|')]
  dt_tags = [tag for tag in tags if 'DT' in tag]
  return dt_tags

def parse_tag_and_category(tag):
  # Check if the tag contains the expected ':' separator
  if ':' in tag:
      tag_name, cat_id = tag.split(':')
      cat_id = int(cat_id)  # Convert to integer
      category_name = f"{cat_id} - {categories.get(cat_id, 'Unknown category')}"
  else:
      # Handle the case where no ':' is found
      tag_name = tag  # Use the original tag as the tag name
      cat_id = 0  # Convert to integer
      category_name = "Unknown category"  # Assign to an unknown category
  
  return f"{tag_name}", category_name,

def process_and_send_file(file_path, files_data):
    channel_id = files_data["channel_id"]
    
    # Read from CSV
    df = pd.read_csv(file_path)
    
    # Drop the first two columns from the DataFrame
    df = df.iloc[:, 2:]
    
    # Process tags
    df['Conversation tags'] = df['Conversation tags'].apply(clean_and_split_tags)
    exploded_df = df.explode('Conversation tags')
    
    # Count and categorize tags.
    tag_counts = exploded_df['Conversation tags'].value_counts()
    summary_df = pd.DataFrame({
        'Unique Tag': tag_counts.index,
        'Count': tag_counts.values
    })

    # Assuming parse_tag_and_category function is defined elsewhere.
    summary_df[['Formatted Tag', 'Category Name']] = summary_df['Unique Tag'].apply(parse_tag_and_category).tolist()
    
    # Group by 'Category Name' and aggregate tags within categories.
    category_groups = summary_df.groupby('Category Name').apply(
        lambda x: x[['Formatted Tag', 'Count']].to_dict('records')
    ).reset_index()
    category_groups.columns = ['Category Name', 'Tags']

    rows = prepare_rows(category_groups)

    category_df = pd.DataFrame(rows)
    exploded_df.reset_index(drop=True, inplace=True)
    category_df.reset_index(drop=True, inplace=True)
    final_df = pd.concat([exploded_df, category_df], axis=1)

    # Save the DataFrame to an Excel file
    new_file_path = file_path.replace(".csv", "_processed.xlsx")
    final_df.to_excel(new_file_path, index=False, engine='openpyxl')

    # Upload the file (assuming this function is defined elsewhere)
    upload_file(channel_id=channel_id, file_path=new_file_path)

# Helper function to prepare rows as before
def prepare_rows(category_groups):
    # Prepare the 'Categories' and 'DT Tags' data.
    rows = []
    total_count = 0
    category_summary = {}

    for category in category_groups.to_dict('records'):
        category_total = sum(tag['Count'] for tag in category["Tags"])
        category_summary[category['Category Name']] = category_total
        total_count += category_total

        rows.append({"Category Name": category['Category Name'], "DT Tags": '', "Count": ''})
        for tag in category["Tags"]:
            rows.append({"Category Name": '', "DT Tags": tag['Formatted Tag'], "Count": tag['Count']})

        rows.append({"Category Name": '', "DT Tags": '', "Count": ''})  # First empty row
        rows.append({"Category Name": '', "DT Tags": '', "Count": ''})  # Second empty row

    # After the last category, add final rows and summary
    rows.append({"Category Name": '', "DT Tags": "Total:", "Count": total_count})
    rows.append({"Category Name": '', "DT Tags": '', "Count": ''})  # First empty row
    rows.append({"Category Name": '', "DT Tags": '', "Count": ''})  # Second empty row
    rows.append({"Category Name": '', "DT Tags": '', "Count": ''})  # Third empty row
    rows.append({"Category Name": "Number of chats by category", "DT Tags": '', "Count": ''})  # Header row for summary
    
    for category, count in category_summary.items():
        rows.append({"Category Name": category, "DT Tags": count, "Count": ''})

    return rows


def download_file(files, files_data):
  for file_info in files:
    # Check the file type for security
    logging.info(f"Received file type: {file_info['filetype']}")
    file_url = file_info["url_private"]
    file_name = file_info["name"]
    
    # Define a temporary storage path
    download_dir = "./temp_downloads"
    os.makedirs(download_dir, exist_ok=True)
    local_file_path = os.path.join(download_dir, file_name)
    
    # Download the file
    headers = {"Authorization": f"Bearer {os.environ.get('SLACK_BOT_TOKEN')}"}
    response = requests.get(file_url, headers=headers, stream=True)
    
    if response.status_code == 200:
        with open(local_file_path, "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        
        logging.info(f"File downloaded: {local_file_path}")
        # Process and send the file, then delete it
        process_and_send_file(local_file_path, files_data)
    else:
        logging.error(f"Failed to download file: {file_url}")