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




query1 = """
WITH node AS method, score AS similarity
CALL {
    WITH method
    MATCH (method)-[:CALLS]->(invoked_method)
    OPTIONAL MATCH (invoked_method)-[:PARAM]->(param)
    WITH invoked_method, collect(param.parameter_name) AS parameters
    WITH collect(invoked_method) AS invoked_methods, collect(parameters) AS method_parameters
    RETURN reduce(str = '', i IN range(0, size(invoked_methods)-1) | 
        str + '\n //invoked_method (method_name: ' + invoked_methods[i].method_name + 
        ', parameters: ' + apoc.text.join(method_parameters[i], ', ') + 
        '): ' + invoked_methods[i].body + '\n') AS invoked_method_Texts
}
RETURN method.body + '\n' + invoked_method_Texts AS text, similarity AS score, {source: method.class_id} AS metadata
"""
query3 = """
with node AS method,score AS similarity
CALL { with method
        MATCH (method)-[:CALLS]->(invoked_method)
        WITH collect(invoked_method) as invoked_methods
        RETURN reduce(str='', invoked_method IN invoked_methods | str + 
                '\n### invoked_method (method_name: '+ invoked_method.method_name +'): '+  invoked_method.body + '\n') as invoked_method_Texts
    } 
return method.body + '\n' + invoked_method_Texts  AS text,similarity as score,{source: method.class_id} AS metadata

"""
query2 = """
WITH node AS method, score AS similarity
CALL{
WITH method
OPTIONAL MATCH (method)-[:CALLS]->(called_method:Method)
WITH method, collect(called_method) AS called_methods
OPTIONAL MATCH (method)-[:PARAM]->(param_class:RequestClass)
WITH 
    called_methods, 
    collect(param_class) AS param_classes
RETURN reduce(calls_str = '', called_method IN called_methods | 
              calls_str +'\n //------//' + '\n //Called Method: \n' + called_method.body) 
       AS called_methods_text,
       reduce(params_str = '', param_class IN param_classes | 
              params_str+'\n //------//' + '\n //Parameter Class: \n'  + param_class.file_content) 
       AS param_classes_text
}
RETURN method.body + '\n' + called_methods_text + '\n' + param_classes_text AS text, similarity AS score, {source: method.class_id} AS metadata
"""

query4 = """
WITH node AS method, score AS similarity
RETURN method.body  AS text, similarity AS score, {source: method.class_id} AS metadata
"""

# Vector + Knowledge Graph response
kg = Neo4jVector.from_existing_index(
    embedding=embeddings,
    url=url,
    username=username,
    password=password,
    database="neo4j",  # neo4j by default
    index_name="method_index",  # vector by default
    text_node_property="body",  # text by default
    retrieval_query=query2,
)

print(kg.similarity_search("addChatGptSystemConfig", k=1))




