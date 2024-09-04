from typing import List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from chains import (
    load_embedding_model,
    load_llm,
    configure_llm_only_chain,
    configure_qa_rag_chain,
    generate_ticket,
)
import os

import streamlit as st
from streamlit.logger import get_logger
from langchain.callbacks.base import BaseCallbackHandler
from langchain_community.graphs import Neo4jGraph
from dotenv import load_dotenv
from utils import (
    create_vector_index,
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
llm = ChatOpenAI(
    api_key="ollama",
    model="llama3.1",
    base_url=ollama_base_url,
)

# llm = load_llm(llm_name, logger=logger, config={"ollama_base_url": ollama_base_url})
class Entities(BaseModel):
    """Identifying information about entities."""
    names: List[str] = Field(
        ...,
        description="All the person or movies appearing in the text",
    )
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are extracting person and movies from the text.",
        ),
        (
            "human",
            "Use the given format to extract information from the following "
            "input: {question}",
        ),
    ]
)
entity_chain = prompt | llm.with_structured_output(Entities)