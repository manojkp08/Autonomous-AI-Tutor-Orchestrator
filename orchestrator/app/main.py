from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .schemas import ChatRequest, ChatResponse
from .workflow import TutorWorkflow
import uvicorn
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Autonomous AI Tutor Orchestrator",
    description="Intelligent middleware for educational tool orchestration with advanced personalization",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize workflow
workflow = TutorWorkflow()

@app.get("/")
async def root():
    return {
        "message": "Autonomous AI Tutor Orchestrator API",
        "version": "2.0.0", 
        "features": [
            "Educational context awareness",
            "Teaching style adaptation", 
            "Emotional state inference",
            "Mastery level personalization",
            "80+ tool scalable architecture"
        ]
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "orchestrator"}

@app.get("/user/{user_id}")
async def get_user_profile(user_id: str):
    """Get user profile with educational context"""
    try:
        user_profile = await workflow.db.get_user_profile(user_id)
        return user_profile
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"User not found: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint with educational context processing
    """
    try:
        logger.info(f"Processing chat request for user {request.user_id}")
        
        # Prepare initial state for LangGraph workflow
        initial_state = {
            "user_id": request.user_id,
            "session_id": request.session_id,
            "message": request.message,
            "chat_history": request.chat_history,
            "user_info": None,
            "educational_context": None,
            "intent": None,
            "extracted_parameters": {},
            "api_response": None,
            "final_response": None
        }
        
        # Execute the enhanced workflow
        result = await workflow.graph.ainvoke(initial_state)
        
        # Prepare response with educational context
        educational_context = None
        if result.get("educational_context"):
            educational_context = {
                "teaching_style": result["educational_context"].teaching_style.value,
                "emotional_state": result["educational_context"].emotional_state.value,
                "mastery_level": result["educational_context"].mastery_level.value,
                "inferred_difficulty": result["educational_context"].inferred_difficulty
            }
        
        return ChatResponse(
            response=result["final_response"],
            tool_used=result["intent"].value if result["intent"] else None,
            data=result.get("api_response", {}).get("data") if result.get("api_response") else None,
            educational_context_used=educational_context
        )
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)