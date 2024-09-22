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

load_dotenv(".env")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
url = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
embedding_model_name = os.getenv("EMBEDDING_MODEL")
logger = get_logger(__name__)
embeddings, dimension = load_embedding_model(
    embedding_model_name, config={"ollama_base_url": ollama_base_url}, logger=logger
)

llm_name = os.getenv("LLM")
llm = ChatOllama(
        temperature=0,
        base_url='http://js1.blockelite.cn:21275',
        model=llm_name,
        # streaming=True,
        # seed=2,
        top_k=10,  # A higher value (100) will give more diverse answers, while a lower value (10) will be more conservative.
        top_p=0.3,  # Higher value (0.95) will lead to more diverse text, while a lower value (0.5) will generate more focused text.
        num_ctx=3072,  # Sets the size of the context window used to generate the next token.
    )
responses = [""" {
    "project_name": [
        "help"
    ],
    "method_desc": [
        "发起esb请求",
        "发起http请求"
    ],
    "class_name": [
        "class_name1",
        "class_name2"
    ],
    "method_name":["method_name1"]
             }
             """]

responses1 = ["""{
    "project_name": [
        "employee-center"
    ],
    "method_name": []
}"""]
llm1 = FakeListLLM(responses=responses)
# prompt = ChatPromptTemplate.from_template("tell me a joke about {topic}")

# chain = prompt | llm | StrOutputParser()
# analysis_prompt = ChatPromptTemplate.from_template("is this a funny joke? {joke}")

# composed_chain = {"joke": chain} | analysis_prompt | llm | StrOutputParser()

# composed_chain.invoke({"topic": "bears"})

# composed_chain_with_lambda = (
#     chain
#     | (lambda input: {"joke": input})
#     | analysis_prompt
#     | llm
#     | StrOutputParser()
# )

# msg = composed_chain_with_lambda.invoke({"topic": "beets"})
# print(msg)

class Joke(BaseModel):
    project_name: List[str] = Field(description="question to set up a joke")
    method_name: List[str] = Field(description="answer to resolve the joke")
    method_desc: List[str] = Field(description="answer to resolve the joke")
    class_name: List[str] = Field(description="answer to resolve the joke")

prompt = """我有一个neo4j图数据库，它主要用来存储java代码，它里面有一个节点叫Method，顾名思义，用来存储方法，
Method节点主要的属性有：project_name(工程名称)，class_name(类名)，method_name(方法名)，body(完整的代码)，method_desc(方法的功能描述)。现在有个问题需要你解决，
从下面的用户问题中提取代码相关的关键字，我要用这些关键字去检索对应的Method节点的属性，所以你得提取务必准确，如果用户没有提到任何和代码相关的关键字，你返回给我{''}也没有任何问题
比如说你判断用户提到了某些工程名称和方法名称，你要这么返回给我{'project_name':[projectName1,projectName2],'method_name':[methodName1,methodName2]}。
用户问题是 {question}"""

prompt1 = """我有一个neo4j图数据库，它主要用来存储java代码，它里面有一个节点叫Method，顾名思义，用来存储方法，
Method节点主要的属性有：project_name(工程名称)，class_name(类名)，method_name(方法名)，body(完整的代码)，method_desc(方法的功能描述)。现在有个问题需要你解决，
从下面的用户问题中提取代码相关的关键字，我要用这些关键字去检索对应的Method节点的属性，所以你得提取务必准确，如果用户没有提到任何和代码相关的关键字，你返回给我空字符串也没有任何问题
比如说你判断用户提到了某些工程名称和方法名称，你要这么返回给我'project_name':projectName1,projectName2,'method_name':methodName1,methodName2。
用户问题是 {question}"""
prompt2 = """首先，明确我的需求，从用户问题中提取关键字，以json格式输出结果，不要产生其他多余的输出。我有一个neo4j图数据库，它主要用来存储java代码，它里面有一个节点叫Method，顾名思义，用来存储java方法相关的信息，
Method节点主要的属性有：project_name(项目名称)，class_name(类名)，method_name(方法名)，body(完整的代码)，method_desc(方法的功能描述)。现在有个问题需要你解决，
从下面的用户问题中提取代码相关的关键字，我要用这些关键字去检索对应的Method节点的属性，所以你得提取务必准确，如果用户没有提到任何和代码相关的关键字，你返回给我空字符串也没有任何问题
比如说你判断用户提到了某些项目名称和方法名称，你要以json格式返回给我'project_name':[projectName1,projectName2],'method_name':[methodName1,methodName2]。
用户问题是 {question}"""


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
RETURN method.body + '\n' + param_classes_text + '\n' + called_methods_text AS text, similarity AS score, {source: method.full_class_name} AS metadata
"""

query4 = """
WITH node AS method, score AS similarity
RETURN method.body AS text, similarity AS score, {source: method.full_class_name,class_name:method.class_name} AS metadata
"""
query5 = """
MATCH (m:Method)
WHERE m.class_name = $query_class_name
RETURN m
"""









general_user_template = "Question:```{question}```"
neo4j_graph = Neo4jGraph(url=url, username=username, password=password)
# Vector + Knowledge Graph response
question = "在help项目中，有个java方法叫addChatGptSystemConfig，请对这个方法的每一处代码生成详细的测试用例，包括它调用的其他方法"
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
    print(result["output_text"])        

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



# kg_qa = RetrievalQAWithSourcesChain(
#     combine_documents_chain=qa_chain,
#     retriever=kg.as_retriever(search_kwargs={"k": 20}),
#     reduce_k_below_max_tokens=False,
#     max_tokens_limit=3375,
# )

# json_str1 = json.dumps(msg1, ensure_ascii=False, indent=4)
# print(json_str1)
# msg2 = chain.invoke({"question": "在employee-center项目中，有个方法的内容是对feign进行功能增强，我想了解这部分功能是如何实现的"})
# json_str2 = json.dumps(msg2, ensure_ascii=False, indent=4)
# print(json_str2)