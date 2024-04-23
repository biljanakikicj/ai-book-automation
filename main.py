import os
import fitz  # Import PyMuPDF
from pathlib import Path
import hashlib
import google.generativeai as genai

# Get API key from environment variable
api_key = os.getenv('GENAI_API_KEY')

# Configure genai with the API key from environment variables
genai.configure(api_key=api_key)

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
    doc = fitz.open(pathname)
    pages_text = [f"--- START OF PDF {pathname} ---"]
    full_text = ""
    for page in doc:
        text = page.get_text()
        pages_text.append(f"--- PAGE {page.number} ---")
        pages_text.append(text)
        full_text += text + " "  # Concatenate all text for summarization
    doc.close()
    return full_text, pages_text

def summarize_text(full_text):
    try:
        # Construct the input string with instruction
        input_text = f"Please summarize this document: {full_text}"

        # Making the API call directly with the constructed string
        response = model.generate_content(input_text)
        
        # Check and print the full response to understand its structure
        print("Full API Response:", response)

        # Assuming the response has a 'text' attribute based on your last message
        if hasattr(response, 'text'):
            return response.text
        else:
            print("Response does not contain 'text' attribute.")
            return None

    except Exception as e:
        # Catch any type of exception and print it for debugging
        print(f"An error occurred: {e}")
        return None

# Example usage in the main function:
def main():
    pdf_path = "The Art Of Systems Thinking.pdf"  # Make sure this is the correct path
    full_text, pages = extract_pdf_pages(pdf_path)

    # Print extracted text page by page
    #for page_content in pages:
       # print(page_content)  # Print each page's content

    # Generate summary and organized content
    summary = summarize_text(full_text)
    print("Generated Summary:")
    print(summary)

    # Optionally clean up by deleting uploaded files
    for uploaded_file in uploaded_files:
        genai.delete_file(name=uploaded_file.name)

if __name__ == "__main__":
    main()



