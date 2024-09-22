# from langchain_ollama import ChatOllama
from langchain_community.chat_models import ChatOllama
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


def configure_llm_only_chain(llm):
    # LLM only response
    template = """
    You are a helpful assistant that helps a support agent with answering programming questions.
    If you don't know the answer, just say that you don't know, you must not make up an answer.
    """
    system_message_prompt = SystemMessagePromptTemplate.from_template(template)
    human_template = "{question}"
    human_message_prompt = HumanMessagePromptTemplate.from_template(human_template)
    chat_prompt = ChatPromptTemplate.from_messages(
        [system_message_prompt, human_message_prompt]
    )

    def generate_llm_output(
        user_input: str, callbacks: List[Any], prompt=chat_prompt
    ) -> str:
        chain = prompt | llm
        answer = chain.invoke(
            {"question": user_input}, config={"callbacks": callbacks}
        ).content
        return {"answer": answer}

    return generate_llm_output
load_dotenv(".env")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
url = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")

general_system_template = """ 
你是一个java代码高手，我会在上下文中提供几个关键的代码片段，代码片段是有结构的，每个片段用//------//分割,开头的一个java方法是非常重要的核心方法，接下来的代码片段会是核心方法的参数定义、核心方法调用的其他方法，
所以我提供的代码片段是非常有用的，你应该参考代码片段回答问题。
当你发现上下文中的某段代码非常有用时，请在最后的回复中加上代码。
如果你不知道答案，就直接说不知道，不要试图编造答案。
如果我没有提供代码片段，你就正常回答问题。
----
{summaries}
----
你生成的每个答案都应在末尾包含一个部分，这部分包含代码
"""
general_user_template = "Question:```{question}```"
messages = [
    SystemMessagePromptTemplate.from_template(general_system_template),
    HumanMessagePromptTemplate.from_template(general_user_template),
]
qa_prompt = ChatPromptTemplate.from_messages(messages)
print(qa_prompt)