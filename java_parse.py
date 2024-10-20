import os
import sys
import logging
import json
import javalang
from concurrent.futures import ThreadPoolExecutor, as_completed
from database import SqliteHelper
from constant import ENTITY, RETURN_TYPE, PARAMETERS, BODY, METHODS, FIELDS, \
    PARAMETER_TYPE_METHOD_INVOCATION_UNKNOWN, JAVA_BASIC_TYPE, MAPPING_LIST, JAVA_UTIL_TYPE
import config as config
from chains import load_embedding_model
from streamlit.logger import get_logger


import os
import requests
from dotenv import load_dotenv
from langchain_community.graphs import Neo4jGraph
from utils import create_constraint_for_method_node, create_method_vector_index,create_constraint_for_class_request_node
from chains import load_embedding_model
from streamlit.logger import get_logger
import uuid

url = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
embedding_model_name = os.getenv("EMBEDDING_MODEL")
# Remapping for Langchain Neo4j integration
os.environ["NEO4J_URL"] = url

logger = get_logger(__name__)


neo4j_graph = Neo4jGraph(url=url, username=username, password=password)

sys.setrecursionlimit(10000)
logging.basicConfig(format='%(asctime)s %(message)s', level=logging.DEBUG)

logger = get_logger(__name__)
embedding_model_name = os.getenv("EMBEDDING_MODEL")
ollama_base_url = os.getenv("OLLAMA_BASE_URL")
embeddings, dimension = load_embedding_model(embedding_model_name, config={"ollama_base_url": ollama_base_url}, logger=logger)
create_constraint_for_method_node(neo4j_graph)
create_constraint_for_class_request_node(neo4j_graph)
create_method_vector_index(neo4j_graph, dimension)


def calculate_similar_score_method_params(except_method_param_list, method_param_list):
    score = 0
    positions = {}

    # 记录list1中每个元素的位置
    for i, item in enumerate(except_method_param_list):
        positions[item] = i

    # 遍历list2,计算分数
    for i, item in enumerate(method_param_list):
        if item in positions:
            score += 1
            score -= abs(i - positions[item])

    return score


