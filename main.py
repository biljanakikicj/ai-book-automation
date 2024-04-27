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

prompts = [
    "Give me a checklist of questions and answers from this chapter that I would have to answer to pass a test?",
    "Give me the benefits taught in this chapter",
    "Give me the headings and sub headings of each chapter?",
    "Make a text soundbite for each heading and sub heading and summarizing each part",
    "Write a one person dialog in first person for a VoiceOver speaking the sound bites? It wouldn't contain any bullets and would talk like a human.",
    "Summarize this chapter in 100 words",
    "Extract key points from this chapter",
    "Analyze this chapter and provide insights",
    "Generate a quiz based on this chapter"
]

file_name_bases = [
    "QA",
    "Benefits",
    "Headings",
    "Soundbites",
    "DialogVoiceOver",
    "KeyPoints",
    "Analysis",
    "Quiz"
]


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
    except Exception as e:
        print(f"Error getting file: {e}")
        pass
    try:
        uploaded_file = genai.upload_file(path=path, display_name=hash_id)
        uploaded_files.append(uploaded_file)
        return [uploaded_file.uri]
    except Exception as e:
        print(f"Error uploading file: {e}")
        return []

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

def write_to_file(result, chapter, prompt, chapter_number):
    file_name_base = file_name_bases[prompts.index(prompt)]
    file_name = f"Chapter_{chapter_number}_{file_name_base}.txt"
    bucket = storage.Client().bucket(bucket_name)
    blob = bucket.blob(file_name)
    blob.upload_from_string(result)
    print(f"Result written to {file_name} in bucket {bucket_name}")
    
def define_chapters(full_text):
    try:
        input_text = f"Please split this document into logical chapters, with the full context for each chapter: {full_text}"
        response = model.generate_content(input_text)
        print("Full API Response:", response)
        if hasattr(response, 'text') and response.text:
            return response.text.split('--- CHAPTER ')  # Split the response into chapters
        else:
            print("No text returned in API response.")
            return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

def process_chapter(chapter, chapter_content, prompts):
    chapter_number = chapter.split(' ')[1]  # Extract chapter number from chapter title
    for prompt in prompts:
        try:
            result = model.generate_content(f"{prompt}: {chapter}")
            write_to_file(result.text, chapter, prompt, chapter_number)
        except Exception as e:
            print(f"Error generating content: {e}")
            continue  # Move on to the next prompt

def main():
    full_text, pages = extract_pdf_pages(pdf_path)

    # Print extracted text page by page
    #for page_content in pages:
    #    print(page_content)  # Print each page's content

    # Generate summary and organized content
    chapters = define_chapters(full_text)
    print("Generated Chapters:")
    for chapter in chapters:
        print(chapter)


    for chapter in chapters:
        process_chapter(chapter, chapter, prompts)

if __name__ == "__main__":
    main()

