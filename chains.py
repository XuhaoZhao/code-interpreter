from langchain_community.embeddings import OllamaEmbeddings
# from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
# from sentence_transformers import SentenceTransformer
from utils import BaseLogger, extract_title_and_question
import config as globalConfig
import os

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