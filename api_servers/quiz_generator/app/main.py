import dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage
import json
import os

logger = logging.getLogger(__name__)

app = FastAPI(title="Quiz Generator Server")

dotenv.load_dotenv()
# Initialize Gemini LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.7
)

class EducationalContext(BaseModel):
    teaching_style: str
    emotional_state: str
    mastery_level: int
    inferred_difficulty: str

class QuizRequest(BaseModel):
    tool_name: str
    user_info: Dict[str, Any]
    chat_history: List[Dict[str, Any]]
    extracted_parameters: Dict[str, Any]
    educational_context: EducationalContext

class QuizResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "Quiz Generator API Server with Educational Context"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "quiz_generator"}

def _adapt_difficulty(original_difficulty: str, context: EducationalContext) -> str:
    """Adapt quiz difficulty based on context"""
    # Normalize difficulty values
    difficulty_map = {
        "beginner": "easy",
        "intermediate": "medium",
        "advanced": "hard",
        "low": "easy",
        "high": "hard",
        "easy": "easy",
        "medium": "medium",
        "hard": "hard"
    }
    
    # Safe normalization with fallback
    normalized = original_difficulty.lower() if isinstance(original_difficulty, str) else "medium"
    mapped_difficulty = difficulty_map.get(normalized, "medium")
    
    if context.emotional_state in ["anxious", "confused"]:
        return "easy"
    elif context.emotional_state == "focused" and context.mastery_level >= 7:
        return "hard"
    elif context.mastery_level <= 3:
        return "easy"
    elif context.mastery_level >= 8:
        return "hard"
        
    return mapped_difficulty

def _adapt_question_type(original_type: str, context: EducationalContext) -> str:
    """Adapt question type based on emotional state"""
    # Normalize question type
    type_map = {
        "mcq": "multiple_choice",
        "multiple_choice": "multiple_choice",
        "true_false": "true_false",
        "tf": "true_false",
        "practice": "practice",
        "open": "practice",
        "open_ended": "practice"
    }
    
    normalized_type = original_type.lower() if isinstance(original_type, str) else "practice"
    question_type = type_map.get(normalized_type, "practice")
    
    if context.emotional_state in ["anxious", "confused"]:
        return "multiple_choice"
    elif context.teaching_style == "socratic":
        return "practice"
    
    return question_type

def _adapt_question_count(original_count, context: EducationalContext) -> int:
    """Adapt number of questions based on context"""
    # Robust type conversion with error handling
    try:
        if isinstance(original_count, str):
            original_count = int(original_count)
        elif not isinstance(original_count, int):
            original_count = 10  # default fallback
    except (ValueError, TypeError):
        logger.warning(f"Invalid question count value: {original_count}, using default of 10")
        original_count = 10
    
    if context.emotional_state in ["anxious", "tired"]:
        return min(original_count, 5)
    elif context.emotional_state == "focused" and context.mastery_level >= 7:
        return min(original_count + 5, 20)
    return min(original_count, 15)

