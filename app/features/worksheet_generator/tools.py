from typing import List, Tuple, Dict, Any
from io import BytesIO
from fastapi import UploadFile, FastAPI, HTTPException
from pypdf import PdfReader
from urllib.parse import urlparse
import requests
import os
import json
import time

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field

from app.services.logger import setup_logger
from app.services.tool_registry import ToolFile
from app.api.error_utilities import LoaderError

relative_path = "features/worksheet_generator"

logger = setup_logger(__name__)

def read_text_file(file_path):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    absolute_file_path = os.path.join(script_dir, file_path)
    with open(absolute_file_path, 'r') as file:
        return file.read()

class RAGRunnable:
    def __init__(self, func):
        self.func = func

    def __or__(self, other):
        def chained_func(*args, **kwargs):
            return other(self.func(*args, **kwargs))
        return RAGRunnable(chained_func)

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

class UploadPDFLoader:
    def __init__(self, files: List[UploadFile]):
        self.files = files

    def load(self) -> List[Document]:
        documents = []
        for upload_file in self.files:
            with upload_file.file as pdf_file:
                pdf_reader = PdfReader(pdf_file)
                for i, page in enumerate(pdf_reader.pages):
                    page_content = page.extract_text()
                    metadata = {"source": upload_file.filename, "page_number": i + 1}
                    doc = Document(page_content=page_content, metadata=metadata)
                    documents.append(doc)
        return documents

class BytesFilePDFLoader:
    def __init__(self, files: List[Tuple[BytesIO, str]]):
        self.files = files

    def load(self) -> List[Document]:
        documents = []
        for file, file_type in self.files:
            logger.debug(file_type)
            if file_type.lower() == "pdf":
                pdf_reader = PdfReader(file)
                for i, page in enumerate(pdf_reader.pages):
                    page_content = page.extract_text()
                    metadata = {"source": file_type, "page_number": i + 1}
                    doc = Document(page_content=page_content, metadata=metadata)
                    documents.append(doc)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
        return documents

