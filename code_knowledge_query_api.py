from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import os
from dotenv import load_dotenv
from langchain_community.vectorstores import Neo4jVector
from chains import (
    load_embedding_model
)
from langchain_core.documents import Document
from streamlit.logger import get_logger

logger = get_logger(__name__)
load_dotenv(".env")
app = FastAPI()

class UserQuestion(BaseModel):
    # question: str
    class_name:str
    method_name:str
    # description: str
class CodeContext(BaseModel):
    page_content:str
    metadata:str
embedding_model_name = os.getenv("EMBEDDING_MODEL")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
url = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
embeddings, dimension = load_embedding_model(
    embedding_model_name, config={"ollama_base_url": ollama_base_url}, logger=logger
)

query4 = """
WITH node AS method, score AS similarity
RETURN method.body AS text, similarity AS score, {source: method.full_class_name,class_name:method.class_name} AS metadata
"""
kg_class = Neo4jVector.from_existing_index(
    embedding=embeddings,
    url=url,
    username=username,
    password=password,
    database="neo4j",  # neo4j by default
    index_name="class_name_index",  # vector by default
    text_node_property="body",  # text by default
    retrieval_query=query4,
)
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
RETURN method.body + '\n' + param_classes_text + '\n' + called_methods_text AS text, similarity AS score, {source: method.full_class_name} AS metadata
"""
kg_method = Neo4jVector.from_existing_index(
    embedding=embeddings,
    url=url,
    username=username,
    password=password,
    database="neo4j",  # neo4j by default
    index_name="method_index",  # vector by default
    text_node_property="body",  # text by default
    retrieval_query=query2,
)

@app.get("/api")
def read_root():
    return {"message": "Hello, FastAPI"}

@app.post("/api/getCodeContext")
def getCodeContext(userQuestion: UserQuestion):
    print("dcjhd" + userQuestion.method_name)
    if  userQuestion.method_name:
        print("hello1")
        result = kg_method.similarity_search(userQuestion.method_name,k=1)
        code =  CodeContext(page_content = "",metadata = "")
        code.page_content = result[0].page_content
        code.metadata = result[0].metadata
        return code
    if  userQuestion.class_name:
        kg_class.similarity_search(userQuestion.class_name,k=100)
        inner_document = []
        result_document = []
        reduce_docment = Document("")
        if len(result) > 0:
            up_class_name = result[0].metadata['class_name']
            for document in result:
                if up_class_name == document.metadata['class_name']:
                    inner_document.append(document)
                else:
                    break
            for document in inner_document:
                reduce_docment.page_content = reduce_docment.page_content + document.page_content + '\n'
                reduce_docment.metadata = document.metadata
            result_document.append(reduce_docment)
            code =  CodeContext(page_content = "",metadata = "")
            code.page_content = result_document[0].page_content
            code.metadata = result_document[0].metadata
            return code

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8800)
