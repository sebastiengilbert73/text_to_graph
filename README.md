# text_to_graph
A program that takes a text as input and organizes the information hierarchically, in a relational graph.

## Streamlit interface
In the Streamlit interface, the user can supply a url, or drag-and-drop a file (.txt, .doc, .pdf).
The program uses an ollama-served LLM to analyze the content of the text, then produces a summarization
in the form of a relational graph. The text main theme must be the source node of the graph. The first-order relations
(or themes) must receive a link from the soure node. Lower-level themes must be analyzed in the same way. Cycles are permitted.

