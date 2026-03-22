import streamlit as st
import requests
import json
import os
import logging
from extractor import extract_text
from llm_graph import generate_graph_from_text

# Configure application logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler()
    ],
    force=True
)
logger = logging.getLogger(__name__)

try:
    from streamlit_agraph import agraph, Node, Edge, Config
    AGRAPH_AVAILABLE = True
except ImportError:
    AGRAPH_AVAILABLE = False

CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            st.sidebar.error(f"Error loading config: {e}")
    return {}

def save_config(server_address, selected_model):
    config = {
        "server_address": server_address,
        "selected_model": selected_model
    }
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        st.sidebar.error(f"Error saving config: {e}")

def get_ollama_models(server_url):
    try:
        server_url = server_url.strip()
        if not server_url.startswith("http"):
            server_url = "http://" + server_url
        if server_url.endswith("/"):
            server_url = server_url[:-1]
            
        response = requests.get(f"{server_url}/api/tags", timeout=5)
        response.raise_for_status()
        models_data = response.json()
        if "models" in models_data:
            return [model["name"] for model in models_data["models"]]
    except Exception:
        pass
    return []

def render_graph_from_json(graph_json):
    if not AGRAPH_AVAILABLE:
        st.error("streamlit-agraph is not installed. Displaying JSON instead.")
        st.json(graph_json)
        return

    nodes = []
    edges = []
    
    node_colors = [
        "#5D6D7E", "#5499C7", "#48C9B0", "#52BE80", 
        "#AF7AC5", "#EB984E", "#EC7063", "#5DADE2",
        "#45B39D", "#99A3A4", "#D2B4DE", "#F4D03F"
    ]

    # Create nodes
    for node_data in graph_json.get("nodes", []):
        node_id = str(node_data.get("id", ""))
        node_label = str(node_data.get("label", node_id))
        is_source = node_data.get("is_source", False)
        
        # Distinctive color and slightly larger size for the source node
        if is_source:
            color = "#FF0000" # Bright red
        else:
            color_idx = sum(ord(c) for c in node_id) % len(node_colors)
            color = node_colors[color_idx]
            
        size = 35 if is_source else 25
        
        nodes.append(Node(id=node_id, label=node_label, size=size, shape="dot", color=color, font={'color': color}))
    
    # Create edges
    for edge_data in graph_json.get("edges", []):
        source_id = str(edge_data.get("source", ""))
        target_id = str(edge_data.get("target", ""))
        label = str(edge_data.get("label", ""))
        edges.append(Edge(source=source_id, target=target_id, label=label))
    
    config = Config(width=1000,
                    height=800,
                    directed=True, 
                    physics={"barnesHut": {"springLength": 200, "avoidOverlap": 0.5}}, 
                    hierarchical=False)
    
    return agraph(nodes=nodes, edges=edges, config=config)

def main():
    st.set_page_config(page_title="Text to Graph Organizer", layout="wide")
    
    # --- SIDEBAR CONFIGURATION ---
    st.sidebar.title("Ollama Configuration")

    if "config_loaded" not in st.session_state:
        config = load_config()
        st.session_state.server_address = config.get("server_address", "http://localhost:11434")
        st.session_state.selected_model = config.get("selected_model", "")
        st.session_state.config_loaded = True
        st.session_state.models = []

    server_address = st.sidebar.text_input("Server Address", value=st.session_state.server_address)

    if server_address != st.session_state.get("last_fetched_server"):
        with st.sidebar.spinner("Fetching models..."):
            models = get_ollama_models(server_address)
            st.session_state.models = models
            st.session_state.last_fetched_server = server_address
            if st.session_state.selected_model not in models and models:
                st.session_state.selected_model = models[0] if len(models) > 0 else ""

    available_models = st.session_state.get("models", [])
    
    if not available_models:
        st.sidebar.warning(f"No models found at {server_address}")
    
    selected_model = ""
    if available_models:
        default_index = 0
        if st.session_state.selected_model in available_models:
            default_index = available_models.index(st.session_state.selected_model)
        selected_model = st.sidebar.selectbox("Select Model", options=available_models, index=default_index)

    if st.sidebar.button("Save Config", type="primary"):
        save_config(server_address, selected_model)
        st.session_state.server_address = server_address
        st.session_state.selected_model = selected_model
        st.sidebar.success("Saved!")

    # --- MAIN PAGE ---
    st.title("Text to Graph Organizer")
    st.markdown("Supply a URL or upload a file to extract its main themes into a relational graph using Ollama.")
    
    input_type = st.radio("Input Source", ["File Upload", "URL"])
    
    text_content = ""
    
    if input_type == "File Upload":
        uploaded_file = st.file_uploader("Upload a document", type=["txt", "pdf", "docx", "doc", "odt"])
        if uploaded_file is not None:
            with st.spinner("Extracting text..."):
                try:
                    text_content = extract_text(file_obj=uploaded_file, file_name=uploaded_file.name)
                except Exception as e:
                    st.error(f"Error extracting text: {e}")
    else:
        url_input = st.text_input("Enter URL")
        if url_input:
            logger.info(f"User requested URL extraction for: {url_input}")
            with st.spinner("Extracting text from URL..."):
                try:
                    text_content = extract_text(url=url_input)
                    if not text_content:
                        logger.warning(f"Extracted completely empty text from {url_input}")
                        st.warning(f"No text could be extracted from {url_input}. The site might be heavily JavaScript-rendered or protected. Check app.log for details.")
                except Exception as e:
                    logger.error(f"Error in UI during URL extraction: {e}")
                    st.error(f"Error extracting URL: {e}")

    if text_content:
        with st.expander("Show Extracted Text"):
            with st.container(height=300):
                st.text(text_content)
            
        if st.button("Generate Relational Graph", type="primary"):
            if not selected_model:
                st.error("Please configure an Ollama model in the sidebar first.")
            else:
                with st.spinner(f"Generating graph using {selected_model}..."):
                    try:
                        graph_json = generate_graph_from_text(
                            text=text_content, 
                            server_url=server_address, 
                            model_name=selected_model
                        )
                        st.session_state.graph_json = graph_json
                        st.success("Graph generated successfully!")
                    except Exception as e:
                        st.error(f"Graph generation failed: {e}")

    if "graph_json" in st.session_state:
        st.markdown("### Visualization")
        render_graph_from_json(st.session_state.graph_json)
        
        with st.expander("Raw JSON Graph Data"):
            st.json(st.session_state.graph_json)

if __name__ == "__main__":
    main()
