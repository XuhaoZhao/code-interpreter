from langchain_community.vectorstores import Neo4jVector

import os

import streamlit as st
from streamlit.logger import get_logger
from langchain.callbacks.base import BaseCallbackHandler
from langchain_community.graphs import Neo4jGraph
from dotenv import load_dotenv
from utils import (
    create_vector_index,
)
from chains import (
    load_embedding_model,
    load_llm,
    configure_llm_only_chain,
    configure_method_rag_chain,
    configure_qa_rag_chain,
    generate_ticket,
)

load_dotenv(".env")

url = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
embedding_model_name = os.getenv("EMBEDDING_MODEL")
llm_name = os.getenv("LLM")
# Remapping for Langchain Neo4j integration
os.environ["NEO4J_URL"] = url

logger = get_logger(__name__)

# if Neo4j is local, you can go to http://localhost:7474/ to browse the database
neo4j_graph = Neo4jGraph(url=url, username=username, password=password)
embeddings, dimension = load_embedding_model(
    embedding_model_name, config={"ollama_base_url": ollama_base_url}, logger=logger
)


# Vector + Knowledge Graph response
kg = Neo4jVector.from_existing_index(
    embedding=embeddings,
    url=url,
    username=username,
    password=password,
    database="neo4j",  # neo4j by default
    index_name="method_name_index",  # vector by default
    text_node_property="body",  # text by default
    retrieval_query="""
with node AS method,score AS similarity
CALL { with method
        MATCH (method)-[:CALLS]->(invoked_method)
        WITH collect(invoked_method) as invoked_methods
        RETURN reduce(str='', invoked_method IN invoked_methods | str + 
                '\n### invoked_method (method_name: '+ invoked_method.method_name +'): '+  invoked_method.body + '\n') as invoked_method_Texts
    } 
return method.body + '\n' + invoked_method_Texts  AS text,similarity as score,{source: method.class_id} AS metadata

""",
)

print(kg.similarity_search("where is the buildCreateTableSql", k=1))

