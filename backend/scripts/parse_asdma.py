import os
import glob
import re
import json
import pymupdf  # fitz
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

PDF_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'asdma_pdfs')
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'asdma_structured_data.json')

client = None
if os.environ.get("GROQ_API_KEY"):
    try:
        client = Groq()
    except Exception as e:
        print(f"Warning: Groq client failed to initialize: {e}")

def extract_text_from_pdf(filepath):
    """Uses PyMuPDF to extract raw text."""
    doc = pymupdf.open(filepath)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def chunk_relevant_text(raw_text):
    """
    Regex chunking to isolate the Kamrup Metro / Guwahati section.
    This saves massive amounts of tokens before hitting the LLM.
    """
    # Look for Kamrup Metro and grab the next ~500 characters
    match = re.search(r'(District:\s*Kamrup Metro[\s\S]{1,500})', raw_text, re.IGNORECASE)
    
    # Also grab date
    date_match = re.search(r'AS ON (\d{4}-\d{2}-\d{2})', raw_text)
    date_str = date_match.group(1) if date_match else "Unknown"
    
    chunk = match.group(1) if match else raw_text[:500]
    return date_str, f"Date: {date_str}\n" + chunk

def parse_with_llm(text_chunk):
    """Uses Groq Llama-3 to structure the data into JSON."""
    if not client:
        return parse_with_regex_fallback(text_chunk)
        
    prompt = f"""
    You are an expert data extraction AI. Extract the following information from the flood report text into strict JSON format.
    Do not include any markdown, only raw JSON.
    
    Fields required:
    - date (string)
    - district (string)
    - affected_population (integer)
    - villages_flooded (list of strings)
    - crops_damaged_hectares (float)
    
    Text:
    {text_chunk}
    """
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"Groq API Error: {e}")
        return parse_with_regex_fallback(text_chunk)

def parse_with_regex_fallback(text_chunk):
    """Fallback if Groq key is missing or API fails."""
    print("Using Regex Fallback for parsing...")
    data = {
        "date": "Unknown",
        "district": "Kamrup Metro",
        "affected_population": 0,
        "villages_flooded": [],
        "crops_damaged_hectares": 0.0
    }
    
    date_m = re.search(r'Date:\s*(\d{4}-\d{2}-\d{2})', text_chunk)
    if date_m: data["date"] = date_m.group(1)
        
    pop_m = re.search(r'Affected Population:\s*(\d+)', text_chunk)
    if pop_m: data["affected_population"] = int(pop_m.group(1))
        
    vill_m = re.search(r'Villages Flooded:\s*([^\n]+)', text_chunk)
    if vill_m:
        data["villages_flooded"] = [v.strip() for v in vill_m.group(1).split(',')]
        
    crop_m = re.search(r'Crops Damaged:\s*([\d\.]+)', text_chunk)
    if crop_m: data["crops_damaged_hectares"] = float(crop_m.group(1))
        
    return data

def process_all_pdfs():
    pdfs = glob.glob(os.path.join(PDF_DIR, "*.pdf"))
    if not pdfs:
        print("No PDFs found!")
        return
        
    print(f"Found {len(pdfs)} PDFs to process.")
    dataset = []
    
    for pdf in pdfs:
        print(f"Processing {os.path.basename(pdf)}...")
        raw_text = extract_text_from_pdf(pdf)
        date_str, chunk = chunk_relevant_text(raw_text)
        
        print(f"  -> Extracted {len(chunk)} characters. Sending to parser...")
        structured_data = parse_with_llm(chunk)
        
        # Ensure date is set correctly even if LLM missed it
        if "date" not in structured_data or structured_data["date"] == "Unknown":
            structured_data["date"] = date_str
            
        dataset.append(structured_data)
        
    # Sort by date
    dataset.sort(key=lambda x: x.get('date', ''))
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(dataset, f, indent=4)
        
    print(f"\nSuccessfully structured {len(dataset)} reports into {OUTPUT_FILE}")
    print(json.dumps(dataset[0], indent=2))

if __name__ == "__main__":
    process_all_pdfs()
