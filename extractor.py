import io
import zipfile
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from docx import Document

def extract_text(file_obj=None, file_name="", url=""):
    """
    Extracts text from a given file object (with a filename to determine type)
    or from a URL.
    Returns the extracted text as a string.
    """
    if url:
        return extract_from_url(url)
    if file_obj is not None and file_name:
        ext = file_name.split('.')[-1].lower()
        if ext == "txt":
            # file_obj from streamlit is a BytesIO or similar
            content = file_obj.read()
            if isinstance(content, bytes):
                return content.decode("utf-8", errors="replace")
            return content
        elif ext == "pdf":
            return extract_from_pdf(file_obj)
        elif ext in ["doc", "docx"]:
            return extract_from_docx(file_obj)
        elif ext == "odt":
            return extract_from_odt(file_obj)
        else:
            raise ValueError(f"Unsupported file extension: {ext}")
    return ""

def extract_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Remove noisy elements
        for element in soup(["script", "style", "nav", "aside", "header", "footer", "noscript"]):
            element.extract()
            
        # Prioritize <article> or <main> if they exist
        target = soup.find('article') or soup.find('main') or soup.find('body')
        
        if target:
            text = target.get_text(separator=' ')
        else:
            text = soup.get_text(separator=' ')
            
        # Break into lines and remove leading/trailing space
        lines = (line.strip() for line in text.splitlines())
        # Drop blank lines
        text = '\n'.join(line for line in lines if line)
        
        return text
    except requests.exceptions.HTTPError as e:
        if e.response.status_code in (401, 403, 406):
            raise Exception("This website actively blocks automated content extraction. Please try a different URL or save the page as a text/PDF file and upload it instead.")
        raise Exception(f"Network error extracting from URL: {e}")
    except Exception as e:
        raise Exception(f"Error extracting from URL: {e}")

def extract_from_pdf(file_obj):
    try:
        reader = PdfReader(file_obj)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        raise Exception(f"Error extracting from PDF: {e}")

def extract_from_docx(file_obj):
    try:
        doc = Document(file_obj)
        return "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        raise Exception(f"Error extracting from DOCX: {e}")

def extract_from_odt(file_obj):
    try:
        with zipfile.ZipFile(file_obj) as zf:
            with zf.open("content.xml") as content_file:
                tree = ET.parse(content_file)
                root = tree.getroot()
                
                text_content = []
                for elem in root.iter():
                    if elem.tag.endswith('}p') or elem.tag.endswith('}h'):
                        text_content.append("".join(elem.itertext()))
                return "\n".join(text_content)
    except Exception as e:
        raise Exception(f"Error extracting from ODT: {e}")