async def _generate_real_question(index: int, topic: str, subject: str, difficulty: str,
                                  question_type: str, context: EducationalContext) -> dict:
    """Generate actual quiz question using Gemini"""
    
    complexity = "simple and clear" if context.mastery_level <= 3 else \
                 "moderate depth" if context.mastery_level <= 6 else "challenging and nuanced"
    
    style_note = ""
    if context.teaching_style == "visual":
        style_note = "Include visual thinking elements where appropriate."
    elif context.teaching_style == "socratic":
        style_note = "Frame questions to encourage critical thinking and reasoning."
    
    # Build question prompt based on type
    if question_type == "multiple_choice":
        prompt = f"""Create ONE {complexity} {difficulty} difficulty multiple choice question about {topic} in {subject}.

Student Context:
- Mastery Level: {context.mastery_level}/10
- Emotional State: {context.emotional_state}
- Teaching Style: {context.teaching_style}

Instructions:
- {style_note}
- Create a clear, unambiguous question
- Provide exactly 4 distinct options
- One option should be clearly correct
- Other options should be plausible but incorrect
- Include a detailed explanation of why the correct answer is right

Return ONLY valid JSON (no markdown, no code blocks):
{{
    "question": "the question text here",
    "options": ["option 1", "option 2", "option 3", "option 4"],
    "correct_answer": 0,
    "explanation": "detailed explanation of the correct answer"
}}"""
    
    elif question_type == "true_false":
        prompt = f"""Create ONE {complexity} true/false question about {topic} in {subject}.

Student Context: Mastery {context.mastery_level}/10, {context.emotional_state}

Return ONLY valid JSON:
{{
    "question": "statement to evaluate as true or false",
    "options": ["True", "False"],
    "correct_answer": 0,
    "explanation": "explanation of why this is true/false"
}}"""
    
    else:  # practice/open-ended
        prompt = f"""Create ONE {complexity} practice question about {topic} in {subject}.

Student Context: Mastery {context.mastery_level}/10

Return ONLY valid JSON:
{{
    "question": "the practice question",
    "options": [],
    "correct_answer": "sample answer with key points to look for",
    "explanation": "what makes a good answer to this question"
}}"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        # Aggressive JSON cleaning
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        # Remove any leading/trailing whitespace
        content = content.strip()
        
        question_data = json.loads(content)
        
        # Validate required fields
        if "question" not in question_data or "explanation" not in question_data:
            raise ValueError("Missing required fields in LLM response")
        
        # Add teaching style enhancements
        enhanced_question = question_data["question"]
        if context.teaching_style == "visual":
            enhanced_question += " (Consider creating a diagram to help your thinking)"
        elif context.teaching_style == "socratic":
            enhanced_question += " (What questions does this raise for you?)"
        
        # Add hints for struggling students
        hint = None
        if context.emotional_state in ["anxious", "confused"]:
            if context.emotional_state == "anxious":
                hint = f"Remember: It's okay to take your time with {topic}. Focus on one concept at a time."
            else:
                hint = f"Hint: Try breaking down {topic} into smaller parts. What's the main idea?"
        
        # Calculate points
        points = {"easy": 1, "medium": 2, "hard": 3}.get(difficulty, 1)
        if context.mastery_level >= 8 and difficulty == "hard":
            points += 1
        
        return {
            "id": index + 1,
            "question": enhanced_question,
            "type": question_type,
            "options": question_data.get("options", []),
            "correct_answer": question_data.get("correct_answer", 0),
            "explanation": question_data.get("explanation", "Explanation of answer"),
            "difficulty": difficulty,
            "points": points,
            "hint": hint
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error for question {index + 1}: {e}. Content: {content}")
        # Return fallback question
        return _create_fallback_question(index, topic, difficulty, question_type, context)
    except Exception as e:
        logger.error(f"Question generation error for {index + 1}: {e}")
        return _create_fallback_question(index, topic, difficulty, question_type, context)

def _create_fallback_question(index: int, topic: str, difficulty: str, 
                              question_type: str, context: EducationalContext) -> dict:
    """Create a fallback question when AI generation fails"""
    if question_type == "multiple_choice":
        return {
            "id": index + 1,
            "question": f"What is an important concept about {topic}?",
            "type": question_type,
            "options": [
                f"Key principle of {topic}",
                f"Related but different concept",
                f"Common misconception",
                f"Unrelated topic"
            ],
            "correct_answer": 0,
            "explanation": f"This represents a fundamental aspect of {topic}",
            "difficulty": difficulty,
            "points": 1,
            "hint": None
        }
    else:
        return {
            "id": index + 1,
            "question": f"Explain the main concept of {topic}",
            "type": question_type,
            "options": [],
            "correct_answer": f"A comprehensive explanation of {topic}",
            "explanation": f"Good answer should demonstrate understanding of {topic}",
            "difficulty": difficulty,
            "points": 1,
            "hint": None
        }

def _estimate_quiz_time(num_questions: int, difficulty: str, context: EducationalContext) -> str:
    """Estimate quiz completion time"""
    base_times = {"easy": 1, "medium": 2, "hard": 3}
    base_minutes = base_times.get(difficulty, 2) * num_questions
    
    if context.emotional_state in ["anxious", "confused"]:
        base_minutes *= 1.5
    elif context.emotional_state == "focused":
        base_minutes *= 0.8
        
    return f"Approximately {int(base_minutes)} minutes"

def _generate_quiz_instructions(context: EducationalContext) -> str:
    """Generate context-aware quiz instructions"""
    base_instructions = "Read each question carefully and select the best answer."
    
    if context.emotional_state == "anxious":
        return base_instructions + " Remember, this is for practice - it's okay to make mistakes."
    elif context.emotional_state == "confused":
        return base_instructions + " Take your time and use the hints if provided."
    elif context.emotional_state == "focused":
        return base_instructions + " Challenge yourself to think deeply about each question."
    else:
        return base_instructions

def _define_success_criteria(difficulty: str, mastery_level: int) -> str:
    """Define success criteria based on difficulty and mastery"""
    if difficulty == "easy":
        target = "70%"
    elif difficulty == "medium":
        target = "80%"
    else:
        target = "85%"
        
    if mastery_level <= 3:
        return f"Aim for {target} correct to demonstrate basic understanding"
    elif mastery_level <= 7:
        return f"Target {target} correct to show solid comprehension"
    else:
        return f"Strive for {target} correct to demonstrate advanced mastery"

def _safe_extract_params(params: Dict[str, Any]) -> tuple:
    """Safely extract and validate parameters"""
    # Extract topic and subject
    topic = params.get("topic", params.get("subject", "general"))
    subject = params.get("subject", params.get("topic", "general"))
    
    # Extract difficulty with variations
    difficulty = params.get("difficulty", params.get("level", "intermediate"))
    
    # Extract question type with variations
    question_type = params.get("question_type", params.get("type", params.get("format", "practice")))
    
    # Extract count with variations
    num_questions = params.get("num_questions", params.get("count", params.get("number", 10)))
    
    logger.info(f"Extracted params - topic: {topic}, subject: {subject}, difficulty: {difficulty}, "
                f"type: {question_type}, count: {num_questions}")
    
    return topic, subject, difficulty, question_type, num_questions

@app.post("/invoke")
async def invoke_tool(request: QuizRequest) -> QuizResponse:
    try:
        logger.info(f"Processing quiz request for {request.user_info.get('name')}")
        logger.info(f"Received parameters: {request.extracted_parameters}")
        
        context = request.educational_context
        
        # Safely extract parameters
        topic, subject, difficulty, question_type, num_questions = _safe_extract_params(
            request.extracted_parameters
        )
        
        # Adapt parameters based on context
        adapted_difficulty = _adapt_difficulty(difficulty, context)
        adapted_question_type = _adapt_question_type(question_type, context)
        adapted_num_questions = _adapt_question_count(num_questions, context)
        
        logger.info(f"Adapted params - difficulty: {adapted_difficulty}, "
                   f"type: {adapted_question_type}, count: {adapted_num_questions}")
        
        # Generate real questions using Gemini
        questions = []
        for i in range(adapted_num_questions):
            question = await _generate_real_question(
                i, topic, subject, adapted_difficulty, adapted_question_type, context
            )
            questions.append(question)
            logger.info(f"Generated question {i+1}/{adapted_num_questions}")
        
        quiz_data = {
            "quiz_title": f"{adapted_difficulty.title()} {topic} Quiz",
            "topic": topic,
            "subject": subject,
            "difficulty": adapted_difficulty,
            "question_type": adapted_question_type,
            "num_questions": adapted_num_questions,
            "questions": questions,
            "time_estimate": _estimate_quiz_time(adapted_num_questions, adapted_difficulty, context),
            "educational_adaptations": {
                "adapted_difficulty": adapted_difficulty,
                "adapted_question_count": adapted_num_questions,
                "emotional_state_considerations": context.emotional_state,
                "mastery_level_alignment": context.mastery_level,
                "teaching_style_influence": context.teaching_style,
                "original_parameters": request.extracted_parameters
            },
            "instructions": _generate_quiz_instructions(context),
            "success_criteria": _define_success_criteria(adapted_difficulty, context.mastery_level)
        }
        
        logger.info(f"Successfully generated {adapted_num_questions} questions for {topic}")
        return QuizResponse(success=True, data=quiz_data)
        
    except Exception as e:
        logger.error(f"Quiz generation error: {e}", exc_info=True)
        return QuizResponse(
            success=False,
            data={},
            error=f"Quiz generation failed: {str(e)}"
        )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)