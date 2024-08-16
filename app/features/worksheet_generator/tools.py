import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
import logging
from typing import List
from app.api.error_utilities import LoaderError
from app.services.tool_registry import ToolFile

logger = logging.getLogger(__name__)

class RAGpipeline:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def compile(self):
        # Compiling the pipeline components
        if self.verbose:
            logger.debug("Pipeline compiled successfully.")

    def __call__(self, files: List[ToolFile]):
        # Process the files and create a database or a structure
        db = self.process_files(files)
        return db

    def process_files(self, files: List[ToolFile]):
        #File processing
        if not files:
            raise LoaderError("No files to process.")
        
        db = {}  # Placeholder for the database creation logic
        if self.verbose:
            logger.debug(f"Processing files: {files}")
        
        # Example processing
        for file in files:
            # process each file and populate the db
            db[file.name] = "Processed content"
        
        return db

class QuizBuilder:
    def __init__(self, db: dict, topic: str, verbose: bool = False):
        self.db = db
        self.topic = topic
        self.verbose = verbose

    def create_questions(self, num_questions: int):
        if self.verbose:
            logger.debug(f"Creating {num_questions} questions for topic: {self.topic}")

        # Placeholder for question generation logic
        questions = []
        for i in range(num_questions):
            question = f"Question {i + 1} on {self.topic}"
            questions.append(question)

        if self.verbose:
            logger.debug(f"Generated questions: {questions}")

        return questions
