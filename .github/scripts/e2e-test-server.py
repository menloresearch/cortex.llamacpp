import requests
import json
import subprocess
import os
import logging
import sys
import random
import platform

n = len(sys.argv)
print("Total arguments passed:", n)
if n < 4:
    print("The number of arguments should >= 4")
    exit(1)

BINARY_PATH = sys.argv[1]
if platform.system == 'Windows':
    BINARY_PATH += '.exe'
DOWNLOAD_LLM_URL = sys.argv[2]
DOWNLOAD_EMBEDDING_URL = sys.argv[3]
LLM_MODEL = 'chat_model'
EMBED_MODEL = 'embedding_model'
LLM_FILE_TO_SAVE = './' + LLM_MODEL + '.gguf'
EMBED_FILE_TO_SAVE = './' + EMBED_MODEL + '.gguf'

if not os.path.isfile(LLM_FILE_TO_SAVE):
    try:
        resp = requests.get(DOWNLOAD_LLM_URL)
        resp.raise_for_status()
        with open(LLM_FILE_TO_SAVE, "wb") as f: # opening a file handler to create new file 
            f.write(resp.content)
    except requests.exceptions.HTTPError as error:
        print(error)        

if not os.path.isfile(EMBED_FILE_TO_SAVE):
    try:    
        resp = requests.get(DOWNLOAD_EMBEDDING_URL)
        resp.raise_for_status()
        with open(EMBED_FILE_TO_SAVE, "wb") as f: # opening a file handler to create new file 
            f.write(resp.content)
    except requests.exceptions.HTTPError as error:
        print(error)

CONST_CTX_SIZE = 2048
CONST_USER_ROLE = "user"
CONST_ASSISTANT_ROLE = "assistant"

port = random.randint(10000, 11000)

cwd = os.getcwd()
upload_folder = cwd + '/uploads'
server_log = cwd + '/' + "server.log"
subprocess.Popen(BINARY_PATH + ' 1 127.0.0.1 ' + str(port))
#'C:\\Users\\vansa\\jan\\extensions\\@janhq\\inference-cortex-extension\\dist\\bin\\win-cpu\\cortex-cpp
logging.basicConfig(filename='./test.log',
                    filemode='w',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.INFO)

chat_data = []

def RequestPost(req_data, url, is_stream = False):
    try:
        r = requests.post(url, json=req_data, stream=is_stream)
        r.raise_for_status()
        if is_stream: 
            if r.encoding is None:
                r.encoding = 'utf-8'

            res = ""
            for line in r.iter_lines(decode_unicode=True):
                if line and "[DONE]" not in line:
                    data = json.loads(line[5:])
                    content = data['choices'][0]['delta']['content']
                    res += content
            logging.info(len(res))
            logging.info('{\'assistant\': \''  + res + '\'}')
            chat_data.append({
                "role": CONST_ASSISTANT_ROLE,
                "content": res
            })
            # Can be an error when model generates gabarge data            
            if len(data) >= CONST_CTX_SIZE - 100:
                logging.warn("Maybe generated gabarge data")
                return False
        else:
            res_json = r.json()
            logging.info(res_json)
        
        if r.status_code == 200:
            return True
        else:
            logging.warn('{\'status_code\': '  + str(r.status_code) + '}') 
            return False
    except requests.exceptions.HTTPError as error:
        logging.error(error)
        return False

def RequestGet(url):
    try:
        r = requests.get(url)
        r.raise_for_status()       
        res_json = r.json()
        logging.info('{\'status_code\': '  + str(r.status_code) + '}') 
        logging.info(res_json)        
        if r.status_code == 200:
            return True
        else:
            return False
    except requests.exceptions.HTTPError as error:
        logging.error(error)
        return False

def StopServer():
    url = "http://127.0.0.1:"+ str(port) + "/processManager/destroy"
    try:
        r = requests.delete(url)
        logging.info(r.status_code)
    except requests.ConnectionError as error:
        logging.error(error)

