import pytest
from unittest.mock import MagicMock
from app.api.error_utilities import LoaderError
from app.services.tool_registry import ToolFile
from app.features.worksheet_generator.tools import RAGpipeline, QuizBuilder

# 1st Test Case: Test the initialization of RAGpipeline
def test_rag_pipeline_initialization():
    pipeline = RAGpipeline(verbose=True)
    assert pipeline.verbose == True

# 2nd Test Case: Test the compile method in RAGpipeline
def test_rag_pipeline_compile(caplog):
    pipeline = RAGpipeline(verbose=True)
    with caplog.at_level("DEBUG"):
        pipeline.compile()
    assert "Pipeline compiled successfully." in caplog.text

# 3rd Test Case: Test the RAGpipeline call method with empty files (should raise LoaderError)
def test_rag_pipeline_call_empty_files():
    pipeline = RAGpipeline(verbose=False)
    with pytest.raises(LoaderError, match="No files to process."):
        pipeline([])

# 4th Test Case: Test the RAGpipeline call method with files
def test_rag_pipeline_call_with_files():
    pipeline = RAGpipeline(verbose=True)
    mock_file = MagicMock(spec=ToolFile)
    mock_file.name = "test_file.txt"
    
    db = pipeline([mock_file])
    assert "test_file.txt" in db
    assert db["test_file.txt"] == "Processed content"

# 5th Test Case: Test the initialization of QuizBuilder
def test_quiz_builder_initialization():
    db = {"topic1": "content"}
    builder = QuizBuilder(db=db, topic="topic1", verbose=True)
    assert builder.db == db
    assert builder.topic == "topic1"
    assert builder.verbose == True

# 6th Test Case: Test the create_questions method in QuizBuilder
def test_quiz_builder_create_questions(caplog):
    db = {"topic1": "content"}
    builder = QuizBuilder(db=db, topic="topic1", verbose=True)
    
    with caplog.at_level("DEBUG"):
        questions = builder.create_questions(num_questions=3)
    
    assert len(questions) == 3
    assert questions == [
        "Question 1 on topic1",
        "Question 2 on topic1",
        "Question 3 on topic1"
    ]
    assert "Generated questions: ['Question 1 on topic1', 'Question 2 on topic1', 'Question 3 on topic1']" in caplog.text
