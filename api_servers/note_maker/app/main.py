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

app = FastAPI(title="Note Maker Server")

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

class NoteRequest(BaseModel):
    tool_name: str
    user_info: Dict[str, Any]
    chat_history: List[Dict[str, Any]]
    extracted_parameters: Dict[str, Any]
    educational_context: EducationalContext

class NoteResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "Note Maker API Server with Educational Context"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "note_maker"}

async def _generate_real_notes(topic: str, subject: str, note_style: str, 
                               context: EducationalContext, user_info: dict) -> dict:
    """Generate actual educational notes using Gemini"""
    
    # Adapt note style based on emotional state
    if context.emotional_state in ["anxious", "confused"]:
        note_style = "structured"
    elif context.emotional_state == "focused" and context.mastery_level >= 7:
        note_style = "narrative"
    
    # Build comprehensive prompt
    complexity = "beginner-friendly" if context.mastery_level <= 3 else \
                 "intermediate" if context.mastery_level <= 6 else "advanced"
    
    style_guide = {
        "visual": "Include visual descriptions, diagrams suggestions, and spatial relationships",
        "socratic": "Use questioning approach to guide understanding",
        "direct": "Clear, concise, step-by-step explanations",
        "flipped_classroom": "Application-focused with real-world connections"
    }
    
    prompt = f"""Generate comprehensive educational notes about {topic} in {subject}.

Student Profile:
- Name: {user_info.get('name')}
- Grade Level: {user_info.get('grade_level')}
- Mastery Level: {context.mastery_level}/10 ({complexity})
- Emotional State: {context.emotional_state}
- Teaching Style: {context.teaching_style}

Requirements:
- Format: {note_style} style
- Complexity: {complexity} level
- Teaching approach: {style_guide.get(context.teaching_style, 'standard')}
- Include 3-4 note sections with detailed content
- Each section should have 3-5 key points
- Include 2-3 practical examples
- Suggest visual elements if teaching style is visual

Return ONLY valid JSON with this structure:
{{
    "summary": "brief overview paragraph",
    "note_sections": [
        {{
            "title": "section title",
            "content": "detailed content paragraph",
            "key_points": ["point 1", "point 2", "point 3"]
        }}
    ],
    "key_concepts": ["concept 1", "concept 2", "concept 3"],
    "examples": ["example 1", "example 2"],
    "practice_suggestions": ["suggestion 1", "suggestion 2"]
}}"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        # Clean JSON
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()
        
        notes_data = json.loads(content)
        
        # Add visual elements for visual learners
        visual_elements = []
        if context.teaching_style == "visual":
            visual_elements = [
                f"Concept map showing {topic} relationships",
                f"Flowchart of {topic} processes",
                f"Infographic summarizing key {topic} points"
            ]
        
        # Add analogies if requested
        analogies = []
        if context.teaching_style in ["visual", "socratic"]:
            analogy_prompt = f"Generate 2 simple analogies to explain {topic} to a {complexity} learner. Return as JSON array."
            try:
                analogy_response = await llm.ainvoke([HumanMessage(content=analogy_prompt)])
                analogy_content = analogy_response.content.strip()
                if analogy_content.startswith("```"):
                    analogy_content = analogy_content[analogy_content.find("["): analogy_content.rfind("]")+1]
                analogies = json.loads(analogy_content)
            except:
                pass
        
        # Combine all data
        result = {
            "topic": topic,
            "title": f"Comprehensive Notes on {topic}",
            "summary": notes_data.get("summary", f"Educational overview of {topic}"),
            "note_sections": notes_data.get("note_sections", []),
            "key_concepts": notes_data.get("key_concepts", []),
            "examples": notes_data.get("examples", []),
            "analogies": analogies,
            "note_taking_style": note_style,
            "educational_adaptations": {
                "adapted_for_emotional_state": context.emotional_state,
                "adapted_for_mastery_level": context.mastery_level,
                "teaching_style_applied": context.teaching_style,
                "complexity_level": complexity
            },
            "practice_suggestions": notes_data.get("practice_suggestions", []),
            "visual_elements": visual_elements
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Note generation error: {e}")
        # Fallback
        return {
            "topic": topic,
            "title": f"Notes on {topic}",
            "summary": f"Educational overview of {topic} in {subject}",
            "note_sections": [{
                "title": "Introduction",
                "content": f"Overview of {topic}",
                "key_points": [f"Key aspect of {topic}"]
            }],
            "key_concepts": [f"Core concept in {topic}"],
            "examples": [f"Example of {topic}"],
            "analogies": [],
            "note_taking_style": note_style,
            "educational_adaptations": {
                "adapted_for_emotional_state": context.emotional_state,
                "adapted_for_mastery_level": context.mastery_level,
                "teaching_style_applied": context.teaching_style,
                "complexity_level": complexity
            },
            "practice_suggestions": [f"Practice {topic} concepts"],
            "visual_elements": []
        }

@app.post("/invoke")
async def invoke_tool(request: NoteRequest) -> NoteResponse:
    try:
        logger.info(f"Processing note request for {request.user_info.get('name')}")
        
        params = request.extracted_parameters
        context = request.educational_context
        
        topic = params.get("topic", "general")
        subject = params.get("subject", "general")
        note_style = params.get("note_taking_style", "structured")
        
        # Generate real notes with Gemini
        note_data = await _generate_real_notes(topic, subject, note_style, context, request.user_info)
        
        return NoteResponse(success=True, data=note_data)
        
    except Exception as e:
        logger.error(f"Note generation error: {e}")
        return NoteResponse(
            success=False,
            data={},
            error=f"Note generation failed: {str(e)}"
        )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)