import os
import fitz  # Import PyMuPDF
from pathlib import Path
import hashlib
import google.generativeai as genai
from google.cloud import storage
import yaml

with open('env.yaml', 'r') as f:
  env_vars = yaml.safe_load(f)

api_key = env_vars['GENAI_API_KEY']

# Get API key from environment variable
# api_key = os.environ['GENAI_API_KEY']

# Configure genai with the API key from environment variables
genai.configure(api_key=api_key)
print(f"API Key: {api_key}")

# Model and generation settings
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 0,
    "max_output_tokens": 8192,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest",
                              generation_config=generation_config,
                              safety_settings=safety_settings)

uploaded_files = []

# Define book variables 
bucket_name = 'staging.ai-book-automation.appspot.com'
file_name = 'The Art Of Systems Thinking.pdf'
pdf_path = f"gs://{bucket_name}/{file_name}"
local_path = f"/tmp/{file_name.replace('/', '_')}"

def upload_if_needed(pathname: str) -> list[str]:
    path = Path(pathname)
    hash_id = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        existing_file = genai.get_file(name=hash_id)
        return [existing_file.uri]
    except:
        pass
    uploaded_file = genai.upload_file(path=path, display_name=hash_id)
    uploaded_files.append(uploaded_file)
    return [uploaded_file.uri]

def extract_pdf_pages(pathname: str) -> list[str]:
    # Download the file from Google Cloud Storage
    storage_client = storage.Client()
    blob = storage_client.bucket(bucket_name).blob(file_name)
    blob.download_to_filename(local_path)

    # Open the downloaded file with fitz
    doc = fitz.open(local_path)
    pages_text = [f"--- START OF PDF {pathname} ---"]
    full_text = ""
    for page in doc:
        text = page.get_text()
        pages_text.append(f"--- PAGE {page.number} ---")
        pages_text.append(text)
        full_text += text + " "  # Concatenate all text for summarization
    doc.close()
    return full_text, pages_text

def define_chapters(full_text):
    try:
        # Construct the input string with instruction
        input_text = f"Please split this document into chapters: {full_text} Identify the chapter boundaries in the provided text based on the detected headings. Return a list of chapter titles and their corresponding contents."

        # Making the API call directly with the constructed string
        response = model.generate_content(input_text)
        
        # Check and print the full response to understand its structure
        print("Full API Response:", response)

        # Assuming the response has a 'text' attribute based on your last message
        if hasattr(response, 'text') and response.text:
            return response.text
        else:
            print("No text returned in API response.")
            return []
    except Exception as e:
        # Catch any type of exception and print it for debugging
        print(f"An error occurred: {e}")
        return []

def write_to_file(result, chapter_title):
    file_name = f"{chapter_title}.txt"
    with open(file_name, "w") as f:
        f.write(result)
    print(f"Result written to {file_name}")

def main():
    full_text, pages = extract_pdf_pages(pdf_path)

    # Print extracted text page by page
    #for page_content in pages:
    #    print(page_content)  # Print each page's content

    # Generate summary and organized content
    chapters = define_chapters(full_text)
    print("Generated Chapters:")
    print(chapters)

    # Run different prompts for each chapter
    for chapter in chapters:
        prompt1 = "Summarize the chapter in 100 words"
        result1 = model.generate_content(prompt1)
        # write_to_file(result1.text, chapter)
        print(result1.text, chapter)

        prompt2 = "Extract key points from the chapter"
        result2 = model.generate_content(prompt2)
        print(result2.text, chapter)

        prompt3 = "Analyze the chapter and provide insights"
        result3 = model.generate_content(prompt3)
        print(result3.text, chapter)

        prompt4 = "Generate a quiz based on the chapter"
        result4 = model.generate_content(prompt4)
        print(result4.text, chapter)

        # Optionally clean up by deleting uploaded files
        for uploaded_file in uploaded_files:
            genai.delete_file(name=uploaded_file.name)

if __name__ == "__main__":
    main()