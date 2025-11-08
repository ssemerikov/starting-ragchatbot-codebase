"""Tests for FastAPI endpoints

This module tests the API endpoints without importing the main app to avoid
static file mounting issues in the test environment.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from unittest.mock import Mock, patch, MagicMock

from config import config


# ============================================================================
# Pydantic Models (duplicated from app.py to avoid import)
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for course queries"""
    query: str
    session_id: Optional[str] = None


class Source(BaseModel):
    """Model for a source citation with optional link"""
    label: str
    url: Optional[str] = None


class QueryResponse(BaseModel):
    """Response model for course queries"""
    answer: str
    sources: List[Source]
    session_id: str


class CourseStats(BaseModel):
    """Response model for course statistics"""
    total_courses: int
    course_titles: List[str]


class ModelInfo(BaseModel):
    """Information about a model"""
    id: str
    name: str
    context: int
    description: str


class ModelsResponse(BaseModel):
    """Response model for available models"""
    current_model: str
    available_models: List[ModelInfo]


class ModelSelectRequest(BaseModel):
    """Request model for selecting a model"""
    model_id: str


# ============================================================================
# Test App Factory
# ============================================================================

def create_test_app(mock_rag_system):
    """
    Create a test FastAPI app with API endpoints but without static file mounting.

    This avoids the issue of mounting static files that don't exist in test environment.
    """
    app = FastAPI(title="Course Materials RAG System - Test", root_path="")

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # Define API endpoints inline
    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        """Process a query and return response with sources"""
        try:
            # Create session if not provided
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()

            # Process query using RAG system
            answer, sources = mock_rag_system.query(request.query, session_id)

            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        """Get course analytics and statistics"""
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/models", response_model=ModelsResponse)
    async def get_available_models():
        """Get list of available models and current selection"""
        try:
            current_model = mock_rag_system.ai_generator.get_current_model()

            # Build list of model info from config
            models = []
            for model_id, model_data in config.AVAILABLE_MODELS.items():
                models.append(ModelInfo(
                    id=model_id,
                    name=model_data["name"],
                    context=model_data["context"],
                    description=model_data["description"]
                ))

            return ModelsResponse(
                current_model=current_model,
                available_models=models
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/models/select")
    async def select_model(request: ModelSelectRequest):
        """Switch to a different model"""
        try:
            # Validate model exists
            if request.model_id not in config.AVAILABLE_MODELS:
                raise HTTPException(status_code=400, detail=f"Model '{request.model_id}' not found")

            # Update the model
            mock_rag_system.ai_generator.set_model(request.model_id)

            return {
                "success": True,
                "current_model": request.model_id,
                "message": f"Switched to {config.AVAILABLE_MODELS[request.model_id]['name']}"
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app


# ============================================================================
# API Endpoint Tests
# ============================================================================

@pytest.mark.api
class TestQueryEndpoint:
    """Test the /api/query endpoint"""

    @pytest.fixture
    def client(self, mock_rag_system):
        """Create a test client with mock RAG system"""
        app = create_test_app(mock_rag_system)
        return TestClient(app)

    def test_query_without_session(self, client, mock_rag_system):
        """Test query endpoint without providing a session_id"""
        print("\n=== Test Query Without Session ===")

        request_data = {
            "query": "What is MCP?",
        }

        response = client.post("/api/query", json=request_data)

        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        assert data["answer"] == "MCP stands for Model Context Protocol."
        assert len(data["sources"]) > 0
        assert data["session_id"] == "test-session-123"

    def test_query_with_session(self, client, mock_rag_system):
        """Test query endpoint with an existing session_id"""
        print("\n=== Test Query With Session ===")

        request_data = {
            "query": "What is MCP?",
            "session_id": "existing-session-456"
        }

        response = client.post("/api/query", json=request_data)

        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")

        assert response.status_code == 200
        data = response.json()

        assert data["session_id"] == "existing-session-456"
        assert "answer" in data
        assert "sources" in data

    def test_query_missing_query_field(self, client):
        """Test query endpoint with missing query field"""
        print("\n=== Test Query Missing Field ===")

        request_data = {}

        response = client.post("/api/query", json=request_data)

        print(f"Status code: {response.status_code}")

        assert response.status_code == 422  # Validation error

    def test_query_empty_query(self, client, mock_rag_system):
        """Test query endpoint with empty query string"""
        print("\n=== Test Query Empty String ===")

        request_data = {
            "query": "",
        }

        response = client.post("/api/query", json=request_data)

        print(f"Status code: {response.status_code}")

        # Should still process but RAG system handles empty queries
        assert response.status_code == 200

    def test_query_rag_system_error(self, client, mock_rag_system):
        """Test query endpoint when RAG system raises an error"""
        print("\n=== Test Query RAG System Error ===")

        # Make the mock raise an exception
        mock_rag_system.query.side_effect = Exception("Database connection failed")

        request_data = {
            "query": "What is MCP?",
        }

        response = client.post("/api/query", json=request_data)

        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")

        assert response.status_code == 500
        assert "Database connection failed" in response.json()["detail"]


@pytest.mark.api
class TestCoursesEndpoint:
    """Test the /api/courses endpoint"""

    @pytest.fixture
    def client(self, mock_rag_system):
        """Create a test client with mock RAG system"""
        app = create_test_app(mock_rag_system)
        return TestClient(app)

    def test_get_courses(self, client, mock_rag_system):
        """Test getting course statistics"""
        print("\n=== Test Get Courses ===")

        response = client.get("/api/courses")

        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")

        assert response.status_code == 200
        data = response.json()

        assert "total_courses" in data
        assert "course_titles" in data
        assert data["total_courses"] == 2
        assert len(data["course_titles"]) == 2
        assert "Test Course on MCP" in data["course_titles"]

    def test_get_courses_empty(self, client, mock_rag_system):
        """Test getting course statistics when no courses exist"""
        print("\n=== Test Get Courses Empty ===")

        # Modify mock to return empty results
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        response = client.get("/api/courses")

        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")

        assert response.status_code == 200
        data = response.json()

        assert data["total_courses"] == 0
        assert len(data["course_titles"]) == 0

    def test_get_courses_error(self, client, mock_rag_system):
        """Test getting courses when RAG system raises an error"""
        print("\n=== Test Get Courses Error ===")

        mock_rag_system.get_course_analytics.side_effect = Exception("Vector store unavailable")

        response = client.get("/api/courses")

        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")

        assert response.status_code == 500
        assert "Vector store unavailable" in response.json()["detail"]


@pytest.mark.api
class TestModelsEndpoint:
    """Test the /api/models endpoints"""

    @pytest.fixture
    def client(self, mock_rag_system):
        """Create a test client with mock RAG system"""
        app = create_test_app(mock_rag_system)
        return TestClient(app)

    def test_get_models(self, client, mock_rag_system):
        """Test getting available models"""
        print("\n=== Test Get Models ===")

        response = client.get("/api/models")

        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")

        assert response.status_code == 200
        data = response.json()

        assert "current_model" in data
        assert "available_models" in data
        assert data["current_model"] == "claude-sonnet-4-20250514"
        assert len(data["available_models"]) > 0

        # Check first model structure
        first_model = data["available_models"][0]
        assert "id" in first_model
        assert "name" in first_model
        assert "context" in first_model
        assert "description" in first_model

    def test_select_model_valid(self, client, mock_rag_system):
        """Test selecting a valid model"""
        print("\n=== Test Select Valid Model ===")

        # Get first available model ID from config
        model_id = list(config.AVAILABLE_MODELS.keys())[0]

        request_data = {
            "model_id": model_id
        }

        response = client.post("/api/models/select", json=request_data)

        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["current_model"] == model_id
        assert "message" in data

        # Verify set_model was called
        mock_rag_system.ai_generator.set_model.assert_called_once_with(model_id)

    def test_select_model_invalid(self, client, mock_rag_system):
        """Test selecting an invalid model"""
        print("\n=== Test Select Invalid Model ===")

        request_data = {
            "model_id": "nonexistent-model"
        }

        response = client.post("/api/models/select", json=request_data)

        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")

        assert response.status_code == 400
        assert "not found" in response.json()["detail"]

    def test_select_model_missing_field(self, client):
        """Test selecting model with missing model_id field"""
        print("\n=== Test Select Model Missing Field ===")

        request_data = {}

        response = client.post("/api/models/select", json=request_data)

        print(f"Status code: {response.status_code}")

        assert response.status_code == 422  # Validation error

    def test_get_models_error(self, client, mock_rag_system):
        """Test getting models when AI generator raises an error"""
        print("\n=== Test Get Models Error ===")

        mock_rag_system.ai_generator.get_current_model.side_effect = Exception("AI service error")

        response = client.get("/api/models")

        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")

        assert response.status_code == 500
        assert "AI service error" in response.json()["detail"]


@pytest.mark.api
class TestRequestValidation:
    """Test request validation and error handling"""

    @pytest.fixture
    def client(self, mock_rag_system):
        """Create a test client with mock RAG system"""
        app = create_test_app(mock_rag_system)
        return TestClient(app)

    def test_query_with_invalid_json(self, client):
        """Test query endpoint with invalid JSON"""
        print("\n=== Test Invalid JSON ===")

        response = client.post(
            "/api/query",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )

        print(f"Status code: {response.status_code}")

        assert response.status_code == 422

    def test_query_with_wrong_data_types(self, client):
        """Test query endpoint with wrong data types"""
        print("\n=== Test Wrong Data Types ===")

        request_data = {
            "query": 123,  # Should be string
            "session_id": ["not", "a", "string"]  # Should be string or None
        }

        response = client.post("/api/query", json=request_data)

        print(f"Status code: {response.status_code}")

        assert response.status_code == 422

    def test_query_response_structure(self, client, mock_rag_system):
        """Test that query response has correct structure"""
        print("\n=== Test Response Structure ===")

        request_data = {
            "query": "What is MCP?",
        }

        response = client.post("/api/query", json=request_data)

        assert response.status_code == 200
        data = response.json()

        # Validate response structure matches QueryResponse model
        assert isinstance(data["answer"], str)
        assert isinstance(data["sources"], list)
        assert isinstance(data["session_id"], str)

        # Validate source structure
        for source in data["sources"]:
            assert "label" in source
            assert "url" in source or source.get("url") is None


@pytest.mark.api
@pytest.mark.integration
class TestAPIIntegration:
    """Integration tests for API endpoints with real RAG system"""

    @pytest.fixture
    def client_with_real_rag(self):
        """Create a test client with a real RAG system instance"""
        from rag_system import RAGSystem

        real_rag_system = RAGSystem(config)
        app = create_test_app(real_rag_system)
        return TestClient(app)

    def test_full_query_flow_with_real_system(self, client_with_real_rag):
        """Test complete query flow with real RAG system (no mocking)"""
        print("\n=== Test Full Query Flow with Real System ===")

        request_data = {
            "query": "What courses are available?",
        }

        response = client_with_real_rag.post("/api/query", json=request_data)

        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0

    def test_get_real_courses(self, client_with_real_rag):
        """Test getting actual course statistics"""
        print("\n=== Test Get Real Courses ===")

        response = client_with_real_rag.get("/api/courses")

        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")

        assert response.status_code == 200
        data = response.json()

        assert "total_courses" in data
        assert "course_titles" in data
        assert data["total_courses"] >= 0
        assert isinstance(data["course_titles"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "api"])