class LocalFileLoader:
    def __init__(self, file_paths: list[str], expected_file_type="pdf"):
        self.file_paths = file_paths
        self.expected_file_type = expected_file_type

    def load(self) -> List[Document]:
        documents = []
        self.file_paths = [self.file_paths] if isinstance(self.file_paths, str) else self.file_paths
        for file_path in self.file_paths:
            file_type = file_path.split(".")[-1]
            if file_type != self.expected_file_type:
                raise ValueError(f"Expected file type: {self.expected_file_type}, but got: {file_type}")
            with open(file_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                for i, page in enumerate(pdf_reader.pages):
                    page_content = page.extract_text()
                    metadata = {"source": file_path, "page_number": i + 1}
                    doc = Document(page_content=page_content, metadata=metadata)
                    documents.append(doc)
        return documents

class URLLoader:
    def __init__(self, file_loader=None, expected_file_type="pdf", verbose=False):
        self.loader = file_loader or BytesFilePDFLoader
        self.expected_file_type = expected_file_type
        self.verbose = verbose

    def load(self, tool_files: List[ToolFile]) -> List[Document]:
        queued_files = []
        documents = []
        any_success = False
        for tool_file in tool_files:
            try:
                url = tool_file.url
                response = requests.get(url)
                parsed_url = urlparse(url)
                path = parsed_url.path
                if response.status_code == 200:
                    file_content = BytesIO(response.content)
                    file_type = path.split(".")[-1]
                    if file_type != self.expected_file_type:
                        raise LoaderError(f"Expected file type: {self.expected_file_type}, but got: {file_type}")
                    queued_files.append((file_content, file_type))
                    if self.verbose:
                        logger.info(f"Successfully loaded file from {url}")
                    any_success = True
                else:
                    logger.error(f"Request failed to load file from {url} and got status code {response.status_code}")
            except Exception as e:
                logger.error(f"Failed to load file from {url}")
                logger.error(e)
                continue
        if any_success:
            file_loader = self.loader(queued_files)
            documents = file_loader.load()
            if self.verbose:
                logger.info(f"Loaded {len(documents)} documents")
        if not any_success:
            raise LoaderError("Unable to load any files from URLs")
        return documents

class RAGpipeline:
    def __init__(self, loader=None, splitter=None, vectorstore_class=None, embedding_model=None, verbose=False):
        default_config = {
            "loader": URLLoader(verbose=verbose),
            "splitter": RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100),
            "vectorstore_class": Chroma,
            "embedding_model": GoogleGenerativeAIEmbeddings(model='models/embedding-001')
        }
        self.loader = loader or default_config["loader"]
        self.splitter = splitter or default_config["splitter"]
        self.vectorstore_class = vectorstore_class or default_config["vectorstore_class"]
        self.embedding_model = embedding_model or default_config["embedding_model"]
        self.verbose = verbose

    def load_PDFs(self, files) -> List[Document]:
        if self.verbose:
            logger.info(f"Loading {len(files)} files")
            logger.info(f"Loader type used: {type(self.loader)}")
        logger.debug(f"Loader is a: {type(self.loader)}")
        try:
            total_loaded_files = self.loader.load(files)
        except LoaderError as e:
            logger.error(f"Loader experienced error: {e}")
            raise LoaderError(e)
        return total_loaded_files

    def split_loaded_documents(self, loaded_documents: List[Document]) -> List[Document]:
        if self.verbose:
            logger.info(f"Splitting {len(loaded_documents)} documents")
            logger.info(f"Splitter type used: {type(self.splitter)}")
        total_chunks = []
        chunks = self.splitter.split_documents(loaded_documents)
        total_chunks.extend(chunks)
        if self.verbose:
            logger.info(f"Split {len(loaded_documents)} documents into {len(total_chunks)} chunks")
        return total_chunks

    def create_vectorstore(self, documents: List[Document]):
        if self.verbose:
            logger.info(f"Creating vectorstore from {len(documents)} documents")
        self.vectorstore = self.vectorstore_class.from_documents(documents, self.embedding_model)
        if self.verbose:
            logger.info(f"Vectorstore created")
        return self.vectorstore

    def compile(self):
        self.load_PDFs = RAGRunnable(self.load_PDFs)
        self.split_loaded_documents = RAGRunnable(self.split_loaded_documents)
        self.create_vectorstore = RAGRunnable(self.create_vectorstore)
        if self.verbose:
            logger.info(f"Completed pipeline compilation")

    def __call__(self, documents):
        if self.verbose:
            logger.info(f"Executing pipeline")
            logger.info(f"Start of Pipeline received: {len(documents)} documents of type {type(documents[0])}")
        pipeline = self.load_PDFs | self.split_loaded_documents | self.create_vectorstore
        return pipeline(documents)

class QuizBuilder:
    def __init__(self, vectorstore, topic, prompt=None, model=None, parser=None, verbose=False):
        default_config = {
            "model": GoogleGenerativeAI(model="gemini-1.0-pro"),
            "parser": JsonOutputParser(pydantic_object=QuizQuestion),
            "prompt": read_text_file("prompt/quizzify-prompt.txt")
        }
        self.prompt = prompt or default_config["prompt"]
        self.model = model or default_config["model"]
        self.parser = parser or default_config["parser"]
        self.vectorstore = vectorstore
        self.topic = topic
        self.verbose = verbose
        if vectorstore is None:
            raise ValueError("Vectorstore must be provided")
        if topic is None:
            raise ValueError("Topic must be provided")

    def compile(self):
        prompt = PromptTemplate(
            template=self.prompt,
            input_variables=["topic"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        retriever = self.vectorstore.as_retriever()
        runner = RunnableParallel(
            {"context": retriever, "topic": RunnablePassthrough()}
        )
        chain = runner | prompt | self.model | self.parser
        if self.verbose:
            logger.info(f"Chain compilation complete")
        return chain

    def validate_response(self, response: Dict)
