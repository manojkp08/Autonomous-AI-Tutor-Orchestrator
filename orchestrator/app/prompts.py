# Enhanced prompts with educational context awareness
INTENT_ANALYSIS_PROMPT = """
Analyze the user's educational intent and determine the most appropriate tool.

Available Tools:
- flashcard_generator: For creating practice flashcards on specific topics
- note_maker: For generating structured notes on subjects  
- concept_explainer: For explaining complex concepts in detail
- quiz_generator: For creating practice questions and assessments

Student Context:
- Message: {message}
- Chat History: {chat_history}
- Student Profile: {user_info}

Educational Context to Consider:
- Emotional State: {emotional_state} (affects difficulty and approach)
- Mastery Level: {mastery_level} (affects content complexity) 
- Teaching Style: {teaching_style} (affects presentation style)

Analyze the intent and respond with ONLY the tool name.
"""

PARAMETER_EXTRACTION_PROMPTS = {
    "flashcard_generator": """
Extract and infer parameters for flashcard generation from the conversational context.

Student Request: {message}
Conversation History: {chat_history}
Student Profile: {user_info}

Educational Context:
- Emotional State: {emotional_state}
- Mastery Level: {mastery_level} (1-10 scale)
- Teaching Style: {teaching_style}

Parameter Inference Guidelines:
- Difficulty: Map emotional state and mastery level to easy/medium/hard
- Count: Adjust based on emotional state (fewer for anxious/tired, more for focused)
- Include Examples: Always true for visual teaching style

Extract parameters in JSON format with inferred values based on educational context.
""",
    
    "note_maker": """
Extract parameters for note generation with educational context adaptation.

Student Request: {message}
Conversation Context: {chat_history} 
Student Profile: {user_info}

Educational Context:
- Emotional State: {emotional_state}
- Mastery Level: {mastery_level}
- Teaching Style: {teaching_style}

Adaptation Rules:
- Visual teaching style: Enable analogies and examples
- Anxious/Confused: Use structured or outline style for clarity
- High mastery: Use narrative style for deeper understanding

Return parameters in JSON format.
""",
    
    "concept_explainer": """
Extract concept explanation parameters with context-aware depth adjustment.

Student Request: {message}
Conversation: {chat_history}
Student Profile: {user_info}

Educational Context:
- Emotional State: {emotional_state} 
- Mastery Level: {mastery_level}
- Teaching Style: {teaching_style}

Depth Adjustment:
- Anxious/Confused/Tired: Use "basic" depth
- Focused with mastery 7+: Use "advanced" or "comprehensive"
- Mastery 1-3: Always use "basic"
- Socratic style: Prefer "intermediate" to encourage thinking

Return parameters in JSON.
""",
    
    "quiz_generator": """
Extract quiz parameters with intelligent inference from educational context.

Student Request: {message}
Chat History: {chat_history}
Student Profile: {user_info}

Educational Context:
- Emotional State: {emotional_state}
- Mastery Level: {mastery_level}
- Teaching Style: {teaching_style}

Inference Rules:
- "struggling" → beginner difficulty
- "practice problems" → practice question type  
- Anxious → fewer questions, multiple_choice format
- Confused → beginner difficulty, fewer questions
- Focused → more questions, varied question types
- Mastery 1-3 → beginner, Mastery 4-7 → intermediate, Mastery 8-10 → advanced

Return JSON parameters with inferred values.
"""
}

EDUCATIONAL_CONTEXT_PROMPT = """
Analyze the educational context and adapt parameters accordingly.

Student Message: {message}
Student Profile: {user_info}

Determine appropriate adaptations based on:
1. Emotional State Inference from message tone and profile
2. Difficulty Level based on mastery and emotional state  
3. Teaching Style preferences
4. Content Complexity adjustment

Return JSON with:
- inferred_difficulty: easy/medium/hard
- emotional_state: focused/anxious/confused/tired
- teaching_style: direct/socratic/visual/flipped_classroom
- adaptations: list of specific adaptations made
"""