def TestLoadChatModel():
    new_data = {
        "ctx_len": CONST_CTX_SIZE,
        "prompt_template": "<|system|>\n{system_message}<|user|>\n{prompt}<|assistant|>",
        "llama_model_path": cwd + "/" + LLM_MODEL + '.gguf',
        "model_alias": LLM_MODEL,
        "ngl": 32,
        # "caching_enabled": True
    }

    url_post = "http://127.0.0.1:"+ str(port) + "/inferences/server/loadmodel"

    res = RequestPost(new_data, url_post)
    if not res:
        StopServer()
        exit(1)

def TestChatCompletion():
    content = "How are you today?"
    user_msg = {
        "role": CONST_USER_ROLE,
        "content": content
    }
    logging.info('{\'user\': \''  + content + '\'}')
    
    chat_data.append(user_msg)
    new_data = {
        "frequency_penalty": 0,
        "max_tokens": CONST_CTX_SIZE,
        "messages": chat_data,
        "model": LLM_MODEL,
        "presence_penalty": 0,
        "stop": [],
        "stream": True,
        "temperature": 0.7,
        "top_p": 0.95
    }

    url_post = "http://127.0.0.1:"+ str(port) + "/v1/chat/completions"

    res = RequestPost(new_data, url_post, True)
    if not res:
        StopServer()
        exit(1)
    
    content = "Tell me a short story"
    user_msg = {
        "role": CONST_USER_ROLE,
        "content": content
    }
    logging.info('{\'user\': \''  + content + '\'}')
    
    chat_data.append({
        "role": CONST_USER_ROLE,
        "content": content
    })

    new_data = {
        "frequency_penalty": 0,
        "max_tokens": CONST_CTX_SIZE,
        "messages": chat_data,
        "model": LLM_MODEL,
        "presence_penalty": 0,
        "stop": [],
        "stream": True,
        "temperature": 0.7,
        "top_p": 0.95
    }

    res = RequestPost(new_data, url_post, True)
    if not res:
        StopServer()
        exit(1)

def TestUnloadModel(model):
    new_data = {
        "model": model,
    }

    url_post = "http://127.0.0.1:"+ str(port) + "/inferences/server/unloadmodel"

    res = RequestPost(new_data, url_post)
    if not res:
        StopServer()
        exit(1)

def TestLoadEmbeddingModel():
    new_data = {
        "llama_model_path": cwd + "/" + EMBED_MODEL + '.gguf',
        "model_alias": EMBED_MODEL,
        "ctx_len": 512,
        "ngl": 99,
        "n_parallel": 1,
        "embedding": True,
        "model_type": "embedding",
        "caching_enabled": False
    } 

    url_post = "http://127.0.0.1:"+ str(port) + "/inferences/server/loadmodel"

    res = RequestPost(new_data, url_post)
    if not res:
        StopServer()
        exit(1)

def TestEmbeddings():
    new_data = {
        "input": "This PDFs was created using Microsoft Word using the print to PDF function. True PDFs consist of both text and images. We should think about these PDFs having two layers – one layer  is the image and a second layer is the text. The image layer shows what the document will look  like if it is printed to paper. The text layer is searchable text that is carried over from the original Word file into the new PDF file (the technical term for this layer is “extracted text”). There is no need to make it searchable and the new PDF will have the same text as the original Word file. An example of True PDFs that federal defenders and CJA panel attorneys will be familiar with are the pleadings filed in CM/ECF. The pleading is originally created in Word, but then the attorney either saves it as PDF or prints to PDF and they file that PDF document with the court. Using either process, there is now a PDF file created with an image layer plus text layer. In terms of usability, this is the best type of PDF to receive in discovery as it will have the closest to text searchability of the original file",
        "model": EMBED_MODEL,
        "encoding_format": "float"
    }
    url_post = "http://127.0.0.1:"+ str(port) + "/v1/embeddings"
    res = RequestPost(new_data, url_post)
    if not res:
        StopServer()
        exit(1)

TestLoadChatModel()
TestChatCompletion()
TestUnloadModel(LLM_MODEL)
TestLoadEmbeddingModel()
TestEmbeddings()
TestUnloadModel(EMBED_MODEL)
StopServer()

with open('./test.log', 'r') as f:
    print(f.read())
    