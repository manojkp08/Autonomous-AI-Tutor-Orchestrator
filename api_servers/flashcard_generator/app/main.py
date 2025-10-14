from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage
import json
import dotenv
import os

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Flashcard Generator",
    description="Specialized server for flashcard generation with educational context adaptation"
)

dotenv.load_dotenv()

# Initialize Gemini LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.7
)

class EducationalContext(BaseModel):
    teaching_style: str
    emotional_state: str
    mastery_level: int
    inferred_difficulty: str

class FlashcardRequest(BaseModel):
    tool_name: str
    user_info: Dict[str, Any]
    chat_history: List[Dict[str, Any]]
    extracted_parameters: Dict[str, Any]
    educational_context: EducationalContext

class FlashcardResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "Flashcard Generator API Server with Educational Context"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "flashcard_generator"}

def _adapt_flashcard_count(original_count: int, context: EducationalContext) -> int:
    """Adapt flashcard count based on emotional state"""
    # Safely convert to int with better error handling
    try:
        if isinstance(original_count, str):
            original_count = int(original_count)
        elif not isinstance(original_count, int):
            original_count = 5  # default fallback
    except (ValueError, TypeError):
        logger.warning(f"Invalid count value: {original_count}, using default of 5")
        original_count = 5
    
    if context.emotional_state in ["anxious", "confused", "tired"]:
        return min(original_count, 3)
    elif context.emotional_state == "focused" and context.mastery_level >= 7:
        return min(original_count + 2, 20)
    return min(original_count, 10)

def _adapt_difficulty(original_difficulty: str, context: EducationalContext) -> str:
    """Adapt difficulty based on mastery and emotional state"""
    # Normalize difficulty values
    difficulty_map = {
        "low": "easy",
        "medium": "medium",
        "high": "hard",
        "easy": "easy",
        "hard": "hard"
    }
    
    normalized_difficulty = difficulty_map.get(original_difficulty.lower() if original_difficulty else "medium", "medium")
    
    if context.emotional_state in ["anxious", "confused"]:
        return "easy"
    elif context.mastery_level >= 8 and context.emotional_state == "focused":
        return "hard"
    return normalized_difficulty

async def _generate_real_flashcard(index: int, topic: str, subject: str, 
                                   difficulty: str, context: EducationalContext) -> dict:
    """Generate actual flashcard content using Gemini"""
    
    # Build context-aware prompt
    complexity = "simple and clear" if context.mastery_level <= 4 else "detailed and comprehensive"
    style_instruction = ""
    
    if context.teaching_style == "visual":
        style_instruction = "Include visual imagery or diagrams in the explanation."
    elif context.teaching_style == "socratic":
        style_instruction = "Frame the answer to encourage further thinking."
    
    prompt = f"""Create a {difficulty} difficulty flashcard about {topic} in {subject}.
    
Student context:
- Mastery level: {context.mastery_level}/10
- Emotional state: {context.emotional_state}
- Preferred style: {context.teaching_style}

Requirements:
- Make it {complexity}
- {style_instruction}
- Include a practical example

Return ONLY valid JSON with this exact structure:
{{
    "question": "the flashcard question",
    "answer": "the comprehensive answer",
    "example": "a practical example or application"
}}"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        # Clean JSON response
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
        
        flashcard_data = json.loads(content)
        
        # Add metadata
        flashcard_data.update({
            "id": index + 1,
            "title": f"Flashcard {index + 1} on {topic}",
            "difficulty": difficulty,
            "adapted_for": {
                "teaching_style": context.teaching_style,
                "emotional_state": context.emotional_state,
                "mastery_level": context.mastery_level
            }
        })
        
        return flashcard_data
        
    except Exception as e:
        logger.error(f"Flashcard generation error: {e}")
        # Fallback
        return {
            "id": index + 1,
            "title": f"Flashcard {index + 1} on {topic}",
            "question": f"What is an important concept about {topic}?",
            "answer": f"Key information about {topic} in {subject}",
            "example": f"Example application of {topic}",
            "difficulty": difficulty
        }

def _generate_adaptation_details(context: EducationalContext, user_info: dict) -> str:
    """Generate human-readable adaptation details"""
    adaptations = []
    
    if context.emotional_state == "anxious":
        adaptations.append("reduced complexity for comfort")
    elif context.emotional_state == "confused":
        adaptations.append("simplified concepts with clear explanations")
    elif context.emotional_state == "focused":
        adaptations.append("enhanced challenge for engagement")
        
    if context.teaching_style == "visual":
        adaptations.append("added visual examples")
    elif context.teaching_style == "socratic":
        adaptations.append("included thought-provoking questions")
        
    adaptation_text = ", ".join(adaptations) if adaptations else "standard presentation"
    return f"Adapted for {user_info.get('name', 'student')}: {adaptation_text}"

def _safe_extract_params(params: Dict[str, Any]) -> tuple:
    """Safely extract and validate parameters"""
    # Extract count with fallback
    count = params.get("count", params.get("number", 5))
    
    # Extract topic and subject
    topic = params.get("topic", params.get("subject", "general"))
    subject = params.get("subject", params.get("topic", "general"))
    
    # Extract difficulty
    difficulty = params.get("difficulty", "medium")
    
    logger.info(f"Extracted params - count: {count}, topic: {topic}, subject: {subject}, difficulty: {difficulty}")
    
    return count, topic, subject, difficulty

@app.post("/invoke")
async def invoke_tool(request: FlashcardRequest) -> FlashcardResponse:
    try:
        logger.info(f"Processing flashcard request for {request.user_info.get('name')}")
        logger.info(f"Received parameters: {request.extracted_parameters}")
        
        context = request.educational_context
        
        # Safely extract parameters
        count, topic, subject, difficulty = _safe_extract_params(request.extracted_parameters)
        
        # Adapt based on educational context
        adapted_count = _adapt_flashcard_count(count, context)
        adapted_difficulty = _adapt_difficulty(difficulty, context)
        
        logger.info(f"Adapted: count={adapted_count}, difficulty={adapted_difficulty}")
        
        # Generate real flashcards using Gemini
        flashcards = []
        for i in range(adapted_count):
            flashcard = await _generate_real_flashcard(
                i, topic, subject, adapted_difficulty, context
            )
            flashcards.append(flashcard)
        
        response_data = {
            "flashcards": flashcards,
            "topic": topic,
            "subject": subject,
            "difficulty": adapted_difficulty,
            "count": adapted_count,
            "adaptation_details": _generate_adaptation_details(context, request.user_info),
            "educational_context_applied": {
                "teaching_style": context.teaching_style,
                "emotional_state": context.emotional_state,
                "mastery_level": context.mastery_level,
                "original_parameters": request.extracted_parameters
            }
        }
        
        logger.info(f"Successfully generated {adapted_count} flashcards with {context.teaching_style} style")
        return FlashcardResponse(success=True, data=response_data)
        
    except Exception as e:
        logger.error(f"Flashcard generation error: {e}", exc_info=True)
        return FlashcardResponse(
            success=False,
            data={},
            error=f"Flashcard generation failed: {str(e)}"
        )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)