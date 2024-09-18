from langchain_community.graphs import Neo4jGraph
import os
from streamlit.logger import get_logger
import json
url = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
embedding_model_name = os.getenv("EMBEDDING_MODEL")
# Remapping for Langchain Neo4j integration
os.environ["NEO4J_URL"] = url

logger = get_logger(__name__)


neo4j_graph = Neo4jGraph(url=url, username=username, password=password)

query = '''
MATCH (u:Method)
RETURN u
'''
method_result = neo4j_graph.query(query)
for method in method_result: 
    method_invocation = json.loads(method['u']['method_invocation_map'])
    for key in method_invocation:
        if 'methods' in method_invocation[key]:
            
            # 能找到方法所在的package
            full_package_split = key.split(".")
            if len(full_package_split) > 1:
                class_name = key
                method_name_list = []
                for key1 in method_invocation[key]['methods']:
                    method_name = key1.split("(", 1)[0]
                    method_name_list.append(method_name)
                method_name_str = ', '.join([f"'{name}'" for name in method_name_list])
                interface_class = full_package_split[-1]
                query_invocation_method = f'''
                MATCH (u:Method)
                WHERE (u.full_class_name = '{class_name}' OR u.implements = '{interface_class}') AND u.method_name IN [{method_name_str}] and u.class_type = 'Class'
                RETURN u
                '''
                invocation_method_result = neo4j_graph.query(query_invocation_method)
                # 根据查找的结果建立关系
                for record in invocation_method_result:
                    call_method_id = record['u']['method_id']  # 获取查询结果节点的ID
                    create_relationship_query = f'''
                    MATCH (current:Method {{method_id: '{method['u']['method_id']}'}})
                    MATCH (target:Method) WHERE target.method_id = '{call_method_id}'
                    CREATE (current)-[:CALLS]->(target)
                    '''
                    neo4j_graph.query(create_relationship_query)
                print(f"Key: {key}, Value: {method_invocation[key]['methods']},full_class_mame:{method['u']['full_class_name']}")
            else:
                 # todo 这个地方 首先要根据方法的名称和class_type = 'Class'搜索方法，然后在根据方法所在的类是否被本类import，最后在同一个package下面的方法是不会import的，这个逻辑也要处理。 
                 print("")
    # 处理参数
    parameters_list = json.loads(method['u']['parameters'])
    for param in parameters_list:
        parameter_type = param["parameter_type"]
        query_parameter = f'''
        MATCH (c:RequestClass)
        WHERE c.class_name = '{parameter_type}' AND c.class_type = 'Class'
        RETURN c
        '''
        parameter_result = neo4j_graph.query(query_parameter)
        for param_detail_info in parameter_result:
            class_request_id = param_detail_info['c']['class_request_id']
            create_relationship_query = f'''
            MATCH (current:Method {{method_id: '{method['u']['method_id']}'}})
            MATCH (target:RequestClass) WHERE target.class_request_id = '{class_request_id}'
            CREATE (current)-[:PARAM]->(target)
            '''
            neo4j_graph.query(create_relationship_query)


