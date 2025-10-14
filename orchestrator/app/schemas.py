from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Literal
from enum import Enum
import re

class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

class TeachingStyle(str, Enum):
    DIRECT = "direct"
    SOCRATIC = "socratic" 
    VISUAL = "visual"
    FLIPPED_CLASSROOM = "flipped_classroom"

class EmotionalState(str, Enum):
    FOCUSED = "focused"
    ANXIOUS = "anxious"
    CONFUSED = "confused"
    TIRED = "tired"

class MasteryLevel(int, Enum):
    LEVEL_1 = 1
    LEVEL_2 = 2
    LEVEL_3 = 3
    LEVEL_4 = 4
    LEVEL_5 = 5
    LEVEL_6 = 6
    LEVEL_7 = 7
    LEVEL_8 = 8
    LEVEL_9 = 9
    LEVEL_10 = 10

class Message(BaseModel):
    role: Role
    content: str

class UserInfo(BaseModel):
    user_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    grade_level: str = Field(..., min_length=1)
    learning_style_summary: str = Field(..., min_length=1)
    emotional_state_summary: str = Field(..., min_length=1)
    mastery_level_summary: str = Field(..., min_length=1)
    
    @validator('emotional_state_summary')
    def validate_emotional_state(cls, v):
        valid_states = ['focused', 'anxious', 'confused', 'tired', 'motivated']
        if not any(state in v.lower() for state in valid_states):
            raise ValueError(f"Emotional state should contain one of {valid_states}")
        return v

class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    chat_history: List[Message]

class ToolIntent(str, Enum):
    FLASHCARD_GENERATOR = "flashcard_generator"
    NOTE_MAKER = "note_maker"
    CONCEPT_EXPLAINER = "concept_explainer"
    QUIZ_GENERATOR = "quiz_generator"
    UNKNOWN = "unknown"

class IntentAnalysis(BaseModel):
    intent: ToolIntent
    confidence: float

# Enhanced parameter schemas with educational context
class EducationalContext(BaseModel):
    teaching_style: TeachingStyle
    emotional_state: EmotionalState
    mastery_level: MasteryLevel
    inferred_difficulty: str = Field(pattern="^(easy|medium|hard|beginner|intermediate|advanced)$")

class FlashcardParams(BaseModel):
    topic: str = Field(..., min_length=1)
    count: int = Field(ge=1, le=20, default=5)
    difficulty: str = Field(pattern="^(easy|medium|hard)$")
    subject: str = Field(..., min_length=1)
    include_examples: bool = True

class NoteMakerParams(BaseModel):
    topic: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    note_taking_style: str = Field(pattern="^(outline|bullet_points|narrative|structured)$")
    include_examples: bool = True
    include_analogies: bool = False

class ConceptExplainerParams(BaseModel):
    concept_to_explain: str = Field(..., min_length=1)
    current_topic: str = Field(..., min_length=1)
    desired_depth: str = Field(pattern="^(basic|intermediate|advanced|comprehensive)$")

class QuizGeneratorParams(BaseModel):
    topic: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    difficulty: str = Field(pattern="^(beginner|intermediate|advanced)$")
    question_type: str = Field(pattern="^(practice|multiple_choice|true_false|fill_blank)$")
    num_questions: int = Field(ge=1, le=50, default=10)

class APIRequest(BaseModel):
    tool_name: str
    user_info: UserInfo
    chat_history: List[Message]
    extracted_parameters: Dict[str, Any]
    educational_context: EducationalContext

class APIResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    tool_used: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    educational_context_used: Optional[Dict[str, Any]] = None