from langchain_community.embeddings import OllamaEmbeddings
# from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
# from sentence_transformers import SentenceTransformer
from utils import BaseLogger, extract_title_and_question
import config as globalConfig
import os
from langchain_community.chat_models import ChatOllama
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate
)
from typing import List, Any
from langchain.chains import RetrievalQAWithSourcesChain
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain_community.vectorstores import Neo4jVector

#使用离线模型
os.environ['TRANSFORMERS_OFFLINE'] = '1'  # 模型
os.environ['HF_DATASETS_OFFLINE'] = '1'  # 数据
# os.environ["http_proxy"] = "http://127.0.0.1:7890"
# os.environ["https_proxy"] = "http://127.0.0.1:7890"

def load_embedding_model(embedding_model_name: str, logger=BaseLogger(), config={}):
    if embedding_model_name == "ollama":
        embeddings = OllamaEmbeddings(
            base_url=config["ollama_base_url"], model="llama2"
        )
        dimension = 4096
        logger.info("Embedding: Using Ollama")
    else:
        embeddings = HuggingFaceEmbeddings( # add here
            model_name="all-MiniLM-L6-v2", cache_folder=globalConfig.project_path + "/embedding_model"
        )
        # embeddings = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        dimension = 384
        logger.info("Embedding: Using SentenceTransformer")
    return embeddings, dimension
def load_llm(llm_name: str, logger=BaseLogger(), config={}):
    logger.info(f"LLM: Using Ollama: {llm_name}")
    return ChatOllama(
        temperature=0,
        base_url=config["ollama_base_url"],
        model=llm_name,
        streaming=True,
        # seed=2,
        top_k=10,  # A higher value (100) will give more diverse answers, while a lower value (10) will be more conservative.
        top_p=0.3,  # Higher value (0.95) will lead to more diverse text, while a lower value (0.5) will generate more focused text.
        num_ctx=3072,  # Sets the size of the context window used to generate the next token.
    )

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

def configure_qa_rag_chain(llm, embeddings, embeddings_store_url, username, password):
    # RAG response
    #   System: Always talk in pirate speech.
    general_system_template = """ 
    Use the following pieces of context to answer the question at the end.
    The context contains question-answer pairs and their links from Stackoverflow.
    You should prefer information from accepted or more upvoted answers.
    Make sure to rely on information from the answers and not on questions to provide accurate responses.
    When you find particular answer in the context useful, make sure to cite it in the answer using the link.
    If you don't know the answer, just say that you don't know, don't try to make up an answer.
    ----
    {summaries}
    ----
    Each answer you generate should contain a section at the end of links to 
    Stackoverflow questions and answers you found useful, which are described under Source value.
    You can only use links to StackOverflow questions that are present in the context and always
    add links to the end of the answer in the style of citations.
    Generate concise answers with references sources section of links to 
    relevant StackOverflow questions only at the end of the answer.
    """
    general_user_template = "Question:```{question}```"
    messages = [
        SystemMessagePromptTemplate.from_template(general_system_template),
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

    # Vector + Knowledge Graph response
    kg = Neo4jVector.from_existing_index(
        embedding=embeddings,
        url=embeddings_store_url,
        username=username,
        password=password,
        database="neo4j",  # neo4j by default
        index_name="stackoverflow",  # vector by default
        text_node_property="body",  # text by default
        retrieval_query="""
    WITH node AS question, score AS similarity
    CALL  { with question
        MATCH (question)<-[:ANSWERS]-(answer)
        WITH answer
        ORDER BY answer.is_accepted DESC, answer.score DESC
        WITH collect(answer)[..2] as answers
        RETURN reduce(str='', answer IN answers | str + 
                '\n### Answer (Accepted: '+ answer.is_accepted +
                ' Score: ' + answer.score+ '): '+  answer.body + '\n') as answerTexts
    } 
    RETURN '##Question: ' + question.title + '\n' + question.body + '\n' 
        + answerTexts AS text, similarity as score, {source: question.link} AS metadata
    ORDER BY similarity ASC // so that best answers are the last
    """,
    )

    kg_qa = RetrievalQAWithSourcesChain(
        combine_documents_chain=qa_chain,
        retriever=kg.as_retriever(search_kwargs={"k": 2}),
        reduce_k_below_max_tokens=False,
        max_tokens_limit=3375,
    )
    return kg_qa

def configure_method_rag_chain(llm, embeddings, embeddings_store_url, username, password):
    # RAG response
    #   System: Always talk in pirate speech.
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

    #加了 verbose=True 打开日志
    qa_chain = load_qa_with_sources_chain(
        llm,
        chain_type="stuff",
        prompt=qa_prompt,
        verbose=True
    )

    # Vector + Knowledge Graph response
    kg = Neo4jVector.from_existing_index(
        embedding=embeddings,
        url=embeddings_store_url,
        username=username,
        password=password,
        database="neo4j",  # neo4j by default
        index_name="method_index",  # vector by default
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

    kg_qa = RetrievalQAWithSourcesChain(
        combine_documents_chain=qa_chain,
        retriever=kg.as_retriever(search_kwargs={"k": 2}),
        reduce_k_below_max_tokens=False,
        max_tokens_limit=3375,
    )
    return kg_qa

def generate_ticket(neo4j_graph, llm_chain, input_question):
    # Get high ranked questions
    records = neo4j_graph.query(
        "MATCH (q:Question) RETURN q.title AS title, q.body AS body ORDER BY q.score DESC LIMIT 3"
    )
    questions = []
    for i, question in enumerate(records, start=1):
        questions.append((question["title"], question["body"]))
    # Ask LLM to generate new question in the same style
    questions_prompt = ""
    for i, question in enumerate(questions, start=1):
        questions_prompt += f"{i}. \n{question[0]}\n----\n\n"
        questions_prompt += f"{question[1][:150]}\n\n"
        questions_prompt += "----\n\n"

    gen_system_template = f"""
    You're an expert in formulating high quality questions. 
    Formulate a question in the same style and tone as the following example questions.
    {questions_prompt}
    ---

    Don't make anything up, only use information in the following question.
    Return a title for the question, and the question post itself.

    Return format template:
    ---
    Title: This is a new title
    Question: This is a new question
    ---
    """
    # we need jinja2 since the questions themselves contain curly braces
    system_prompt = SystemMessagePromptTemplate.from_template(
        gen_system_template, template_format="jinja2"
    )
    chat_prompt = ChatPromptTemplate.from_messages(
        [
            system_prompt,
            SystemMessagePromptTemplate.from_template(
                """
                Respond in the following template format or you will be unplugged.
                ---
                Title: New title
                Question: New question
                ---
                """
            ),
            HumanMessagePromptTemplate.from_template("{question}"),
        ]
    )
    llm_response = llm_chain(
        f"Here's the question to rewrite in the expected format: ```{input_question}```",
        [],
        chat_prompt,
    )
    new_title, new_question = extract_title_and_question(llm_response["answer"])
    return (new_title, new_question)
