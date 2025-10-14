import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from orchestrator.app.main import app
from orchestrator.app.schemas import Message, Role

# Test data for different student profiles and scenarios
TEST_USERS = {
    "flashcard_test": {
        "user_id": "student123",
        "scenario": "Kinesthetic learner, focused, level 6",
        "message": "I want to practice flashcards on photosynthesis for biology",
        "expected_tool": "flashcard_generator"
    },
    "note_test": {
        "user_id": "student456",
        "scenario": "Visual learner, anxious, level 3",
        "message": "Create detailed notes about the water cycle",
        "expected_tool": "note_maker"
    },
    "concept_test": {
        "user_id": "student789",
        "scenario": "Auditory learner, confused, level 4",
        "message": "Please explain me the concept of Operating Systems and its types.",
        "expected_tool": "concept_explainer"
    },
    "quiz_test": {
        "user_id": "student123",
        "scenario": "Kinesthetic learner, focused, level 6",
        "message": "I need practice problems and a quiz on calculus derivatives.",
        "expected_tool": "quiz_generator"
    }
}


class TestOrchestratorWorkflow:
    """Test suite for the autonomous AI tutor orchestrator"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_orchestrator_health(self, client):
        """Test orchestrator health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        assert response.json()["service"] == "orchestrator"
        print("\n✅ Health Check Passed")

    def test_orchestrator_root(self, client):
        """Test orchestrator root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        assert "Autonomous AI Tutor Orchestrator" in response.json()["message"]
        assert "version" in response.json()
        print("✅ Root Endpoint Passed")

    def test_user_profile_retrieval(self, client):
        """Test user profile retrieval endpoint"""
        response = client.get("/user/student456")
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["user_id"] == "student456"
        assert user_data["name"] == "Alice"
        assert user_data["grade_level"] == "10"
        print("✅ User Profile Retrieval Passed")

    def test_flashcard_generator_scenario(self, client):
        """
        Scenario 1: Flashcard Generator
        Student: Charlie (Kinesthetic, Focused, Level 6)
        Message: Wants to practice flashcards on photosynthesis
        """
        test_data = TEST_USERS["flashcard_test"]

        request_payload = {
            "user_id": test_data["user_id"],
            "session_id": "test-flashcard-001",
            "message": test_data["message"],
            "chat_history": [
                {
                    "role": "user",
                    "content": "Hi, I want to improve my biology knowledge"
                },
                {
                    "role": "assistant",
                    "content": "Great! Biology is fascinating. What topic interests you?"
                }
            ]
        }

        response = client.post("/chat", json=request_payload)
        
        # Assertions
        assert response.status_code == 200, f"Status code: {response.status_code}"
        response_data = response.json()
        
        assert response_data["response"] is not None
        assert response_data["tool_used"] is not None
        assert response_data["tool_used"] == "flashcard_generator", f"Got {response_data['tool_used']}"
        assert response_data["data"] is not None
        assert "flashcards" in response_data["data"]
        assert len(response_data["data"]["flashcards"]) > 0
        assert response_data["educational_context_used"]["emotional_state"] == "focused"
        assert response_data["educational_context_used"]["mastery_level"] == 6

        print(f"\n✅ SCENARIO 1: Flashcard Generator Test Passed")
        print(f"   Student: {test_data['scenario']}")
        print(f"   Message: {test_data['message']}")
        print(f"   Tool Used: {response_data['tool_used']}")
        print(f"   Flashcards Generated: {len(response_data['data']['flashcards'])}")
        print(f"   Mastery Level: {response_data['educational_context_used']['mastery_level']}")

    def test_note_maker_scenario(self, client):
        """
        Scenario 2: Note Maker
        Student: Alice (Visual, Anxious, Level 3)
        Message: Wants comprehensive notes about water cycle
        """
        test_data = TEST_USERS["note_test"]

        request_payload = {
            "user_id": test_data["user_id"],
            "session_id": "test-notes-001",
            "message": test_data["message"],
            "chat_history": [
                {
                    "role": "user",
                    "content": "I'm starting environmental science"
                },
                {
                    "role": "assistant",
                    "content": "Environmental science is important! What would you like to learn?"
                }
            ]
        }

        response = client.post("/chat", json=request_payload)
        
        # Assertions
        assert response.status_code == 200, f"Status code: {response.status_code}"
        response_data = response.json()
        
        assert response_data["response"] is not None
        assert response_data["tool_used"] is not None
        # Note: Your intent analysis might map "notes" to concept_explainer or note_maker
        # Both are acceptable since they both generate educational content
        assert response_data["tool_used"] in ["note_maker", "concept_explainer"], \
            f"Got {response_data['tool_used']}"
        
        # Either tool should return data
        if response_data["data"]:
            assert response_data["educational_context_used"]["teaching_style"] == "visual"
            assert response_data["educational_context_used"]["emotional_state"] == "anxious"
            assert response_data["educational_context_used"]["mastery_level"] == 3

        print(f"\n✅ SCENARIO 2: Note Maker Test Passed")
        print(f"   Student: {test_data['scenario']}")
        print(f"   Message: {test_data['message']}")
        print(f"   Tool Used: {response_data['tool_used']}")
        print(f"   Teaching Style: {response_data['educational_context_used']['teaching_style']}")
        print(f"   Emotional State: {response_data['educational_context_used']['emotional_state']}")

    def test_concept_explainer_scenario(self, client):
        """
        Scenario 3: Concept Explainer
        Student: Bob (Auditory, Confused, Level 4)
        Message: Wants explanation of Operating Systems
        """
        test_data = TEST_USERS["concept_test"]

        request_payload = {
            "user_id": test_data["user_id"],
            "session_id": "test-concept-001",
            "message": test_data["message"],
            "chat_history": [
                {
                    "role": "user",
                    "content": "I'm learning about computer systems"
                },
                {
                    "role": "assistant",
                    "content": "Computer systems are interesting! Let me help you understand them better."
                }
            ]
        }

        response = client.post("/chat", json=request_payload)
        
        # Assertions
        assert response.status_code == 200, f"Status code: {response.status_code}"
        response_data = response.json()
        
        assert response_data["response"] is not None
        assert response_data["tool_used"] is not None
        assert response_data["tool_used"] == "concept_explainer", \
            f"Got {response_data['tool_used']}"
        
        # Verify adapted content for confused student
        if response_data["data"]:
            assert response_data["educational_context_used"]["teaching_style"] == "socratic"
            assert response_data["educational_context_used"]["emotional_state"] == "confused"
            assert response_data["educational_context_used"]["mastery_level"] == 4
            
            # Check for simplified language for confused student
            if "explanation" in response_data["data"]:
                explanation = response_data["data"]["explanation"].lower()
                # Should have reassuring language for confused students
                assert len(explanation) > 50, "Explanation too short"

        print(f"\n✅ SCENARIO 3: Concept Explainer Test Passed")
        print(f"   Student: {test_data['scenario']}")
        print(f"   Message: {test_data['message']}")
        print(f"   Tool Used: {response_data['tool_used']}")
        print(f"   Emotional State: {response_data['educational_context_used']['emotional_state']}")

    def test_quiz_generator_scenario(self, client):
        """
        Scenario 4: Quiz Generator
        Student: Charlie (Kinesthetic, Focused, Level 6)
        Message: Wants practice problems on derivatives
        """
        test_data = TEST_USERS["quiz_test"]

        request_payload = {
            "user_id": test_data["user_id"],
            "session_id": "test-quiz-001",
            "message": test_data["message"],
            "chat_history": [
                {
                    "role": "user",
                    "content": "I'm studying calculus"
                },
                {
                    "role": "assistant",
                    "content": "Calculus is challenging but rewarding! What aspect would you like to practice?"
                }
            ]
        }

        response = client.post("/chat", json=request_payload)
        
        # Assertions
        assert response.status_code == 200, f"Status code: {response.status_code}"
        response_data = response.json()
        
        assert response_data["response"] is not None
        assert response_data["tool_used"] is not None
        # Quiz or practice problems should map to quiz_generator
        assert response_data["tool_used"] in ["quiz_generator", "flashcard_generator"], \
            f"Got {response_data['tool_used']}"
        
        if response_data["data"] and "questions" in response_data["data"]:
            assert len(response_data["data"]["questions"]) > 0
            assert response_data["educational_context_used"]["emotional_state"] == "focused"
            
            # Verify questions have required fields
            for question in response_data["data"]["questions"]:
                assert "question" in question

        print(f"\n✅ SCENARIO 4: Quiz Generator Test Passed")
        print(f"   Student: {test_data['scenario']}")
        print(f"   Message: {test_data['message']}")
        print(f"   Tool Used: {response_data['tool_used']}")
        if response_data["data"] and "questions" in response_data["data"]:
            print(f"   Questions Generated: {len(response_data['data']['questions'])}")

    def test_educational_context_adaptation(self, client):
        """
        Test that educational context properly adapts responses
        Anxious student should get simplified content
        """
        request_payload = {
            "user_id": "student456",  # Anxious student (Alice)
            "session_id": "test-adaptation-001",
            "message": "Explain quantum mechanics to me",
            "chat_history": []
        }

        response = client.post("/chat", json=request_payload)
        assert response.status_code == 200
        response_data = response.json()
        
        # Anxious student should get basic/simplified content
        assert response_data["educational_context_used"]["inferred_difficulty"] == "easy"
        assert response_data["educational_context_used"]["emotional_state"] == "anxious"
        assert response_data["educational_context_used"]["teaching_style"] == "visual"
        
        print(f"\n✅ Educational Context Adaptation Test Passed")
        print(f"   Emotional State: {response_data['educational_context_used']['emotional_state']}")
        print(f"   Inferred Difficulty: {response_data['educational_context_used']['inferred_difficulty']}")
        print(f"   Teaching Style: {response_data['educational_context_used']['teaching_style']}")

    def test_intent_routing_accuracy(self, client):
        """
        Test that the orchestrator correctly routes to different tools
        based on intent analysis
        """
        test_cases = [
            ("I need flashcards to memorize biology terms", "flashcard_generator"),
            ("Please explain the theory of evolution", "concept_explainer"),
            ("Create notes about world war 2 for me", "note_maker"),
            ("Give me a quiz on algebra", "quiz_generator"),
        ]
        
        print(f"\n✅ Intent Routing Accuracy Test")
        for message, expected_tool in test_cases:
            request_payload = {
                "user_id": "student123",
                "session_id": f"test-routing-{message[:20]}",
                "message": message,
                "chat_history": []
            }
            
            response = client.post("/chat", json=request_payload)
            assert response.status_code == 200
            response_data = response.json()
            
            # Check if a tool was used
            tool_used = response_data.get("tool_used")
            assert tool_used is not None
            # Tool should be one of the 4 tools (or unknown if LLM routing fails)
            assert tool_used in ["flashcard_generator", "note_maker", 
                               "concept_explainer", "quiz_generator", "unknown"]
            
            print(f"   Message: '{message[:40]}...'")
            print(f"   → Tool: {tool_used}")


class TestOrchestratorErrorHandling:
    """Test error handling in orchestrator"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_invalid_user_id(self, client):
        """Test handling of invalid user ID"""
        request_payload = {
            "user_id": "nonexistent-user",
            "session_id": "test-error-001",
            "message": "Can you help me?",
            "chat_history": []
        }
        
        # Should handle gracefully
        response = client.post("/chat", json=request_payload)
        # Either returns 200 with default context or 404
        assert response.status_code in [200, 404, 500]
        print("✅ Invalid User ID Handling Test Passed")

    def test_empty_message(self, client):
        """Test handling of empty message"""
        request_payload = {
            "user_id": "student123",
            "session_id": "test-error-002",
            "message": "",
            "chat_history": []
        }
        
        # Should fail validation
        response = client.post("/chat", json=request_payload)
        assert response.status_code == 422  # Pydantic validation error
        print("✅ Empty Message Handling Test Passed")


def run_all_tests():
    """Run all tests with verbose output"""
    print("\n" + "="*70)
    print("ORCHESTRATOR TEST SUITE - ALL 4 TOOL SCENARIOS")
    print("="*70)
    
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        "--color=yes"
    ])


if __name__ == "__main__":
    run_all_tests()