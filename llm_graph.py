import json
import requests
import logging
from pydantic import BaseModel, Field
from typing import List
from langdetect import detect, DetectorFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("llm_interactions.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# To ensure consistent language detection
DetectorFactory.seed = 0

# Define expected JSON structure (useful for explicit referencing)
class Node(BaseModel):
    id: str = Field(description="Unique identifier for the node")
    label: str = Field(description="Display label for the node")
    is_source: bool = Field(default=False, description="True ONLY for the main theme (source) node")

class Edge(BaseModel):
    source: str = Field(description="ID of the source node")
    target: str = Field(description="ID of the target node")
    label: str = Field(description="Description of the relationship")

def generate_graph_from_text(text: str, server_url: str, model_name: str):
    """
    Sends text to Ollama to generate a relational graph JSON.
    Returns a dict containing nodes and edges.
    """
    try:
        detected_language = detect(text)
    except Exception:
        detected_language = "unknown"
        
    language_instruction = ""
    if detected_language != "unknown":
        language_instruction = f"The input text is detected as language code '{detected_language}'. You MUST output all labels for nodes and edges in this exact language."

    system_prompt = f'''
You are an expert at analyzing text and converting it into a concise relational graph.
Your task is to identify the MAIN theme of the text to serve as the SOURCE node of the graph.
Then, identify first-order themes that relate to the main theme. Provide edges from the source node to these themes.
Then, do the same for lower-level themes. Cycles are permitted.
{language_instruction}

CRITICAL: You must use a rich and descriptive vocabulary for edge labels. Do NOT simply use "contains" for all edges. Use specific verbs or short verb phrases that accurately describe the relationship (e.g., "causes", "depends on", "is a type of", "results in", "requires", "opposes", "supports", "relates to").

You must reply with valid JSON ONLY conforming exactly to this structure:
{{
  "nodes": [
    {{"id": "Node1", "label": "Main Theme", "is_source": true}}, 
    {{"id": "Node2", "label": "Sub Theme", "is_source": false}}
  ],
  "edges": [{{"source": "Node1", "target": "Node2", "label": "descriptive_verb_phrase"}}]
}}
Ensure the JSON is perfectly formatted. Do not include markdown blocks or other text.
'''
    
    # Trim extremely large texts just in case context window is small
    user_prompt = f"Here is the text:\n\n{text[:15000]}"

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "format": "json", # Requires Ollama >= 0.1.30 to enforce JSON
        "stream": False
    }
    
    server_url = server_url.strip()
    if not server_url.startswith("http"):
        server_url = "http://" + server_url
    if server_url.endswith("/"):
        server_url = server_url[:-1]

    endpoint = f"{server_url}/api/chat"
    
    logger.info("=== Sending Request to LLM ===")
    logger.info(f"System Prompt:\n{system_prompt}")
    logger.info(f"User Prompt:\n{user_prompt}")
    
    try:
        response = requests.post(endpoint, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        reply_content = data.get("message", {}).get("content", "")
        
        logger.info("=== Received Response from LLM ===")
        logger.info(f"Response Content:\n{reply_content}")
        
        # Parse output
        try:
            graph_json = json.loads(reply_content)
        except json.JSONDecodeError:
            # Strip markdown just in case the format flag didn't fully prevent it
            reply_content = reply_content.replace('```json', '').replace('```', '').strip()
            graph_json = json.loads(reply_content)
            
        return graph_json
    except Exception as e:
        raise Exception(f"Failed to generate graph: {e}")
