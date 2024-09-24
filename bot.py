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

from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import JsonOutputParser
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain_community.vectorstores import Neo4jVector
from langchain_core.documents import Document
import config as globalConfig
from dotenv import load_dotenv
from streamlit.logger import get_logger
import os
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate
)
from langchain_community.graphs import Neo4jGraph
from chains import (
    load_embedding_model,
    load_llm,
    configure_llm_only_chain,
    configure_method_rag_chain,
    configure_qa_rag_chain,
    generate_ticket,
)
from typing import List, Any
from langchain_core.messages import AIMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from typing import List
from langchain_community.llms import FakeListLLM
import json


general_system_template_method = """ 
你是一个java代码高手，我会在上下文中提供几个关键的代码片段，代码片段的内部是有结构的，每个片段中间用//------//分割,每个片段开头的一个java方法是非常重要的核心方法，接下来的代码片段会是核心方法的参数定义、核心方法调用的其他方法，
所以我提供的代码片段是非常有用的，你应该参考代码片段回答问题。
当你发现上下文中的某段代码非常有用时，请在最后的回复中加上代码。
如果你不知道答案，就直接说不知道，不要试图编造答案。
如果我没有提供代码片段，你就正常回答问题。
----
{summaries}
----
你生成的每个答案都应在末尾包含一个部分，这部分包含代码
"""
general_system_template_class = """ 
你是一个java代码高手，我会在上下文中提供一个class中所有方法的代码，
所以我提供的代码片段是非常有用的，你应该参考代码片段回答问题。
当你发现上下文中的某段代码非常有用时，请在最后的回复中加上代码。
如果你不知道答案，就直接说不知道，不要试图编造答案。
如果我没有提供代码片段，你就正常回答问题。
----
{summaries}
----
你生成的每个答案都应在末尾包含一个部分，这部分包含代码
"""
prompt2 = """首先，明确我的需求，从用户问题中提取关键字，以json格式输出结果，不要产生其他多余的输出。我有一个neo4j图数据库，它主要用来存储java代码，它里面有一个节点叫Method，顾名思义，用来存储java方法相关的信息，
Method节点主要的属性有：project_name(项目名称)，class_name(类名)，method_name(方法名)，body(完整的代码)，method_desc(方法的功能描述)。现在有个问题需要你解决，
从下面的用户问题中提取代码相关的关键字，我要用这些关键字去检索对应的Method节点的属性，所以你得提取务必准确，如果用户没有提到任何和代码相关的关键字，你返回给我空字符串也没有任何问题
比如说你判断用户提到了某些项目名称和方法名称，你要以json格式返回给我'project_name':[projectName1,projectName2],'method_name':[methodName1,methodName2]。
用户问题是 {question}"""

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

query4 = """
WITH node AS method, score AS similarity
RETURN method.body AS text, similarity AS score, {source: method.full_class_name,class_name:method.class_name} AS metadata
"""

class Joke(BaseModel):
    project_name: List[str] = Field(description="question to set up a joke")
    method_name: List[str] = Field(description="answer to resolve the joke")
    method_desc: List[str] = Field(description="answer to resolve the joke")
    class_name: List[str] = Field(description="answer to resolve the joke")
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
create_vector_index(neo4j_graph, dimension)


class StreamHandler(BaseCallbackHandler):
    def __init__(self, container, initial_text=""):
        self.container = container
        self.text = initial_text

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        self.text += token
        self.container.markdown(self.text)


llm = load_llm(llm_name, logger=logger, config={"ollama_base_url": ollama_base_url})

llm_chain = configure_llm_only_chain(llm)
rag_chain = configure_method_rag_chain(
    llm, embeddings, embeddings_store_url=url, username=username, password=password
)

# Streamlit UI
styl = f"""
<style>
    /* not great support for :has yet (hello FireFox), but using it for now */
    .element-container:has([aria-label="Select RAG mode"]) {{
      position: fixed;
      bottom: 200px;
      background: white;
      z-index: 101;
    }}
    .stChatFloatingInputContainer {{
        bottom: 10px;
    }}

    /* Generate ticket text area */
    textarea[aria-label="Description"] {{
        height: 200px;
    }}
</style>
"""
st.markdown(styl, unsafe_allow_html=True)


