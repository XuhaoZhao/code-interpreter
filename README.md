根据操作系统的不同，为neo4j创建数据文件夹

create folder '/data'

chmod +777 ./data

export PWD=$(pwd)



testapi

fastapi
pydantic
uvicorn


from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn


app = FastAPI()

@app.get("/api")
def read_root():
    return {"message": "请帮我查找 天气"}


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8800)



RUN pip install --upgrade -r requirements.txt