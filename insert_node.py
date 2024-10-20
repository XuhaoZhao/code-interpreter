
import json
import os
import sys
import time
import fnmatch
import config
from database import SqliteHelper
from java_parse import JavaParse, calculate_similar_score_method_params
from chains import load_embedding_model
from streamlit.logger import get_logger
def _get_project_files(project_dir):
    file_lists = []
    for root, dirs, files in os.walk(project_dir):
        if '.git' in root or os.path.join('src', 'test') in root:
            continue
        for file in files:
            ignore = False
            
            filepath = os.path.join(root, file)
            for pattern in config.ignore_file:
                if fnmatch.fnmatch(filepath, pattern):
                    ignore = True
                    break
            if ignore:
                continue
            filepath = filepath.replace('\\', '/')
            file_lists.append(filepath)
    return file_lists
commit_first = '5afb04e31e10c491e0f8e7e1506b599bd2d683ec'
commit_second = '41b3bb1712f9dba00a7b76d772187ce7865c9200'
branch_name = 'master'
username = 'XuhaoZhao'
commit_or_branch_new = commit_first[0: 7] if len(commit_first) > 7 else commit_first
commit_or_branch_old = commit_second[0: 7] if len(commit_second) > 7 else commit_second
sqlite = SqliteHelper(config.db_path + '/' + username + '_jcci.db')
git_url = 'https://github.com/CodePhiliaX/Chat2DB'
# git_url = 'https://github.com/spring-cloud/spring-cloud-consul'
project_name = git_url.split('/')[-1].split('.git')[0]
project_id = sqlite.add_project(project_name, git_url, branch_name,commit_or_branch_new,commit_or_branch_old)
file_path = os.path.join(config.project_path, project_name)
file_path_list = _get_project_files(file_path)

java_parse = JavaParse(sqlite.db_path, project_id)
java_parse.parse_java_file_list(file_path_list, commit_or_branch_new)

logger = get_logger(__name__)
embedding_model_name = os.getenv("EMBEDDING_MODEL")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
embeddings, dimension = load_embedding_model(embedding_model_name, config={"ollama_base_url": ollama_base_url}, logger=logger)
question_text = "hi everyone"
embeddings_data = embeddings.embed_query(question_text)

print(dimension)
# print(embeddings_data.tolist())