def chat_input():
    user_input = st.chat_input("What coding issue can I help you resolve today?")

    if user_input:
        with st.chat_message("user"):
            st.write(user_input)
        with st.chat_message("assistant"):
            st.caption(f"RAG: {name}")
            stream_handler = StreamHandler(st.empty())
            # result = getLLMResponse(user_input,stream_handler)
            result = output_function(
                {"question": user_input, "chat_history": []}, callbacks=[stream_handler]
            )["answer"]
            output = result
            st.session_state[f"user_input"].append(user_input)
            st.session_state[f"generated"].append(output)
            st.session_state[f"rag_mode"].append(name)

def getLLMResponse(user_input,stream_handler):
    general_user_template = "Question:```{question}```"
    # Vector + Knowledge Graph response
    question = user_input
    promp_second = ChatPromptTemplate.from_template(prompt2)
    parser = JsonOutputParser(pydantic_object=Joke)
    chain = promp_second | llm | parser
    msg1 = chain.invoke({"question": question})
    if msg1.get('class_name'):
        messages = [
            SystemMessagePromptTemplate.from_template(general_system_template_class),
            HumanMessagePromptTemplate.from_template(general_user_template),
        ]
        qa_prompt = ChatPromptTemplate.from_messages(messages)
        kg = Neo4jVector.from_existing_index(
            embedding=embeddings,
            url=url,
            username=username,
            password=password,
            database="neo4j",  # neo4j by default
            index_name="class_name_index",  # vector by default
            text_node_property="body",  # text by default
            retrieval_query=query4,
        )
        result = kg.similarity_search(msg1.get('class_name')[0], k=100)
        inner_document = []
        result_document = []
        str = ''
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
        qa_chain = load_qa_with_sources_chain(
            llm,
            chain_type="stuff",
            prompt=qa_prompt,
            verbose=True
        )
        result = qa_chain.invoke({"question": question, "input_documents": result_document})
        return result["output_text"]   

    if msg1.get("method_name"):
        
        messages = [
            SystemMessagePromptTemplate.from_template(general_system_template_method),
            HumanMessagePromptTemplate.from_template(general_user_template),
        ]
        qa_prompt = ChatPromptTemplate.from_messages(messages)

    #加了 verbose=True 打开日志
        qa_chain = load_qa_with_sources_chain(
            llm,
            chain_type="stuff",
            prompt=qa_prompt,
            verbose=True
        )
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
        result = kg.similarity_search(msg1.get("method_name")[0], k=1)
        result = qa_chain.invoke({"question": question, "input_documents": result})
        print(result["output_text"])
        return result["output_text"]
    return output_function(
                {"question": user_input, "chat_history": []},callbacks=[stream_handler]
            )["answer"]
def display_chat():
    # Session state
    if "generated" not in st.session_state:
        st.session_state[f"generated"] = []

    if "user_input" not in st.session_state:
        st.session_state[f"user_input"] = []

    if "rag_mode" not in st.session_state:
        st.session_state[f"rag_mode"] = []

    if st.session_state[f"generated"]:
        size = len(st.session_state[f"generated"])
        # Display only the last three exchanges
        for i in range(max(size - 3, 0), size):
            with st.chat_message("user"):
                st.write(st.session_state[f"user_input"][i])

            with st.chat_message("assistant"):
                st.caption(f"RAG: {st.session_state[f'rag_mode'][i]}")
                st.write(st.session_state[f"generated"][i])

        with st.expander("Not finding what you're looking for?"):
            st.write(
                "Automatically generate a draft for an internal ticket to our support team."
            )
            st.button(
                "Generate ticket",
                type="primary",
                key="show_ticket",
                on_click=open_sidebar,
            )
        with st.container():
            st.write("&nbsp;")


def mode_select() -> str:
    options = ["Disabled", "Enabled"]
    return st.radio("Select RAG mode", options, horizontal=True)


name = mode_select()
if name == "LLM only" or name == "Disabled":
    output_function = llm_chain
elif name == "Vector + Graph" or name == "Enabled":
    output_function = rag_chain


def open_sidebar():
    st.session_state.open_sidebar = True


def close_sidebar():
    st.session_state.open_sidebar = False


if not "open_sidebar" in st.session_state:
    st.session_state.open_sidebar = False
if st.session_state.open_sidebar:
    new_title, new_question = generate_ticket(
        neo4j_graph=neo4j_graph,
        llm_chain=llm_chain,
        input_question=st.session_state[f"user_input"][-1],
    )
    with st.sidebar:
        st.title("Ticket draft")
        st.write("Auto generated draft ticket")
        st.text_input("Title", new_title)
        st.text_area("Description", new_question)
        st.button(
            "Submit to support team",
            type="primary",
            key="submit_ticket",
            on_click=close_sidebar,
        )


display_chat()
chat_input()
