class BaseLogger:
    def __init__(self) -> None:
        self.info = print


def extract_title_and_question(input_string):
    lines = input_string.strip().split("\n")

    title = ""
    question = ""
    is_question = False  # flag to know if we are inside a "Question" block

    for line in lines:
        if line.startswith("Title:"):
            title = line.split("Title: ", 1)[1].strip()
        elif line.startswith("Question:"):
            question = line.split("Question: ", 1)[1].strip()
            is_question = (
                True  # set the flag to True once we encounter a "Question:" line
            )
        elif is_question:
            # if the line does not start with "Question:" but we are inside a "Question" block,
            # then it is a continuation of the question
            question += "\n" + line.strip()

    return title, question


def create_vector_index(driver, dimension: int) -> None:
    index_query = "CALL db.index.vector.createNodeIndex('stackoverflow', 'Question', 'embedding', $dimension, 'cosine')"
    try:
        driver.query(index_query, {"dimension": dimension})
    except:  # Already exists
        pass
    index_query = "CALL db.index.vector.createNodeIndex('top_answers', 'Answer', 'embedding', $dimension, 'cosine')"
    try:
        driver.query(index_query, {"dimension": dimension})
    except:  # Already exists
        pass
def create_method_vector_index(driver, dimension: int) -> None:
    index_query1 = "CALL db.index.vector.createNodeIndex('method_index', 'Method', 'method_name_embedding', $dimension, 'cosine')"
    index_query2 = "CALL db.index.vector.createNodeIndex('body_index', 'Method', 'body_embedding', $dimension, 'cosine')"
    index_query3 = "CALL db.index.vector.createNodeIndex('documentation_index', 'Method', 'documentation_embedding', $dimension, 'cosine')"
    index_query4 = "CALL db.index.vector.createNodeIndex('class_name_index', 'Method', 'class_name_embedding', $dimension, 'cosine')"
    index_querynn = """
BEGIN;
CALL db.index.vector.createNodeIndex('method_name_index', 'Method', 'method_name_embedding', $dimension, 'cosine');
CALL db.index.vector.createNodeIndex('body_index', 'Method', 'body_embedding', $dimension, 'cosine');
CALL db.index.vector.createNodeIndex('documentation_index', 'Method', 'documentation_embedding', $dimension, 'cosine');
CALL db.index.vector.createNodeIndex('class_name_index', 'Method', 'class_name_embedding', $dimension, 'cosine');
COMMIT;
"""
    try:
        driver.query(index_query1, {"dimension": dimension})
        driver.query(index_query2, {"dimension": dimension})
        driver.query(index_query3, {"dimension": dimension})
        driver.query(index_query4, {"dimension": dimension})
    except:  # Already exists
        pass

def create_constraints(driver):
    driver.query(
        "CREATE CONSTRAINT question_id IF NOT EXISTS FOR (q:Question) REQUIRE (q.id) IS UNIQUE"
    )
    driver.query(
        "CREATE CONSTRAINT answer_id IF NOT EXISTS FOR (a:Answer) REQUIRE (a.id) IS UNIQUE"
    )
    driver.query(
        "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE (u.id) IS UNIQUE"
    )
    driver.query(
        "CREATE CONSTRAINT tag_name IF NOT EXISTS FOR (t:Tag) REQUIRE (t.name) IS UNIQUE"
    )
def create_constraint_for_method_node(driver):
    driver.query(
    "CREATE CONSTRAINT method_id_unique IF NOT EXISTS FOR (m:Method) REQUIRE (m.method_id) IS UNIQUE")

def create_constraint_for_class_request_node(driver):
    driver.query(
    "CREATE CONSTRAINT class_request_id_unique IF NOT EXISTS FOR (rc:RequestClass) REQUIRE (rc.class_request_id) IS UNIQUE")