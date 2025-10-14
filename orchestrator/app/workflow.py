from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, SystemMessage
from typing import TypedDict, Annotated
import operator
import json
import httpx
import os
import re
import dotenv

dotenv.load_dotenv()

from orchestrator.app.schemas import *
from .database import Database, SAMPLE_USERS
from .prompts import INTENT_ANALYSIS_PROMPT, PARAMETER_EXTRACTION_PROMPTS, EDUCATIONAL_CONTEXT_PROMPT

class WorkflowState(TypedDict):
    user_id: str
    session_id: str
    message: str
    chat_history: List[Message]
    user_info: Optional[UserInfo]
    educational_context: Optional[EducationalContext]
    intent: Optional[ToolIntent]
    extracted_parameters: Dict[str, Any]
    api_response: Optional[Dict[str, Any]]
    final_response: Optional[str]


class TutorWorkflow:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1
        )
        self.db = Database()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("retrieve_state", self.retrieve_state)
        workflow.add_node("analyze_educational_context", self.analyze_educational_context)
        workflow.add_node("analyze_intent", self.analyze_intent)
        workflow.add_node("extract_flashcard_params", self.extract_flashcard_params)
        workflow.add_node("extract_note_params", self.extract_note_params)
        workflow.add_node("extract_concept_params", self.extract_concept_params)
        workflow.add_node("extract_quiz_params", self.extract_quiz_params)
        workflow.add_node("dispatch_to_api", self.dispatch_to_api)
        workflow.add_node("format_response", self.format_response)
        
        # Set entry point
        workflow.set_entry_point("retrieve_state")
        
        # Add edges
        workflow.add_edge("retrieve_state", "analyze_educational_context")
        workflow.add_edge("analyze_educational_context", "analyze_intent")
        
        workflow.add_conditional_edges(
            "analyze_intent",
            self.route_by_intent,
            {
                "extract_flashcard_params": "extract_flashcard_params",
                "extract_note_params": "extract_note_params",
                "extract_concept_params": "extract_concept_params",
                "extract_quiz_params": "extract_quiz_params",
                "format_response": "format_response"
            }
        )
        
        workflow.add_edge("extract_flashcard_params", "dispatch_to_api")
        workflow.add_edge("extract_note_params", "dispatch_to_api")
        workflow.add_edge("extract_concept_params", "dispatch_to_api")
        workflow.add_edge("extract_quiz_params", "dispatch_to_api")
        workflow.add_edge("dispatch_to_api", "format_response")
        workflow.add_edge("format_response", END)
        
        return workflow.compile()
    
    async def retrieve_state(self, state: WorkflowState) -> WorkflowState:
        """Retrieve user profile and state"""
        user_id = state["user_id"]
        user_profile = await self.db.get_user_profile(user_id)
        
        if user_profile:
            state["user_info"] = UserInfo(
                user_id=user_profile["user_id"],
                name=user_profile["name"],
                grade_level=user_profile["grade_level"],
                learning_style_summary=user_profile["learning_style_summary"],
                emotional_state_summary=user_profile["emotional_state_summary"],
                mastery_level_summary=user_profile["mastery_level_summary"]
            )
        
        return state
    
    async def analyze_educational_context(self, state: WorkflowState) -> WorkflowState:
        """Analyze and adapt based on educational context"""
        try:
            user_info = state["user_info"]
            message = state["message"]
            
            # Infer emotional state from message
            emotional_state = self._infer_emotional_state(message, user_info.emotional_state_summary)
            
            # Infer difficulty based on mastery and emotional state
            inferred_difficulty = self._infer_difficulty(
                user_info.mastery_level_summary, 
                emotional_state
            )
            
            # Get teaching style from user profile
            user_profile = await self.db.get_user_profile(state["user_id"])
            teaching_style = user_profile.get("preferred_teaching_style", TeachingStyle.DIRECT)
            
            state["educational_context"] = EducationalContext(
                teaching_style=teaching_style,
                emotional_state=emotional_state,
                mastery_level=user_profile.get("current_mastery_level", MasteryLevel.LEVEL_1),
                inferred_difficulty=inferred_difficulty
            )
            
        except Exception as e:
            print(f"Educational context analysis error: {e}")
            # Fallback context
            state["educational_context"] = EducationalContext(
                teaching_style=TeachingStyle.DIRECT,
                emotional_state=EmotionalState.FOCUSED,
                mastery_level=MasteryLevel.LEVEL_1,
                inferred_difficulty="medium"
            )
            
        return state
    
    def _infer_emotional_state(self, message: str, current_state: str) -> EmotionalState:
        """Infer emotional state from message content"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['confused', 'lost', "don't understand", "don't get"]):
            return EmotionalState.CONFUSED
        elif any(word in message_lower for word in ['anxious', 'nervous', 'worried', 'struggling', 'hard']):
            return EmotionalState.ANXIOUS
        elif any(word in message_lower for word in ['tired', 'exhausted', 'sleepy', 'burned out']):
            return EmotionalState.TIRED
        elif any(word in message_lower for word in ['focused', 'ready', 'excited', 'motivated']):
            return EmotionalState.FOCUSED
        
        # Fallback to current state from profile
        if 'focused' in current_state.lower():
            return EmotionalState.FOCUSED
        elif 'anxious' in current_state.lower():
            return EmotionalState.ANXIOUS
        elif 'confused' in current_state.lower():
            return EmotionalState.CONFUSED
        else:
            return EmotionalState.FOCUSED
    
    def _infer_difficulty(self, mastery_summary: str, emotional_state: EmotionalState) -> str:
        """Infer appropriate difficulty level"""
        # Extract mastery level from summary
        mastery_match = re.search(r'Level\s*(\d+)', mastery_summary)
        mastery_level = int(mastery_match.group(1)) if mastery_match else 1
        
        # Adjust based on emotional state
        if emotional_state in [EmotionalState.ANXIOUS, EmotionalState.CONFUSED, EmotionalState.TIRED]:
            return "easy"
        elif emotional_state == EmotionalState.FOCUSED and mastery_level >= 7:
            return "hard"
        else:
            return "medium"
    
    async def analyze_intent(self, state: WorkflowState) -> WorkflowState:
        """Analyze user intent with educational context"""
        try:
            prompt = INTENT_ANALYSIS_PROMPT.format(
                message=state["message"],
                chat_history=state["chat_history"],
                user_info=state["user_info"].model_dump(),
                emotional_state=state["educational_context"].emotional_state.value,
                mastery_level=state["educational_context"].mastery_level.value,
                teaching_style=state["educational_context"].teaching_style.value
            )
            
            messages = [HumanMessage(content=prompt)]
            response = await self.llm.ainvoke(messages)
            tool_name = response.content.strip().lower()

            # print(f"🔍 LLM Intent Response: '{tool_name}'")
            
            # Map to ToolIntent
            intent_map = {
                'flashcard': ToolIntent.FLASHCARD_GENERATOR,
                'note': ToolIntent.NOTE_MAKER,
                'concept': ToolIntent.CONCEPT_EXPLAINER,
                'explain': ToolIntent.CONCEPT_EXPLAINER,
                'quiz': ToolIntent.QUIZ_GENERATOR,
                'practice': ToolIntent.QUIZ_GENERATOR,
                'question': ToolIntent.QUIZ_GENERATOR
            }
            
            for keyword, intent in intent_map.items():
                if keyword in tool_name:
                    state["intent"] = intent
                    return state
            state["intent"] = self._analyze_intent_keywords(state["message"])
                
        except Exception as e:
            print(f"Intent analysis error: {e}")
            state["intent"] = self._analyze_intent_keywords(state["message"])
            
        return state
    
    def _analyze_intent_keywords(self, message: str) -> ToolIntent:
        """
        Fallback intent analysis using keyword matching
        Used when LLM fails or in testing environments
        """
        message_lower = message.lower()
    
        # Flashcard keywords
        if any(word in message_lower for word in 
               ['flashcard', 'memorize', 'cards', 'practice terms', 'drill']):
            return ToolIntent.FLASHCARD_GENERATOR
    
        # Note keywords
        if any(word in message_lower for word in 
               ['note', 'notes', 'summary', 'outline', 'write']):
            return ToolIntent.NOTE_MAKER
    
        # Concept keywords
        if any(word in message_lower for word in 
               ['explain', 'concept', 'understand', 'what is', 'how does', 'tell me about']):
            return ToolIntent.CONCEPT_EXPLAINER
    
        # Quiz/Practice keywords
        if any(word in message_lower for word in 
               ['quiz', 'practice', 'questions', 'test', 'problems', 'exercises']):
            return ToolIntent.QUIZ_GENERATOR
    
        return ToolIntent.UNKNOWN
    
    async def extract_flashcard_params(self, state: WorkflowState) -> WorkflowState:
        """Extract parameters with educational context adaptation"""
        return await self._extract_parameters("flashcard_generator", state)
    
    async def extract_note_params(self, state: WorkflowState) -> WorkflowState:
        """Extract parameters with educational context adaptation"""
        return await self._extract_parameters("note_maker", state)
    
    async def extract_concept_params(self, state: WorkflowState) -> WorkflowState:
        """Extract parameters with educational context adaptation"""
        return await self._extract_parameters("concept_explainer", state)
    
    async def extract_quiz_params(self, state: WorkflowState) -> WorkflowState:
        """Extract parameters with educational context adaptation"""
        return await self._extract_parameters("quiz_generator", state)
    
    async def _extract_parameters(self, tool_name: str, state: WorkflowState) -> WorkflowState:
        """Generic parameter extraction with educational context"""
        try:
            prompt = PARAMETER_EXTRACTION_PROMPTS[tool_name].format(
                message=state["message"],
                chat_history=state["chat_history"],
                user_info=state["user_info"].model_dump(),
                emotional_state=state["educational_context"].emotional_state.value,
                mastery_level=state["educational_context"].mastery_level.value,
                teaching_style=state["educational_context"].teaching_style.value
            )
            
            messages = [HumanMessage(content=prompt)]
            response = await self.llm.ainvoke(messages)
            params_text = response.content.strip()
            
            # Clean JSON response
            if params_text.startswith("```json"):
                params_text = params_text[7:-3].strip()
            elif params_text.startswith("```"):
                params_text = params_text[3:-3].strip()
            
            params = json.loads(params_text)
            state["extracted_parameters"] = params
            
        except Exception as e:
            print(f"Parameter extraction error for {tool_name}: {e}")
            state["extracted_parameters"] = self._get_fallback_params(tool_name)
            
        return state
    
    def _get_fallback_params(self, tool_name: str) -> dict:
        """Get fallback parameters when extraction fails"""
        fallbacks = {
            "flashcard_generator": {
                "topic": "general",
                "count": 5,
                "difficulty": "medium",
                "subject": "general",
                "include_examples": True
            },
            "note_maker": {
                "topic": "general",
                "subject": "general", 
                "note_taking_style": "structured",
                "include_examples": True,
                "include_analogies": False
            },
            "concept_explainer": {
                "concept_to_explain": "general concept",
                "current_topic": "general",
                "desired_depth": "intermediate"
            },
            "quiz_generator": {
                "topic": "general",
                "subject": "general",
                "difficulty": "intermediate",
                "question_type": "practice",
                "num_questions": 10
            }
        }
        return fallbacks.get(tool_name, {})
    
    async def dispatch_to_api(self, state: WorkflowState) -> WorkflowState:
        """Dispatch request to appropriate API server"""
        if state["intent"] == ToolIntent.UNKNOWN:
            return state
            
        try:
            tool_mapping = {
                # ToolIntent.FLASHCARD_GENERATOR: os.getenv("FLASHCARD_API_URL"),
                # ToolIntent.NOTE_MAKER: os.getenv("NOTE_MAKER_API_URL"),
                # ToolIntent.CONCEPT_EXPLAINER: os.getenv("CONCEPT_EXPLAINER_API_URL"),
                # ToolIntent.QUIZ_GENERATOR: os.getenv("QUIZ_GENERATOR_API_URL")
                ToolIntent.FLASHCARD_GENERATOR: "http://localhost:8001",
                ToolIntent.NOTE_MAKER: "http://localhost:8002",
                ToolIntent.CONCEPT_EXPLAINER: "http://localhost:8003",
                ToolIntent.QUIZ_GENERATOR: "http://localhost:8004"
            }
            
            api_url = tool_mapping.get(state["intent"])
            if not api_url:
                state["api_response"] = {"success": False, "error": "Tool not configured"}
                return state
            
            request_data = APIRequest(
                tool_name=state["intent"].value,
                user_info=state["user_info"],
                chat_history=state["chat_history"],
                extracted_parameters=state["extracted_parameters"],
                educational_context=state["educational_context"]
            )
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{api_url}/invoke",
                    json=request_data.dict(),
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    state["api_response"] = response.json()
                else:
                    state["api_response"] = {
                        "success": False,
                        "error": f"API server error: {response.status_code}"
                    }
                    
        except Exception as e:
            print(f"API dispatch error: {e}")
            state["api_response"] = {
                "success": False,
                "error": f"Connection error: {str(e)}"
            }
            
        return state
    
    def format_response(self, state: WorkflowState) -> WorkflowState:
        """Format final response with educational context"""
        if state["intent"] == ToolIntent.UNKNOWN:
            state["final_response"] = "I understand you need help with learning. Could you please specify if you'd like flashcards, notes, concept explanations, or practice questions?"
        elif state["api_response"] and state["api_response"].get("success"):
            data = state["api_response"]["data"]
            tool_name = state["intent"].value.replace('_', ' ')
            
            # Create context-aware response
            context = state["educational_context"]
            adaptation_note = self._get_adaptation_note(context)
            
            state["final_response"] = (
                f"I've generated {tool_name} for you, adapted to your learning needs.\n"
                f"{adaptation_note}\n"
                f"Here are your results:\n\n{json.dumps(data, indent=2)}"
            )
        else:
            error = state["api_response"].get("error", "Unknown error") if state["api_response"] else "No response from tool"
            state["final_response"] = f"I encountered an issue while processing your request: {error}. Please try again."
            
        return state
    
    def _get_adaptation_note(self, context: EducationalContext) -> str:
        """Generate note about educational adaptations"""
        adaptations = []
        
        if context.emotional_state == EmotionalState.ANXIOUS:
            adaptations.append("simplified for comfort")
        elif context.emotional_state == EmotionalState.CONFUSED:
            adaptations.append("broken down into simpler concepts")
        elif context.emotional_state == EmotionalState.TIRED:
            adaptations.append("made concise for easy digestion")
        
        if context.teaching_style == TeachingStyle.VISUAL:
            adaptations.append("enhanced with visual elements")
        elif context.teaching_style == TeachingStyle.SOCRATIC:
            adaptations.append("structured to encourage thinking")
        
        if adaptations:
            return f"Adaptations: {', '.join(adaptations)}."
        return "Tailored to your learning preferences."

    def route_by_intent(self, state: WorkflowState) -> str:
        """Route to appropriate node based on intent"""
        intent = state.get("intent")
        routing = {
            ToolIntent.FLASHCARD_GENERATOR: "extract_flashcard_params",
            ToolIntent.NOTE_MAKER: "extract_note_params", 
            ToolIntent.CONCEPT_EXPLAINER: "extract_concept_params",
            ToolIntent.QUIZ_GENERATOR: "extract_quiz_params",
            ToolIntent.UNKNOWN: "format_response"
        }
        return routing.get(intent, "format_response")