class JavaParse(object):
    def __init__(self, db_path, project_id):
        self.project_id = project_id
        self.sqlite = SqliteHelper(db_path)
        self.sibling_dirs = []
        self.parsed_filepath = []

    def _handle_extends(self, extends, import_list: list, package_name):
        if isinstance(extends, list):
            extends_package_class_list = []
            extends_class = extends[0].name
            extends_package_class = self._get_extends_class_full_package(extends_class, import_list, package_name)
            extends_package_class_list.append(extends_package_class)
            if 'arguments' in extends[0].attrs and extends[0].arguments:
                extends_arguments = extends[0].arguments
                extends_argument_classes = []
                for extends_argument in extends_arguments:
                    if type(extends_argument) == javalang.tree.TypeArgument:
                        extends_argument_class = extends_argument.type.name
                    else:
                        extends_argument_class = extends_argument.name
                    extends_argument_package_class = self._get_extends_class_full_package(extends_argument_class, import_list, package_name)
                    extends_argument_classes.append(extends_argument_package_class)
                extends_package_class_list += extends_argument_classes
                return extends_package_class + '<' + ','.join(extends_argument_classes) + '>', extends_package_class_list
            else:
                return extends_package_class, [extends_package_class]
        else:
            extends_class = self._get_extends_class_full_package(extends.name, import_list, package_name)
            return extends_class, [extends_class]

    def _get_extends_class_full_package(self, extends_class, import_list, package_name):
        extends_in_imports = [import_obj for import_obj in import_list if extends_class in import_obj['import_path']]
        return extends_in_imports[0]['import_path'] if extends_in_imports else package_name + '.' + extends_class

    def _parse_class(self, node, filepath: str, package_name: str, import_list: list, commit_or_branch: str, parse_import_first,lines):
        # 处理class信息
        documentation = node.documentation
        class_name = node.name
        package_class = package_name + '.' + node.name
        class_type = type(node).__name__.replace('Declaration', '')
        access_modifier = [m for m in list(node.modifiers) if m.startswith('p')][0] if list([m for m in list(node.modifiers) if m.startswith('p')]) else 'public'
        annotations_json = json.dumps(node.annotations, default=lambda obj: obj.__dict__)
        is_controller, controller_base_url = self._judge_is_controller(node.annotations)
        extends_package_class = None
        if 'extends' in node.attrs and node.extends:
            extends_package_class, extends_package_class_list = self._handle_extends(node.extends, import_list, package_name)
            package_path = package_class.replace('.', '/') + '.java'
            base_filepath = filepath.replace(package_path, '')
            for extends_package_class_item in extends_package_class_list:
                if extends_package_class_item == package_class:
                    continue
                extends_class_filepath = base_filepath + extends_package_class_item.replace('.', '/') + '.java'
                self.parse_java_file(extends_class_filepath, commit_or_branch, parse_import_first=parse_import_first)
        implements = ','.join([implement.name for implement in node.implements]) if 'implements' in node.attrs and node.implements else None
        class_id, new_add = self.sqlite.add_class(filepath.replace('\\', '/'), access_modifier, class_type, class_name, package_name, extends_package_class, self.project_id, implements, annotations_json, documentation, is_controller, controller_base_url, commit_or_branch)
        if 'Request' in class_name:
            class_db_data = {'class_request_id':uuid.uuid4().hex,'filepath':filepath.replace('\\', '/'),'class_type':class_type,'class_name':class_name,'package_name':package_name,'file_content':"\n".join(lines)}
            create_cypher = """
            CREATE (rc:RequestClass {class_request_id:$class_request_id,filepath: $filepath, class_type: $class_type,class_name:$class_name,package_name:$package_name,file_content:$file_content})
            """
            neo4j_graph.query(create_cypher,class_db_data)


        return class_id, new_add

    def _parse_imports(self, imports):
        import_list = []
        for import_decl in imports:
            import_obj = {
                'import_path': import_decl.path,
                'is_static': import_decl.static,
                'is_wildcard': import_decl.wildcard,
                'start_line': import_decl.position.line,
                'end_line': import_decl.position.line
            }
            import_list.append(import_obj)
        return import_list

    def _parse_fields(self, fields, package_name, class_name, class_id, import_map, filepath):
        field_list = []
        package_class = package_name + "." + class_name
        for field_obj in fields:
            field_annotations = json.dumps(field_obj.annotations, default=lambda obj: obj.__dict__)
            access_modifier = next((m for m in list(field_obj.modifiers) if m.startswith('p')), 'public')
            field_name = field_obj.declarators[0].name
            field_type: str = field_obj.type.name
            if field_type.lower() in JAVA_BASIC_TYPE:
                pass
            elif field_type in JAVA_UTIL_TYPE and ('java.util' in import_map.values() or 'java.util.' + field_type in import_map.values()):
                var_declarator_type_arguments = self._deal_arguments_type(field_obj.type.arguments, FIELDS, {}, {}, {}, import_map, {}, package_name, filepath, [], {}, class_id)
                if var_declarator_type_arguments:
                    field_type = field_type + '<' + '#'.join(var_declarator_type_arguments) + '>'
            elif field_type in import_map.keys():
                field_type = import_map.get(field_type)
            else:
                in_import = False
                for key in import_map.keys():
                    if key[0].isupper():
                        continue
                    field_type_db = self.sqlite.select_data(f'select class_id from class where project_id={self.project_id} and package_name = "{import_map.get(key)}" and class_name = "{field_type}" limit 1')
                    if field_type_db:
                        field_type = f'{import_map.get(key)}.{field_type}'
                        in_import = True
                        break
                if not in_import:
                    field_type_db = self.sqlite.select_data(f'select class_id from class where project_id={self.project_id} and package_name = "{package_class}" and class_name = "{field_type}" limit 1')
                    if field_type_db:
                        field_type = f'{package_class}.{field_type}'
                    else:
                        field_type = package_name + '.' + field_type
                    import_map[field_obj.type.name] = field_type
                else:
                    import_map[field_obj.type.name] = field_type
            is_static = 'static' in list(field_obj.modifiers)
            documentation = field_obj.documentation
            start_line = field_obj.position.line if not field_obj.annotations else field_obj.annotations[0].position.line
            end_line = self._get_method_end_line(field_obj)
            field_obj = {
                'class_id': class_id,
                'project_id': self.project_id,
                'annotations': field_annotations,
                'access_modifier': access_modifier,
                'field_type': field_type,
                'field_name': field_name,
                'is_static': is_static,
                'documentation': documentation,
                'start_line': start_line,
                'end_line': end_line
            }
            field_list.append(field_obj)
        self.sqlite.update_data(f'DELETE FROM field where class_id={class_id}')
        self.sqlite.insert_data('field', field_list)
        return field_list

    def _parse_method_body_variable(self, node, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id):
        var_declarator = node.declarators[0].name
        var_declarator_type = self._deal_declarator_type(node.type, BODY, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
        variable_map[var_declarator] = var_declarator_type
        initializer = node.declarators[0].initializer
        if self._is_valid_prefix(var_declarator_type):
            self._add_entity_used_to_method_invocation(method_invocation, var_declarator_type, BODY)
        if not initializer:
            return var_declarator_type
        for init_path, init_node in initializer.filter(javalang.tree.MemberReference):
            self._deal_member_reference(init_node, parameters_map, variable_map, field_map, import_map, method_invocation, BODY, package_name, filepath)
        return var_declarator_type

    def _parse_method_body_class_creator(self, node, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id):
        qualifier = node.type.name
        node_line = node.position.line if node.position else None
        qualifier_type = self._get_var_type(qualifier, parameters_map, variable_map, field_map, import_map, method_invocation, BODY, package_name, filepath)
        node_arguments = self._deal_var_type(node.arguments, BODY, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
        if node.selectors is None or not node_arguments:
            self._add_entity_used_to_method_invocation(method_invocation, qualifier_type, BODY)
        else:
            if node_arguments:
                qualifier_package_class, method_params, method_db = self._find_method_in_package_class(qualifier_type, qualifier, node_arguments)
                if not method_db:
                    return qualifier_type
                self._add_method_used_to_method_invocation(method_invocation, qualifier_type, method_params, [node_line])
            self._parse_node_selectors(node.selectors, qualifier_type, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
        if self._is_valid_prefix(qualifier_type):
            self._add_entity_used_to_method_invocation(method_invocation, qualifier_type, BODY)
        return qualifier_type

    def _parse_method_body_method_invocation(self, node, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id):
        qualifier = node.qualifier
        member = node.member
        return_type = PARAMETER_TYPE_METHOD_INVOCATION_UNKNOWN
        # 类静态方法调用
        if not qualifier and not member[0].islower():
            qualifier_type = self._get_var_type(member, parameters_map, variable_map, field_map, import_map, method_invocation, BODY, package_name, filepath)
            # todo a.b.c
            qualifier_type = self._parse_node_selectors(node.selectors, qualifier_type, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
            return_type = qualifier_type
        elif qualifier:
            qualifier_type = self._get_var_type(qualifier, parameters_map, variable_map, field_map, import_map, method_invocation, BODY, package_name, filepath)
            node_arguments = self._deal_var_type(node.arguments, BODY, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
            node_line = node.position.line
            node_arguments = [n for n in node_arguments if n]
            node_method = f'{member}({",".join(node_arguments)})'
            # node_method = f'{member}(),{",".join(node_arguments)}'
            self._add_method_used_to_method_invocation(method_invocation, qualifier_type, node_method, [node_line])
            if self._is_valid_prefix(qualifier_type):
                qualifier_package_class, method_params, method_db = self._find_method_in_package_class(qualifier_type, member, node_arguments)
                if not method_db:
                    return qualifier_type
                if method_params != node_method:
                    self._add_method_used_to_method_invocation(method_invocation, qualifier_type, method_params, [node_line])
                method_db_type = method_db.get("return_type", method_db.get("field_type"))
            elif qualifier_type.startswith('Map<') and member == 'get':
                method_db_type = qualifier_type.split('#')[1].split('>')[0]
            else:
                method_db_type = qualifier_type
            method_db_type = self._parse_node_selectors(node.selectors, method_db_type, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
            return_type = method_db_type
        # 在一个类的方法或父类方法
        elif member:
            class_db = self.sqlite.select_data(f'SELECT package_name, class_name, extends_class FROM class where project_id = {self.project_id} and class_id={class_id} limit 1')[0]
            package_class = class_db['package_name'] + '.' + class_db['class_name']
            node_line = node.position.line
            node_arguments = self._deal_var_type(node.arguments, BODY, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
            # todo 同级方法, 判断参数长度，不精确
            if method_name_entity_map.get(member):
                same_class_method = None
                max_score = -float('inf')
                for method_item in methods:
                    if method_item.name != member or len(node.arguments) != len(method_item.parameters):
                        continue
                    method_item_param_types = [self._deal_declarator_type(parameter.type, PARAMETERS, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id) for parameter in method_item.parameters]
                    score = calculate_similar_score_method_params(node_arguments, method_item_param_types)
                    if score > max_score:
                        max_score = score
                        same_class_method = method_item
                if same_class_method:
                    node_arguments = self._deal_var_type(same_class_method.parameters, BODY, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
                    node_method = f'{member}({",".join(node_arguments)})'
                    # node_method = f'{member}(),{",".join(node_arguments)}'
                    self._add_method_used_to_method_invocation(method_invocation, package_class, node_method, [node_line])
                    return_type = self._deal_declarator_type(same_class_method.return_type, BODY, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
            # todo 继承方法
            elif class_db['extends_class']:
                extends_package_class, method_params, method_db = self._find_method_in_package_class(class_db['extends_class'], member, node_arguments)
                if extends_package_class:
                    self._add_method_used_to_method_invocation(method_invocation, extends_package_class, method_params, [node_line])
                    return_type = method_db.get("return_type", method_db.get("field_type"))
        return return_type

    def _parse_node_selectors(self, selectors, qualifier_type, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id):
        if not selectors:
            return qualifier_type
        selector_qualifier_type = qualifier_type
        for selector in selectors:
            if type(selector) == javalang.tree.ArraySelector:
                continue
            selector_member = selector.member
            if type(selector) == javalang.tree.MethodInvocation:
                self._parse_method_body_method_invocation(selector, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
                selector_arguments = self._deal_var_type(selector.arguments, BODY, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
                selector_line = selector.position.line
                selector_method = f'{selector_member}({",".join(selector_arguments)})'
                # selector_method = f'{selector_member}(),{",".join(selector_arguments)}'
                if self._is_valid_prefix(selector_qualifier_type):
                    self._add_method_used_to_method_invocation(method_invocation, selector_qualifier_type, selector_method, [selector_line])
                selector_package_class, method_params, method_db = self._find_method_in_package_class(selector_qualifier_type, selector_member, selector_arguments)
                if not method_db:
                    continue
                method_db_type = method_db.get("return_type", method_db.get("field_type"))
                selector_qualifier_type = method_db_type
            elif type(selector) == javalang.tree.MemberReference:
                self._deal_member_reference(selector, parameters_map, variable_map, field_map, import_map, method_invocation, BODY, package_name, filepath)
                selector_qualifier_type = self._get_var_type(selector_member, parameters_map, variable_map, field_map, import_map, method_invocation, BODY, package_name, filepath)
                if self._is_valid_prefix(selector_qualifier_type):
                    self._add_field_used_to_method_invocation(method_invocation, selector_qualifier_type, selector_member, [None])
        return selector_qualifier_type

    def _parse_enum(self, enum_body, lines, class_id, import_map, field_map, package_name, filepath):
        constants = enum_body.constants
        field_list = []
        init_line = 0
        for constant in constants:
            constant_type = 'ENUM'
            constant_name = constant.name
            arguments = constant.arguments
            start_text = constant_name if not arguments else constant_name + '('
            start_lines = [lines.index(line) for line in lines if line.strip().startswith(start_text)]
            if start_lines:
                start_line = start_lines[0] + 1
                init_line = start_line
            else:
                start_line = init_line
            end_line = start_line
            field_obj = {
                'class_id': class_id,
                'project_id': self.project_id,
                'annotations': None,
                'access_modifier': 'public',
                'field_type': constant_type,
                'field_name': constant_name,
                'is_static': True,
                'documentation': None,
                'start_line': start_line,
                'end_line': end_line
            }
            field_list.append(field_obj)
        self.sqlite.insert_data('field', field_list)

    def _parse_constructors(self, constructors, lines, class_id, import_map, field_map, package_name, filepath):
        all_method = []
        for constructor in constructors:
            method_invocation = {}
            cs_name = constructor.name
            annotations = json.dumps(constructor.annotations, default=lambda obj: obj.__dict__)  # annotations

            access_modifier = [m for m in list(constructor.modifiers) if m.startswith('p')][0] if list([m for m in list(constructor.modifiers) if m.startswith('p')]) else 'public'
            parameters = []
            parameters_map = {}
            for parameter in constructor.parameters:
                parameter_obj = {
                    'parameter_type': self._deal_declarator_type(parameter.type, PARAMETERS, parameters_map, {}, field_map, import_map, method_invocation, package_name, filepath, [], {}, class_id),
                    'parameter_name': parameter.name,
                    'parameter_varargs': parameter.varargs
                }
                parameters.append(parameter_obj)
            parameters_map = {parameter['parameter_name']: parameter['parameter_type'] for parameter in parameters}
            return_type = package_name + '.' + cs_name
            start_line = constructor.position.line
            if constructor.annotations:
                start_line = constructor.annotations[0].position.line
            end_line = self._get_method_end_line(constructor)
            cs_body = lines[start_line - 1: end_line + 1]
            for body in constructor.body:
                for path, node in body.filter(javalang.tree.This):
                    self._parse_node_selectors(node.selectors, None, {}, {}, field_map, import_map, method_invocation, package_name, filepath, [], {}, class_id)

            method_db = {
                'class_id': class_id,
                'project_id': self.project_id,
                'annotations': annotations,
                'access_modifier': access_modifier,
                'return_type': return_type,
                'method_name': cs_name,
                'parameters': json.dumps(parameters),
                'body': json.dumps(cs_body),
                'method_invocation_map': json.dumps(method_invocation),
                'is_static': False,
                'is_abstract': False,
                'is_api': False,
                'api_path': None,
                'start_line': start_line,
                'end_line': end_line,
                'documentation': constructor.documentation
            }
            all_method.append(method_db)
        self.sqlite.insert_data('methods', all_method)

    def _parse_method(self, methods, lines, class_id, import_map, field_map, package_name, filepath,methods_end_line):
        # 处理 methods
        all_method = []
        all_method_graph = []
        class_db = self.sqlite.select_data(f'SELECT class_type,class_name,package_name, controller_base_url, implements FROM class WHERE project_id = {self.project_id} and class_id = {class_id}')[0]
        base_url = class_db['controller_base_url'] if class_db['controller_base_url'] else ''
        class_implements = class_db['implements']
        method_name_entity_map = {method.name: method for method in methods}
        for method_obj in methods:
            method_invocation = {}
            variable_map = {}
            method_name = method_obj.name
            documentation = method_obj.documentation  # document
            annotations = json.dumps(method_obj.annotations, default=lambda obj: obj.__dict__)  # annotations
            is_override_method = 'Override' in annotations
            is_api, api_path = self._judge_is_api(method_obj.annotations, base_url, method_name)
            if not is_api and class_implements and is_override_method:
                class_implements_list = class_implements.split(',')
                class_implements_obj = self.sqlite.select_data(f'''select m.is_api, m.api_path from methods m left join class c on c.class_id = m.class_id 
                                                                where c.project_id = {self.project_id} and m.method_name = '{method_name}' and c.class_name in ("{'","'.join(class_implements_list)}")''')
                if class_implements_obj:
                    is_api = class_implements_obj[0]['is_api']
                    api_path = class_implements_obj[0]['api_path']
            access_modifier = [m for m in list(method_obj.modifiers) if m.startswith('p')][0] if list([m for m in list(method_obj.modifiers) if m.startswith('p')]) else 'public'
            is_static = 'static' in list(method_obj.modifiers)
            is_abstract = 'abstract' in list(method_obj.modifiers)
            parameters = []
            parameters_map = {}
            type_parameters = method_obj.type_parameters if method_obj.type_parameters else []
            for type_parameter in type_parameters:
                type_parameter_name = type_parameter.name
                type_parameter_extends_name = type_parameter.extends[0].name if type_parameter.extends else None
                if type_parameter_extends_name:
                    type_parameter_extends_name_type = self._deal_declarator_type(type_parameter.extends[0], PARAMETERS, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
                else:
                    type_parameter_extends_name_type = type_parameter_name
                parameters_map[type_parameter_name] = type_parameter_extends_name_type
            for parameter in method_obj.parameters:
                parameter_obj = {
                    'parameter_type': self._deal_declarator_type(parameter.type, PARAMETERS, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id),
                    'parameter_name': parameter.name,
                    'parameter_varargs': parameter.varargs
                }
                parameters.append(parameter_obj)
            parameters_map.update({parameter['parameter_name']: parameter['parameter_type'] for parameter in parameters})
            # 处理返回对象
            return_type = self._deal_declarator_type(method_obj.return_type, RETURN_TYPE, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
            if self._is_valid_prefix(return_type):
                self._add_entity_used_to_method_invocation(method_invocation, return_type, RETURN_TYPE)
            method_start_line = method_obj.position.line
            if method_obj.annotations:
                method_start_line = method_obj.annotations[0].position.line
            method_end_line = self._get_method_end_line(method_obj)
            if method_name in methods_end_line:
                method_end_line = methods_end_line.get(method_name)['end_line']
                method_end_line = method_end_line - 1
            method_body = lines[method_start_line - 1: method_end_line + 1]

            # 处理方法体
            if not method_obj.body:
                method_obj.body = []
            for body in method_obj.body:
                for path, node in body.filter(javalang.tree.VariableDeclaration):
                    self._parse_method_body_variable(node, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
                for path, node in body.filter(javalang.tree.ClassCreator):
                    self._parse_method_body_class_creator(node, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
                for path, node in body.filter(javalang.tree.This):
                    self._parse_node_selectors(node.selectors, None, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
                for path, node in body.filter(javalang.tree.MethodInvocation):
                    self._parse_method_body_method_invocation(node, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
            method_db = {
                'class_id': class_id,
                'project_id': self.project_id,
                'annotations': annotations,
                'access_modifier': access_modifier,
                'return_type': return_type,
                'method_name': method_name,
                'parameters': json.dumps(parameters),
                'body': json.dumps(method_body),
                'method_invocation_map': json.dumps(method_invocation),
                'is_static': is_static,
                'is_abstract': is_abstract,
                'is_api': is_api,
                'api_path': json.dumps(api_path) if is_api else None,
                'start_line': method_start_line,
                'end_line': method_end_line,
                'documentation': documentation
            }

            try:
                if not documentation:
                    documentation = " "
                doc_embed = embeddings.embed_query(documentation)
                
            except Exception as e:
                logging.error(f"Error insert neo4j {filepath}: {e}")
                return
            
            method_db_graph= {
                'method_id': uuid.uuid4().hex,
                'class_id': class_id,
                'project_id': self.project_id,
                'annotations': annotations,
                'access_modifier': access_modifier,
                'return_type': return_type,
                'method_name': method_name,
                'method_name_embedding': embeddings.embed_query(method_name),
                'parameters': json.dumps(parameters),
                'body': "\n".join(method_body),
                'body_embedding': embeddings.embed_query( "\n".join(method_body)),
                'method_invocation_map': json.dumps(method_invocation),
                'is_static': is_static,
                'is_abstract': is_abstract,
                'is_api': is_api,
                'api_path': json.dumps(api_path) if is_api else None,
                'start_line': method_start_line,
                'end_line': method_end_line,
                'documentation': documentation,
                'documentation_embedding': doc_embed,
                'full_class_name': class_db['package_name'] + '.'+ class_db['class_name'],
                'class_name': class_db['class_name'],
                'class_name_embedding': embeddings.embed_query(class_db['class_name']),
                'class_type': class_db['class_type'],
                'implements': class_db['implements']

            }
            all_method.append(method_db)
            all_method_graph.append(method_db_graph)
        query = """
        UNWIND $all_method_graph AS method_data
        MERGE (method:Method {method_id: method_data.method_id})
        ON CREATE SET 
            method.class_id = method_data.class_id,
            method.project_id = method_data.project_id,
            method.annotations = method_data.annotations,
            method.access_modifier = method_data.access_modifier,
            method.return_type = method_data.return_type,
            method.method_name = method_data.method_name,
            method.method_name_embedding = method_data.method_name_embedding,
            method.parameters = method_data.parameters,
            method.body = method_data.body,
            method.body_embedding = method_data.body_embedding,
            method.method_invocation_map = method_data.method_invocation_map,
            method.is_static = method_data.is_static,
            method.is_abstract = method_data.is_abstract,
            method.is_api = method_data.is_api,
            method.api_path = method_data.api_path,
            method.start_line = method_data.start_line,
            method.end_line = method_data.end_line,
            method.documentation = method_data.documentation,
            method.documentation_embedding = method_data.documentation_embedding,
            method.full_class_name = method_data.full_class_name,
            method.class_name = method_data.class_name,
            method.class_name_embedding = method_data.class_name_embedding,
            method.class_type = method_data.class_type,
            method.implements = method_data.implements
        ON MATCH SET
            method.class_id = method_data.class_id,
            method.project_id = method_data.project_id,
            method.annotations = method_data.annotations,
            method.access_modifier = method_data.access_modifier,
            method.return_type = method_data.return_type,
            method.method_name = method_data.method_name,
            method.method_name_embedding = method_data.method_name_embedding,
            method.parameters = method_data.parameters,
            method.body = method_data.body,
            method.body_embedding = method_data.body_embedding,
            method.method_invocation_map = method_data.method_invocation_map,
            method.is_static = method_data.is_static,
            method.is_abstract = method_data.is_abstract,
            method.is_api = method_data.is_api,
            method.api_path = method_data.api_path,
            method.start_line = method_data.start_line,
            method.end_line = method_data.end_line,
            method.documentation = method_data.documentation,
            method.documentation_embedding = method_data.documentation_embedding,
            method.full_class_name = method_data.full_class_name,
            method.class_name = method_data.class_name,
            method.class_name_embedding = method_data.class_name_embedding,
            method.class_type = method_data.class_type,
            method.implements = method_data.implements
        """
        params = {"all_method_graph":all_method_graph}


        neo4j_graph.query(query, params)

        
        self.sqlite.update_data(f'DELETE FROM methods where class_id={class_id}')
        self.sqlite.insert_data('methods', all_method)

    def _find_method_in_package_class(self, package_class: str, method_name: str, method_arguments):
        if not package_class or not self._is_valid_prefix(package_class):
            return None, None, None
        # 查表有没有记录
        extend_package = '.'.join(package_class.split('.')[0: -1])
        extend_class = package_class.split('.')[-1]
        extend_class_db = self.sqlite.select_data(f'SELECT class_id, package_name, class_name, extends_class, annotations '
                                                  f'FROM class WHERE package_name="{extend_package}" '
                                                  f'AND class_name="{extend_class}" '
                                                  f'AND project_id={self.project_id} limit 1')

        if not extend_class_db:
            return None, None, None
        extend_class_entity = extend_class_db[0]
        extend_class_id = extend_class_entity['class_id']
        methods_db_list = self.sqlite.select_data(f'SELECT method_name, parameters, return_type FROM methods WHERE project_id = {self.project_id} and class_id={extend_class_id} and method_name = "{method_name}"')
        data_in_annotation = [annotation for annotation in json.loads(extend_class_entity['annotations']) if annotation['name'] in ['Data', 'Getter', 'Setter', 'Builder', 'NoArgsConstructor', 'AllArgsConstructor']]
        if not methods_db_list and data_in_annotation and (method_name.startswith('get') or method_name.startswith('set')) and method_name[3:]:
            field_name = method_name[3:]
            field_name = field_name[0].lower() + field_name[1:] if len(field_name) > 1 else field_name[0].lower()
            methods_db_list = self.sqlite.select_data(f'SELECT field_name, field_type FROM field WHERE project_id = {self.project_id} and class_id={extend_class_id} and field_name = "{field_name}"')
        if not methods_db_list and not extend_class_entity['extends_class']:
            return None, None, None
        if not methods_db_list:
            return self._find_method_in_package_class(extend_class_entity['extends_class'], method_name, method_arguments)
        else:
            filter_methods = [method for method in methods_db_list if len(json.loads(method.get('parameters', '[]'))) == len(method_arguments)]
            if not filter_methods:
                return self._find_method_in_package_class(extend_class_entity['extends_class'], method_name, method_arguments)
            # package_class = extend_class_entity['package_name'] + '.' + extend_class_entity['class_name']
            if len(filter_methods) == 1:
                method_db = filter_methods[0]
                method_params = f'{method_db.get("method_name", method_name)}({",".join([param["parameter_type"] for param in json.loads(method_db.get("parameters", "[]"))])})'
                return package_class, method_params, method_db
            else:
                max_score = -float('inf')
                max_score_method = None
                for method_db in filter_methods:
                    method_db_params = [param["parameter_type"] for param in json.loads(method_db.get("parameters", "[]"))]
                    score = calculate_similar_score_method_params(method_arguments, method_db_params)
                    if score > max_score:
                        max_score = score
                        max_score_method = method_db
                if max_score_method is None:
                    max_score_method = filter_methods[0]
                method_params = f'{max_score_method.get("method_name", method_name)}({",".join([param["parameter_type"] for param in json.loads(max_score_method.get("parameters", "[]"))])})'
                return package_class, method_params, max_score_method

    def _get_method_end_line(self, method_obj):
        method_end_line = method_obj.position.line
        while True:
            if isinstance(method_obj, list):
                method_obj = [obj for obj in method_obj if obj and not isinstance(obj, str)]
                if len(method_obj) == 0:
                    break
                length = len(method_obj)
                for i in range(0, length):
                    temp = method_obj[length - 1 - i]
                    if temp is not None:
                        method_obj = temp
                        break
                if method_obj is None:
                    break
            if isinstance(method_obj, list):
                continue
            if hasattr(method_obj, 'position') \
                    and method_obj.position is not None \
                    and method_obj.position.line > method_end_line:
                method_end_line = method_obj.position.line
            if hasattr(method_obj, 'children'):
                method_obj = method_obj.children
            else:
                break
        return method_end_line

    def _get_element_value(self, method_element):
        method_api_path = []
        if type(method_element).__name__ == 'BinaryOperation':
            operandl = method_element.operandl
            operandr = method_element.operandr
            operandl_str = self._get_api_part_route(operandl)
            operandr_str = self._get_api_part_route(operandr)
            method_api_path = [operandl_str + operandr_str]
        elif type(method_element).__name__ == 'MemberReference':
            method_api_path = [method_element.member.replace('"', '')]
        elif type(method_element).__name__ == 'ElementArrayValue':
            method_api_path = self._get_element_with_values(method_element)
        elif method_element.value is not None:
            method_api_path = [method_element.value.replace('"', '')]
        return method_api_path

    def _get_element_with_values(self, method_api_path_obj):
        result = []
        for method_api_value in method_api_path_obj.values:
            result += self._get_element_value(method_api_value)
        return result

    def _get_api_part_route(self, part):
        part_class = type(part).__name__
        if part_class == 'MemberReference':
            return part.member.replace('"', '')
        elif part_class == 'Literal':
            return part.value.replace('"', '')
        else:
            return ''

    def _judge_is_controller(self, annotation_list):
        is_controller = any('Controller' in annotation.name for annotation in annotation_list)
        base_request = ''
        if not is_controller:
            return is_controller, base_request
        for annotation in annotation_list:
            if 'RequestMapping' != annotation.name:
                continue
            if annotation.element is None:
                continue
            if isinstance(annotation.element, list):
                base_request_list = []
                for annotation_element in annotation.element:
                    if annotation_element.name != 'value' and annotation_element.name != 'path':
                        continue
                    if 'values' in annotation_element.value.attrs:
                        base_request_list += self._get_element_with_values(annotation_element.value)
                    else:
                        base_request_list += self._get_element_value(annotation_element.value)
                if len(base_request_list) > 0:
                    base_request = base_request_list[0]
            else:
                if 'value' in annotation.element.attrs:
                    base_request = annotation.element.value.replace('"', '')
                elif 'values' in annotation.element.attrs:
                    base_request = ' || '.join([literal.value for literal in annotation.element.values])
        if is_controller and not base_request.endswith('/'):
            base_request += '/'
        return is_controller, base_request

    def _judge_is_api(self, method_annotations, base_request, method_name):
        api_path_list = []
        req_method_list = []
        method_api_path = []
        is_api = False
        for method_annotation in method_annotations:
            if method_annotation.name not in MAPPING_LIST:
                continue
            is_api = True
            if method_annotation.name != 'RequestMapping':
                req_method_list.append(method_annotation.name.replace('Mapping', ''))
            else:
                if not method_annotation.element:
                    continue
                for method_annotation_element in method_annotation.element:
                    if type(method_annotation_element) == tuple:
                        req_method_list = ['ALL']
                        break
                    if 'name' not in method_annotation_element.attrs or method_annotation_element.name != 'method':
                        continue
                    method_annotation_element_value = method_annotation_element.value
                    if 'member' in method_annotation_element_value.attrs:
                        req_method_list.append(method_annotation_element_value.member)
                    elif 'values' in method_annotation_element_value.attrs:
                        method_annotation_element_values = method_annotation_element_value.values
                        req_method_list += [method_annotation_element_temp.member for
                                            method_annotation_element_temp in
                                            method_annotation_element_values
                                            if 'member' in method_annotation_element_temp.attrs]
            if not isinstance(method_annotation.element, list):
                if method_annotation.element is None:
                    continue
                method_api_path += self._get_element_value(method_annotation.element)
            else:
                method_api_path_list = [method_annotation_element.value for method_annotation_element in method_annotation.element
                                        if method_annotation_element.name == 'path' or method_annotation_element.name == 'value']
                if len(method_api_path_list) == 0:
                    continue
                method_api_path_obj = method_api_path_list[0]
                if 'value' in method_api_path_obj.attrs:
                    method_api_path += [method_api_path_obj.value.replace('"', '')]
                else:
                    if 'values' in method_api_path_obj.attrs:
                        for method_api_value in method_api_path_obj.values:
                            method_api_path += self._get_element_value(method_api_value)
                    else:
                        method_api_path += [method_name + '/cci-unknown']
        if len(method_api_path) == 0:
            method_api_path = ['/']
        for method_api_path_obj in method_api_path:
            if method_api_path_obj.startswith('/'):
                method_api_path_obj = method_api_path_obj[1:]
            api_path = base_request + method_api_path_obj
            if not api_path:
                continue
            if api_path.endswith('/'):
                api_path = api_path[0:-1]
            if len(req_method_list) > 0:
                api_path_list += ['[' + req_method_temp + ']' + api_path for req_method_temp in req_method_list]
            else:
                api_path_list.append('[ALL]' + api_path)
        return is_api, api_path_list

    def _add_entity_used_to_method_invocation(self, method_invocation, package_class, section):
        if package_class not in method_invocation.keys():
            method_invocation[package_class] = {ENTITY: {section: True}}
        elif ENTITY not in method_invocation[package_class].keys():
            method_invocation[package_class][ENTITY] = {section: True}
        elif section not in method_invocation[package_class][ENTITY].keys():
            method_invocation[package_class][ENTITY][section] = True

    def _add_method_used_to_method_invocation(self, method_invocation, package_class, method, lines):
        if package_class not in method_invocation.keys():
            method_invocation[package_class] = {METHODS: {method: lines}}
        elif METHODS not in method_invocation[package_class].keys():
            method_invocation[package_class][METHODS] = {method: lines}
        elif method not in method_invocation[package_class][METHODS].keys():
            method_invocation[package_class][METHODS][method] = lines
        else:
            method_invocation[package_class][METHODS][method] += lines

    def _add_field_used_to_method_invocation(self, method_invocation, package_class, field, lines):
        if package_class not in method_invocation.keys():
            method_invocation[package_class] = {FIELDS: {field: lines}}
        elif FIELDS not in method_invocation[package_class].keys():
            method_invocation[package_class][FIELDS] = {field: lines}
        elif field not in method_invocation[package_class][FIELDS].keys():
            method_invocation[package_class][FIELDS][field] = lines
        else:
            method_invocation[package_class][FIELDS][field] += lines

    def _deal_declarator_type(self, node_type, section, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id):
        if node_type is None:
            return node_type
        if type(node_type) == javalang.tree.BasicType:
            node_name = node_type.name
            if node_name != 'int':
                node_name = node_name[0].upper() + node_name[1:]
            return node_name
        var_declarator_type = self._parse_sub_type(node_type)
        var_declarator_type = self._get_var_type(var_declarator_type, parameters_map, variable_map, field_map, import_map, method_invocation, section, package_name, filepath)
        var_declarator_type_arguments = self._deal_arguments_type(node_type.arguments, section, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
        if var_declarator_type_arguments:
            var_declarator_type = var_declarator_type + '<' + '#'.join(var_declarator_type_arguments) + '>'
        return var_declarator_type

    def _parse_sub_type(self, type_obj):
        type_name = type_obj.name
        if 'sub_type' in type_obj.attrs and type_obj.sub_type:
            type_name = type_name + '.' + self._parse_sub_type(type_obj.sub_type)
        return type_name

    def _deal_arguments_type(self, arguments, section, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id):
        var_declarator_type_arguments_new = []
        if not arguments:
            return var_declarator_type_arguments_new
        var_declarator_type_arguments = []
        for argument in arguments:
            argument_type = type(argument)
            if argument_type == javalang.tree.MethodInvocation:
                var_declarator_type_argument = self._parse_method_body_method_invocation(argument, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
            elif argument_type == javalang.tree.This:
                var_declarator_type_argument = self._parse_node_selectors(argument.selectors, None, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
            else:
                var_declarator_type_argument = self._deal_type(argument)
                var_declarator_type_argument = self._get_var_type(var_declarator_type_argument, parameters_map, variable_map, field_map, import_map, method_invocation, section, package_name, filepath)
            if self._is_valid_prefix(var_declarator_type_argument):
                self._add_entity_used_to_method_invocation(method_invocation, var_declarator_type_argument, section)
            var_declarator_type_arguments.append(var_declarator_type_argument)
        return var_declarator_type_arguments

    def _deal_member_reference(self, member_reference, parameters_map, variable_map, field_map, import_map, method_invocation, section, package_name, filepath):
        member = member_reference.member
        qualifier: str = member_reference.qualifier
        if not qualifier:
            qualifier_type = self._get_var_type(member, parameters_map, variable_map, field_map, import_map, method_invocation, section, package_name, filepath)
        else:
            qualifier_type = self._get_var_type(qualifier, parameters_map, variable_map, field_map, import_map, method_invocation, section, package_name, filepath)
        if self._is_valid_prefix(qualifier_type):
            self._add_field_used_to_method_invocation(method_invocation, qualifier_type, member, [None])
        return qualifier_type

    def _deal_type(self, argument):
        if not argument:
            return None
        argument_type = type(argument)
        if argument_type == javalang.tree.MemberReference:
            var_declarator_type_argument = argument.member
        elif argument_type == javalang.tree.ClassCreator:
            var_declarator_type_argument = argument.type.name
        elif argument_type == javalang.tree.Literal:
            var_declarator_type_argument = self._deal_literal_type(argument.value)
        elif argument_type == javalang.tree.LambdaExpression:
            var_declarator_type_argument = PARAMETER_TYPE_METHOD_INVOCATION_UNKNOWN
        elif argument_type == javalang.tree.BinaryOperation:
            # todo BinaryOperation temp set string
            var_declarator_type_argument = 'String'
        elif argument_type == javalang.tree.MethodReference or argument_type == javalang.tree.TernaryExpression:
            # todo MethodReference temp set unknown
            var_declarator_type_argument = PARAMETER_TYPE_METHOD_INVOCATION_UNKNOWN
        elif argument_type == javalang.tree.SuperMethodInvocation:
            logging.info(argument_type)
            var_declarator_type_argument = PARAMETER_TYPE_METHOD_INVOCATION_UNKNOWN
        elif argument_type == javalang.tree.Assignment:
            var_declarator_type_argument = self._deal_type(argument.value)
        elif argument_type == javalang.tree.Cast:
            var_declarator_type_argument = argument.type.name
        # todo
        elif argument_type == javalang.tree.SuperMemberReference:
            var_declarator_type_argument = 'String'
        elif 'type' in argument.attrs and argument.type is not None:
            var_declarator_type_argument = argument.type.name
        else:
            logging.info(f'argument type is None：{argument}')
            var_declarator_type_argument = PARAMETER_TYPE_METHOD_INVOCATION_UNKNOWN
        return var_declarator_type_argument

    def _deal_literal_type(self, text):
        if 'true' == text or 'false' == text:
            return 'Boolean'
        if text.isdigit():
            return 'Int'
        return 'String'

    def _deal_var_type(self, arguments, section, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id):
        var_declarator_type_arguments_new = []
        if not arguments:
            return var_declarator_type_arguments_new
        var_declarator_type_arguments = []
        for argument in arguments:
            argument_type = type(argument)
            if argument_type == javalang.tree.MethodInvocation:
                var_declarator_type_argument = self._parse_method_body_method_invocation(argument, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
            elif argument_type == javalang.tree.MemberReference:
                var_declarator_type_argument = self._deal_member_reference(argument, parameters_map, variable_map, field_map, import_map, method_invocation, section, package_name, filepath)
            elif argument_type == javalang.tree.This:
                var_declarator_type_argument = self._parse_node_selectors(argument.selectors, None, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id)
                if var_declarator_type_argument is None:
                    var_declarator_type_argument = PARAMETER_TYPE_METHOD_INVOCATION_UNKNOWN
            else:
                var_declarator_type_argument = self._deal_type(argument)
                var_declarator_type_argument = self._get_var_type(var_declarator_type_argument, parameters_map, variable_map, field_map, import_map, method_invocation, section, package_name, filepath)
            type_arguments = self._deal_arguments_type(argument.type.arguments, section, parameters_map, variable_map, field_map, import_map, method_invocation, package_name, filepath, methods, method_name_entity_map, class_id) \
                if 'type' in argument.attrs \
                   and not isinstance(argument.type, str) \
                   and 'arguments' in argument.type.attrs \
                   and argument.type.arguments \
                else []
            if type_arguments:
                var_declarator_type_argument = var_declarator_type_argument + '<' + '#'.join(type_arguments) + '>'
            var_declarator_type_arguments.append(var_declarator_type_argument)
        return var_declarator_type_arguments

    def _get_var_type(self, var, parameters_map, variable_map, field_map, import_map, method_invocation, section, package_name, filepath):
        if not var:
            return var
        if var.lower() in JAVA_BASIC_TYPE or var in JAVA_UTIL_TYPE:
            return var
        var_path = "/".join(filepath.split("/")[0: -1]) + "/" + var + ".java"
        if var in parameters_map.keys():
            return parameters_map.get(var)
        elif var in variable_map.keys():
            return variable_map.get(var)
        elif var in field_map.keys():
            field_type = field_map.get(var)['field_type']
            package_class = field_map.get(var)['package_class']
            start_line = field_map.get(var)['start_line']
            self._add_field_used_to_method_invocation(method_invocation, package_class, var, [start_line])
            return field_type
        elif var in import_map.keys():
            if '.' in var:
                return self._parse_layer_call_var_type(var, import_map, method_invocation)
            var_type = import_map.get(var)
            return var_type
        elif os.path.exists(var_path):
            var_type = f'{package_name}.{var}'
            return var_type
        if '.' not in var:
            sql = "select package_name, class_name from class where project_id = {} and class_name=\"{}\" and filepath = \"{}\"".format(self.project_id, var, filepath)
            var_class_db = self.sqlite.select_data(sql)
            if var_class_db:
                return var_class_db[0]['package_name'] + '.' + var_class_db[0]['class_name']
        return self._parse_layer_call_var_type(var, import_map, method_invocation)

    def _parse_layer_call_var_type(self, var, import_map, method_invocation):
        ## 判断是否内部类
        var_split = var.split('.')
        var_class = var_split[-1]
        if var_class.lower() in JAVA_BASIC_TYPE or var_class in JAVA_UTIL_TYPE:
            return var
        elif len(var_split) > 1:
            var_field = var_split[-1]
            var_class = var_split[-2]
            if var_class in import_map.keys():
                var_type = import_map.get(var_class)
                var_type_package = '.'.join(var_type.split('.')[0: -1])
                var_field_db = self.sqlite.select_data(f'select field_type from field where project_id={self.project_id} and field_name="{var_field}" '
                                                       f'and class_id in (select class_id from class where project_id={self.project_id} and class_name="{var_class}" and package_name="{var_type_package}")')
                if var_field_db:
                    self._add_field_used_to_method_invocation(method_invocation, var_type, var_field, [None])
                    field_type = var_field_db[0]['field_type']
                    if field_type == 'ENUM':
                        return var_type
                    return field_type
            var_package_end = '.'.join(var_split[0: -1])
            sql = "select package_name, class_name from class where project_id = {} and class_name=\"{}\" and package_name like \"%{}\"".format(self.project_id, var_field, var_package_end)
            var_class_db = self.sqlite.select_data(sql)
            if var_class_db:
                var_type = var_class_db[0]['package_name'] + '.' + var_class_db[0]['class_name']
                return var_type
        elif var != PARAMETER_TYPE_METHOD_INVOCATION_UNKNOWN:
            return var[0].upper() + var[1:]
        return var

    def _get_extends_class_fields_map(self, class_id: int):
        class_db = self.sqlite.select_data(f'SELECT extends_class FROM class WHERE project_id = {self.project_id} and class_id = {class_id}')[0]
        extend_package_class = class_db['extends_class']
        if not extend_package_class:
            return {}
        extend_package = '.'.join(extend_package_class.split('.')[0: -1])
        extend_class = extend_package_class.split('.')[-1]
        extend_class_db = self.sqlite.select_data(f'SELECT class_id, extends_class FROM class WHERE package_name="{extend_package}" '
                                                  f'AND class_name="{extend_class}" '
                                                  f'AND project_id={self.project_id} limit 1')
        if not extend_class_db:
            return {}
        extend_class_entity = extend_class_db[0]
        extend_class_id = extend_class_entity['class_id']
        extend_class_fields = self.sqlite.select_data(f'SELECT field_name, field_type, start_line  FROM field WHERE project_id = {self.project_id} and class_id = {extend_class_id}')
        extend_class_fields_map = {field_obj['field_name']: {'field_type': field_obj['field_type'], 'package_class': extend_package_class, 'start_line': field_obj['start_line']} for field_obj in extend_class_fields}
        if not extend_class_entity['extends_class']:
            return extend_class_fields_map
        else:
            extend_new_map = self._get_extends_class_fields_map(extend_class_id)
            extend_new_map.update(extend_class_fields_map)
            return extend_new_map

    def _is_valid_prefix(self, import_str):
        for prefix in config.package_prefix:
            if import_str and import_str.startswith(prefix):
                return True
        return False

    def _get_sibling_dirs(self, path):
        parent_dir = os.path.abspath(os.path.join(path, os.pardir))
        dirs = [os.path.join(parent_dir, d).replace('\\', '/') for d in os.listdir(parent_dir) if os.path.isdir(os.path.join(parent_dir, d)) and not d.startswith('.')]
        return dirs

    def _list_files(self, directory):
        # 使用 os.listdir() 获取目录下所有文件和文件夹名
        all_contents = os.listdir(directory)

        # 完整的文件路径列表
        full_paths = [os.path.join(directory, f) for f in all_contents]

        # 筛选出是文件的路径
        only_files = [f.replace('\\', '/') for f in full_paths if os.path.isfile(f)]

        return only_files

    def _parse_import_file(self, imports, commit_or_branch, parse_import_first):
        for import_decl in imports:
            import_path = import_decl.path
            is_static = import_decl.static
            is_wildcard = import_decl.wildcard
            if not self._is_valid_prefix(import_path):
                continue
            if is_static:
                import_path = '.'.join(import_path.split('.')[0:-1])
            java_files = []
            if is_wildcard:
                import_filepaths = [file_path + '/src/main/java/' + import_path.replace('.', '/') for file_path in self.sibling_dirs]
                for import_filepath in import_filepaths:
                    if not os.path.exists(import_filepath):
                        continue
                    java_files += self._list_files(import_filepath)
            else:
                java_files = [file_path + '/src/main/java/' + import_path.replace('.', '/') + '.java' for file_path in self.sibling_dirs]
            for import_filepath in java_files:
                if not os.path.exists(import_filepath):
                    continue
                self.parse_java_file(import_filepath, commit_or_branch, parse_import_first=parse_import_first)

    def _parse_tree_class(self, class_declaration, filepath, tree_imports, package_name, commit_or_branch, lines, parse_import_first,tree):
        class_name = class_declaration.name
        package_class = package_name + '.' + class_name
        import_list = self._parse_imports(tree_imports)
        import_map = {import_obj['import_path'].split('.')[-1]: import_obj['import_path'] for import_obj in import_list}

        # 处理 class 信息
        class_type = type(class_declaration).__name__.replace('Declaration', '')
        class_id, new_add = self._parse_class(class_declaration, filepath, package_name, import_list, commit_or_branch, parse_import_first,lines)
        # 已经处理过了，返回
        if not new_add and not config.reparse_class:
            return
        # 导入import
        imports = [dict(import_obj, class_id=class_id, project_id=self.project_id) for import_obj in import_list]
        self.sqlite.update_data(f'DELETE FROM import WHERE class_id={class_id}')
        self.sqlite.insert_data('import', imports)

        # 处理 inner class
        inner_class_declarations = [inner_class for inner_class in class_declaration.body
                                    if type(inner_class) == javalang.tree.ClassDeclaration
                                    or type(inner_class) == javalang.tree.InterfaceDeclaration]
        for inner_class_obj in inner_class_declarations:
            self._parse_tree_class(inner_class_obj, filepath, tree_imports, package_class, commit_or_branch, lines, parse_import_first,tree)

        # 处理 field 信息
        field_list = self._parse_fields(class_declaration.fields, package_name, class_name, class_id, import_map, filepath)
        field_map = {field_obj['field_name']: {'field_type': field_obj['field_type'], 'package_class': package_class, 'start_line': field_obj['start_line']} for field_obj in field_list}
        import_map = dict((k, v) for k, v in import_map.items() if self._is_valid_prefix(v))

        # 将extend class的field导进来
        extends_class_fields_map = self._get_extends_class_fields_map(class_id)
        extends_class_fields_map.update(field_map)

        if class_type == 'Enum':
            self._parse_enum(class_declaration.body, lines, class_id, import_map, field_map, package_name, filepath)
        methods_end_line = self.get_accurate_method_end_line(tree,lines)
        # 处理 methods 信息
        self._parse_method(class_declaration.methods, lines, class_id, import_map, extends_class_fields_map, package_name, filepath,methods_end_line)

        self._parse_constructors(class_declaration.constructors, lines, class_id, import_map, extends_class_fields_map, package_name, filepath)

    def parse_java_file(self, filepath: str, commit_or_branch: str, parse_import_first=True):
        if filepath + '_' + commit_or_branch in self.parsed_filepath or not filepath.endswith('.java'):
            return
        self.parsed_filepath.append(filepath + '_' + commit_or_branch)
        try:
            with open(filepath, encoding='UTF-8') as fp:
                file_content = fp.read()
        except:
            return
        lines = file_content.splitlines()
        try:
            tree = javalang.parse.parse(file_content)
            if not tree.types:
                return
        except Exception as e:
            logging.error(f"Error parsing {filepath}: {e}")
            return

        # 处理包信息
        package_name = tree.package.name if tree.package else 'unknown'
        class_declaration = tree.types[0]
        class_name = class_declaration.name
        package_class = package_name + '.' + class_name
        if not self.sibling_dirs:
            package_path = package_class.replace('.', '/') + '.java'
            base_filepath = filepath.replace(package_path, '')
            self.sibling_dirs = self._get_sibling_dirs(base_filepath.replace('src/main/java/', ''))
        # 处理 import 信息
        if parse_import_first:
            self._parse_import_file(tree.imports, commit_or_branch, parse_import_first)
        logging.info(f'Parsing java file: {filepath}')
        self._parse_tree_class(class_declaration, filepath, tree.imports, package_name, commit_or_branch, lines, parse_import_first,tree)

    def parse_java_file_list(self, filepath_list: list, commit_or_branch: str):
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(self.parse_java_file, file, commit_or_branch) for file in filepath_list]
            for _ in as_completed(futures):
                continue
    def get_accurate_method_end_line(self,tree,lines):
        methods_end_line = {}
        for path, method in tree.filter(javalang.tree.MethodDeclaration):
            start_line = method.position.line
            end_line = start_line
            for _, node in method:
                if hasattr(node, "position") and node.position:
                    end_line = max(end_line, node.position.line)
            # Find the last statement in the method body to determine the end lineif method.body:
            # last_statement = method.body[-1]
            # end_line = last_statement.position.line

            # javalang给出的行号是从1开始计算的，但是java_code_lines用的是数组下标，是从0开始的，所以要记住这个差异
            end_line_judge = end_line
            while end_line_judge < len(lines) - 1 and lines[end_line_judge].count("}") == 1:
                end_line_judge = end_line_judge + 1
                end_line = end_line_judge
            methods_end_line[method.name] = {'end_line':end_line}
        return methods_end_line


if __name__ == '__main__':
    print('jcci')
