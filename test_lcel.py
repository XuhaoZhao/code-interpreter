from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_models import ChatOllama
from langchain_core.output_parsers import JsonOutputParser
import config as globalConfig
from dotenv import load_dotenv
import os
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate
)
from typing import List, Any
from langchain_core.messages import AIMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from typing import List
from langchain.llms.fake import FakeListLLM


load_dotenv(".env")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
url = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
llm_name = os.getenv("LLM")
# llm = ChatOllama(
#         temperature=0,
#         base_url='http://js1.blockelite.cn:16281',
#         model=llm_name,
#         # streaming=True,
#         # seed=2,
#         top_k=10,  # A higher value (100) will give more diverse answers, while a lower value (10) will be more conservative.
#         top_p=0.3,  # Higher value (0.95) will lead to more diverse text, while a lower value (0.5) will generate more focused text.
#         num_ctx=3072,  # Sets the size of the context window used to generate the next token.
#     )
responses = ["窗前明月光\n低头鞋两双"]
llm = FakeListLLM(responses=responses)
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
promp_second = ChatPromptTemplate.from_template(prompt2)
parser = JsonOutputParser(pydantic_object=Joke)
chain = promp_second | llm | parser
msg1 = chain.invoke({"question": "在help项目中，有个方法的功能是发起esb请求，还有个方法是发起http请求，请给我这些方法的代码"})
print(msg1)

# msg2 = chain.invoke({"question": "在employee-center项目中，有个方法的内容是对feign进行功能增强，我想了解这部分功能是如何实现的"})
# print(msg2)