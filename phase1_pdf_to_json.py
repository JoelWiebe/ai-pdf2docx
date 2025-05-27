# File: phase1_pdf_to_json.py
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
import argparse # Keep for direct execution if needed, but wrapper will use its own
import os
import time

# This function will be called by the wrapper
def analyze_pdf_for_structured_output(pdf_path: str, model_name: str) -> str | None:
    """
    Sends a PDF to Gemini and requests structured output.
    Returns the raw text response from Gemini.
    Assumes vertexai.init() has been called.
    """
    print(f"Preparing to analyze {pdf_path} with model {model_name}...")
    model = GenerativeModel(model_name)

    try:
        with open(pdf_path, "rb") as f:
            pdf_content_bytes = f.read()
    except FileNotFoundError:
        print(f"Error: PDF file not found at {pdf_path}")
        return None
    except Exception as e:
        print(f"Error reading PDF file {pdf_path}: {e}")
        return None
    
    pdf_part = Part.from_data(mime_type="application/pdf", data=pdf_content_bytes)

    prompt = """
    You are an expert document structure analyzer. Please process the provided PDF document.
    Your task is to identify and extract content, discerning between different levels of headings,
    paragraphs, and tables.

    Return the output as a single JSON object. This object should contain one key: "document_elements".
    The value of "document_elements" should be a list of objects.
    Each object in the list represents a structural element from the document and must have two keys:
    1. "type": A string indicating the type of element. Possible values are:
        - "heading_1" (for main titles/H1)
        - "heading_2" (for sub-titles/H2)
        - "heading_3" (for sub-sub-titles/H3)
        - "paragraph" (for regular text paragraphs)
        - "table_markdown" (for tables, represented as GitHub-flavored Markdown)
    2. "content": A string containing:
        - For "heading_1", "heading_2", "heading_3": The text of the heading.
        - For "paragraph": The consolidated text of the paragraph. Internal line breaks from the PDF's visual formatting (that are not semantic new paragraphs) should be converted to spaces to form continuous prose.
        - For "table_markdown": The full table formatted as GitHub-flavored Markdown.

    Example of the expected JSON structure:
    {
      "document_elements": [
        { "type": "heading_1", "content": "The Main Title of the Document" },
        { "type": "paragraph", "content": "This is the first paragraph, and it flows continuously even if it spanned multiple lines in the PDF." },
        { "type": "heading_2", "content": "Introduction" }
      ]
    }

    Ensure you process the entire document and maintain the order of the elements.
    Identify headings based on common academic paper structures.
    Represent tables accurately in Markdown. Ensure semantic paragraphs are distinct elements.
    The entire output must be a single, valid JSON object.
    """
    
    generation_config = GenerationConfig(
        response_mime_type="application/json"
    )

    print(f"Sending {pdf_path} to Gemini model ({model_name})...")
    try:
        response = model.generate_content(
            [pdf_part, prompt],
            generation_config=generation_config,
        )
        if response and response.text:
            return response.text
        elif response and response.candidates and response.candidates[0].finish_reason != "SAFETY":
            print(f"Warning: Gemini returned an empty response for {pdf_path} but not due to safety. Check PDF content.")
            return '{ "document_elements": [] }'
        else:
            print(f"Error: Gemini response for {pdf_path} was empty or potentially blocked.")
            if response and response.candidates:
                 print(f"Finish reason: {response.candidates[0].finish_reason}")
                 if response.candidates[0].safety_ratings:
                    print(f"Safety ratings: {response.candidates[0].safety_ratings}")
            return None
    except Exception as e:
        print(f"Error calling Gemini API for {pdf_path}: {e}")
        if hasattr(e, 'message'): print(f"Error details: {e.message}")
        if hasattr(e, '_response') and e._response and hasattr(e._response, 'text'):
             print(f"Gemini API Error Response (raw): {e._response.text}")
        return None

def run_pdf_to_json_conversion(args):
    """
    Main logic for Phase 1: PDF to JSON conversion.
    Takes an argparse Namespace object.
    """
    if not os.path.isdir(args.input_pdf_directory):
        print(f"Error: Input PDF directory '{args.input_pdf_directory}' not found.")
        return
    
    os.makedirs(args.output_json_directory, exist_ok=True)
    
    print(f"Initializing Vertex AI with Project ID: {args.project_id}, Location: {args.location}")
    try:
        vertexai.init(project=args.project_id, location=args.location)
    except Exception as e:
        print(f"Failed to initialize Vertex AI: {e}")
        return

    for filename in os.listdir(args.input_pdf_directory):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(args.input_pdf_directory, filename)
            json_filename = os.path.splitext(filename)[0] + ".json"
            output_json_path = os.path.join(args.output_json_directory, json_filename)
            
            if os.path.exists(output_json_path) and not args.overwrite:
                print(f"Skipping {pdf_path}, JSON output already exists: {output_json_path}")
                continue

            print(f"\nProcessing {pdf_path}...")
            raw_gemini_output = analyze_pdf_for_structured_output(pdf_path, args.model)
            
            if raw_gemini_output:
                try:
                    with open(output_json_path, "w", encoding="utf-8") as f:
                        f.write(raw_gemini_output)
                    print(f"Successfully saved Gemini's raw output to: {output_json_path}")
                except Exception as e:
                    print(f"Error saving JSON file {output_json_path}: {e}")
            else:
                print(f"Failed to get structured data for {pdf_path}. Skipping JSON file creation.")
            
            if args.delay > 0:
                print(f"Waiting for {args.delay} seconds...")
                time.sleep(args.delay)

    print("\nPhase 1 (PDF to JSON) processing complete.")

# Keep this for potential direct execution of this file, though the wrapper is preferred.
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Standalone Phase 1: PDF to JSON using Gemini.")
    parser.add_argument("input_pdf_directory", help="Path to the directory containing PDF files.")
    parser.add_argument("output_json_directory", help="Path to the directory where JSON files will be saved.")
    parser.add_argument("--project_id", required=True, help="Google Cloud Project ID.")
    parser.add_argument("--location", default="global", help="Google Cloud location.")
    parser.add_argument("--model", default="gemini-2.5-pro-preview-05-06", help="Name of the Gemini model.")
    parser.add_argument("--delay", type=int, default=0, help="Delay in seconds between API calls.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing JSON files.")
    args = parser.parse_args()
    run_pdf_to_json_conversion(args)