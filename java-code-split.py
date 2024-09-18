import javalang
import os
import re

    # def __init__(self, method_name, method_start_line, method_end_line,method_body,method_comment):
class Java_Method:

    def __init__(self):
        # 定义私有属性（使用双下划线前缀）

        #方法名称
        self.__method_name = None
        #方法起始行号
        self.__method_start_line = None
        #方法起始行号
        self.__method_end_line = None
        self.__method_body = None
        self.__method_comment = None
        self.__class_first_line = None
    # getter 和 setter 方法

    # method_name
    def get_method_name(self):
        return self.__method_name

    def set_method_name(self, method_name):
        self.__method_name = method_name

    # method_start_line
    def get_method_start_line(self):
        return self.__method_start_line

    def set_method_start_line(self, start_line):
        self.__method_start_line = start_line

    # method_end_line
    def get_method_end_line(self):
        return self.__method_end_line

    def set_method_end_line(self, end_line):
        self.__method_end_line = end_line

    # method_body
    def get_method_body(self):
        return self.__method_body

    def set_method_body(self, method_body):
        self.__method_body = method_body

    # method_comment
    def get_method_comment(self):
        return self.__method_comment

    def set_method_comment(self, method_comment):
        self.__method_comment = method_comment


#通过正则表达式，直接把每段注释都提取出来，但是这个方法存在的问题是，不知道如何和方法匹配上
def extract_comments(java_code):
    # 正则表达式匹配单行注释、多行注释、Javadoc注释
    comment_pattern = re.compile(
        r'//.*?$|'          # 匹配单行注释
        r'/\*.*?\*/|'       # 匹配多行注释
        r'/\*\*.*?\*/',     # 匹配Javadoc注释
        re.DOTALL | re.MULTILINE
    )

    # 查找所有匹配的注释
    comments = comment_pattern.findall(java_code)
    return comments
#这个方法是通过方法的前一行，有没有注释，如果有的话，再往前查看，直到找到注释的开头，返回一个数组[注释起始行号，注释结束行号]
def get_comment(start_line,java_code_lines):
    
    comment_start_line = start_line-2
    comment_end_line = start_line - 1
    #忽略空行
    while java_code_lines[comment_start_line].strip() == '':
        comment_start_line = comment_start_line - 1
        comment_end_line = comment_end_line - 1
    # 使用正则表达式来判断是否以“//”开头
    if re.match(r'^\s*//.*',java_code_lines[comment_start_line]) is not None:
        while re.match(r'^\s*//.*',java_code_lines[comment_start_line]) is not None:
            comment_start_line = comment_start_line - 1
        
        return [comment_start_line + 1,comment_end_line]
    # 使用正则表达式来判断是否以 */ 结尾    
    if re.match(r'.*\*/\s*$', java_code_lines[comment_start_line]) is not None:
        # 使用正则表达式来判断是否以 /* 开头，不断往前递归，直到找到为止
        while comment_start_line > 0 and not (re.match(r'\s*/\*+', java_code_lines[comment_start_line]) is not None):
            comment_start_line = comment_start_line - 1
        return [comment_start_line + 1,comment_end_line]       
    return []

def parse_java_code(java_code):

    method_list = []
    
    tree = javalang.parse.parse(java_code)
    java_code_lines = java_code.splitlines()

    # # 遍历语法树，查找变量声明
    # last_file_line = 0
    # for path, node in tree.filter(javalang.tree.FieldDeclaration):
    #     for decl in node.declarators:
    #         var_name = decl.name
    #         line_number = node.position.line

    #         #寻找最后一个变量的位置
    #         last_file_line = max(last_file_line,line_number)
    #         print(f"Variable '{var_name}' is declared at line {line_number}")
    # # 遍历语法树，查找类声明
    # for path, node in tree.filter(javalang.tree.ClassDeclaration):
    #     class_name = node.name
    #     line_number = node.position.line
    #     print(f"Class '{class_name}' is declared at line {line_number}")

    for class_path, clazz in tree.filter(javalang.tree.TypeDeclaration):
        # print("class_path",class_path)
        print("class_name",clazz.name)

    # Iterate over all methods in the code
    for path, method in tree.filter(javalang.tree.MethodDeclaration):

        for path1, node in method.filter(javalang.tree.LocalVariableDeclaration):
            print("FieldDeclaration.node:",node)
        for path1, node in method.filter(javalang.tree.MethodInvocation):
            print("node.member:",node.member,"node.qualifier:",node.qualifier)
        method_info = Java_Method()
        start_line = method.position.line
        
        print(f"Method {method.name} starts at line {start_line}")
        end_line = start_line
        for _, node in method:
            if hasattr(node, "position") and node.position:
                end_line = max(end_line, node.position.line)
        # Find the last statement in the method body to determine the end lineif method.body:
        # last_statement = method.body[-1]
        # end_line = last_statement.position.line

        # javalang给出的行号是从1开始计算的，但是java_code_lines用的是数组下标，是从0开始的，所以要记住这个差异
        end_line_judge = end_line
        while end_line_judge < len(java_code_lines) - 1 and java_code_lines[end_line_judge].count("}") == 1:
            end_line_judge = end_line_judge + 1
            end_line = end_line_judge
        
        print(extract_comments("\n".join(java_code_lines[start_line:end_line_judge])))

        print(f"Method {method.name} ends at line {end_line}")
    else:
        print(" is empty.")


def find_java_files(folder_path):
    # 使用 os.walk 递归遍历文件夹
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".java"):  # 检查文件扩展名是否为 .java
                java_file_path = os.path.join(root, file)
                print(java_file_path)
                with open(java_file_path, 'r', encoding='utf-8') as f:
                     java_code = f.read()
                     parse_java_code(java_code)
                

    

# 示例用法
folder_path = "./Chat2DB/chat2db-server/chat2db-server-web/chat2db-server-web-api/src/main/java/ai/chat2db/server/web/api/controller/sql"
find_java_files(folder_path)
