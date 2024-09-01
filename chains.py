from langchain_community.embeddings import OllamaEmbeddings
# from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
# from sentence_transformers import SentenceTransformer
from utils import BaseLogger, extract_title_and_question
import config as globalConfig
import os
from langchain_community.chat_models import ChatOllama
#使用离线模型
os.environ['TRANSFORMERS_OFFLINE'] = '1'  # 模型
os.environ['HF_DATASETS_OFFLINE'] = '1'  # 数据

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