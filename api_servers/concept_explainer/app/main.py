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

app = FastAPI(title="Concept Explainer API Server")

# Initialize Gemini LLM with better model
dotenv.load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-exp",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.8  # Higher temperature for more creative explanations
)

class EducationalContext(BaseModel):
    teaching_style: str
    emotional_state: str
    mastery_level: int
    inferred_difficulty: str

class ConceptRequest(BaseModel):
    tool_name: str
    user_info: Dict[str, Any]
    chat_history: List[Dict[str, Any]]
    extracted_parameters: Dict[str, Any]
    educational_context: EducationalContext

class ConceptResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "Concept Explainer API Server with Educational Context"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "concept_explainer"}

def _safe_extract_params(params: Dict[str, Any]) -> tuple:
    """Safely extract and validate parameters"""
    concept = params.get("concept_to_explain", params.get("concept", params.get("topic", "general concept")))
    topic = params.get("current_topic", params.get("subject", params.get("topic", "general")))
    depth = params.get("desired_depth", params.get("depth", params.get("level", "intermediate")))
    
    logger.info(f"Extracted params - concept: {concept}, topic: {topic}, depth: {depth}")
    return concept, topic, depth

def _adapt_depth(requested_depth: str, context: EducationalContext) -> str:
    """Adapt explanation depth based on educational context"""
    # Normalize depth values
    depth_map = {
        "basic": "basic",
        "beginner": "basic",
        "simple": "basic",
        "intermediate": "intermediate",
        "medium": "intermediate",
        "standard": "intermediate",
        "advanced": "advanced",
        "hard": "advanced",
        "expert": "comprehensive",
        "comprehensive": "comprehensive",
        "master": "comprehensive"
    }
    
    normalized = requested_depth.lower() if isinstance(requested_depth, str) else "intermediate"
    depth = depth_map.get(normalized, "intermediate")
    
    depth_order = ["basic", "intermediate", "advanced", "comprehensive"]
    current_index = depth_order.index(depth)
    
    # Adjust based on emotional state
    if context.emotional_state in ["anxious", "confused", "tired"]:
        current_index = max(0, current_index - 1)
    elif context.emotional_state == "focused" and context.mastery_level >= 7:
        current_index = min(len(depth_order) - 1, current_index + 1)
        
    # Adjust based on mastery level
    if context.mastery_level <= 3:
        current_index = 0
    elif context.mastery_level >= 8:
        current_index = min(len(depth_order) - 1, current_index + 1)
        
    return depth_order[current_index]

async def _generate_main_explanation(concept: str, topic: str, depth: str, 
                                     context: EducationalContext, user_info: dict) -> str:
    """Generate the main explanation text"""
    
    depth_requirements = {
        "basic": "Explain in simple terms suitable for beginners. Use everyday language and analogies.",
        "intermediate": "Provide detailed explanation with key mechanisms and relationships. Balance clarity with depth.",
        "advanced": "Deep dive into complex aspects, theoretical foundations, and advanced applications.",
        "comprehensive": "Exhaustive coverage including historical context, current research, edge cases, and future directions."
    }
    
    style_adaptations = {
        "visual": "Use vivid visual metaphors and spatial descriptions. Paint a mental picture.",
        "socratic": "Structure the explanation using questions that build understanding progressively.",
        "direct": "Be clear, concise, and systematic. Use numbered steps where appropriate.",
        "flipped_classroom": "Focus heavily on practical applications and real-world scenarios."
    }
    
    emotional_tone = {
        "anxious": "Be gentle and reassuring. Break concepts into small, digestible chunks. Emphasize that confusion is normal.",
        "confused": "Be extra clear. Define all terms. Provide multiple angles of understanding. Use concrete examples.",
        "tired": "Be concise but complete. Highlight the essential takeaways. Use bullet points mentally.",
        "focused": "Be engaging and challenging. Provide depth and encourage deeper thinking."
    }
    
    prompt = f"""You are an expert educator explaining "{concept}" to a {user_info.get('grade_level', 'student')}.

STUDENT PROFILE:
- Name: {user_info.get('name', 'Student')}
- Grade: {user_info.get('grade_level', 'Unknown')}
- Current Mastery: {context.mastery_level}/10 in this topic
- Emotional State: {context.emotional_state}
- Learning Style: {context.teaching_style}

EXPLANATION REQUIREMENTS:
- Depth: {depth_requirements[depth]}
- Style: {style_adaptations.get(context.teaching_style, 'Engaging and clear')}
- Tone: {emotional_tone.get(context.emotional_state, 'Professional and engaging')}
- Context: This is being taught as part of {topic}

INSTRUCTIONS:
1. Start with a compelling hook or real-world connection
2. Explain {concept} thoroughly at the {depth} level
3. Connect it specifically to {topic}
4. Address common misconceptions if relevant
5. Make it personally relevant to a {user_info.get('grade_level', 'student')}

Write a comprehensive explanation paragraph (150-250 words for basic, 250-400 words for intermediate/advanced, 400-600 for comprehensive).

Return ONLY the explanation text, no JSON, no formatting."""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        explanation = response.content.strip()
        
        # Remove any markdown or code blocks
        if explanation.startswith("```"):
            explanation = explanation.split("```")[1].strip()
        
        return explanation
        
    except Exception as e:
        logger.error(f"Explanation generation error: {e}")
        return f"A comprehensive explanation of {concept} in the context of {topic}, covering its fundamental principles, key applications, and relevance to your learning."

async def _generate_real_examples(concept: str, topic: str, context: EducationalContext, 
                                  user_info: dict) -> List[str]:
    """Generate specific, contextual examples"""
    
    num_examples = 3 if context.mastery_level <= 5 else 4
    
    prompt = f"""Generate {num_examples} SPECIFIC, CONCRETE examples of "{concept}" in {topic}.

Student Context: Grade {user_info.get('grade_level')}, Mastery Level {context.mastery_level}/10

Requirements:
- Each example must be unique and specific (no generic statements)
- Include real-world scenarios a {user_info.get('grade_level')} student can relate to
- Progress from simple to complex
- Make them practical and memorable
- Each example should be 1-2 sentences

Return ONLY a JSON array of strings:
["example 1", "example 2", "example 3"{', "example 4"' if num_examples == 4 else ''}]"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        # Extract JSON array
        if "```" in content:
            content = content[content.find("["):content.rfind("]")+1]
        elif content.startswith("["):
            pass  # Already good
        else:
            # Try to find array in content
            start = content.find("[")
            end = content.rfind("]") + 1
            if start != -1 and end > start:
                content = content[start:end]
        
        examples = json.loads(content)
        return examples if isinstance(examples, list) else []
        
    except Exception as e:
        logger.error(f"Examples generation error: {e}")
        return [
            f"A practical application of {concept} in everyday {topic}",
            f"How {concept} is used professionally in {topic} field",
            f"An unexpected place where {concept} appears in {topic}"
        ]

async def _generate_related_concepts(concept: str, topic: str, context: EducationalContext) -> List[str]:
    """Generate related concepts appropriate for mastery level"""
    
    num_concepts = 3 if context.mastery_level <= 5 else 4
    
    prompt = f"""List {num_concepts} concepts related to "{concept}" in {topic}.

Student Mastery Level: {context.mastery_level}/10

Requirements:
- Include prerequisites (what to learn before)
- Include extensions (what to learn next)
- Make each concept specific and named
- Order from foundational to advanced

Return ONLY a JSON array of strings with concept names:
["Concept 1", "Concept 2", "Concept 3"{', "Concept 4"' if num_concepts == 4 else ''}]"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        if "```" in content:
            content = content[content.find("["):content.rfind("]")+1]
        
        related = json.loads(content)
        return related if isinstance(related, list) else []
        
    except Exception as e:
        logger.error(f"Related concepts error: {e}")
        return [
            f"Foundational concept for {concept}",
            f"Complementary concept to {concept}",
            f"Advanced extension of {concept}"
        ]

async def _generate_practice_questions(concept: str, topic: str, context: EducationalContext) -> List[str]:
    """Generate thoughtful practice questions"""
    
    question_complexity = {
        0: "recall and recognition",
        1: "basic application",
        2: "analysis and comparison",
        3: "synthesis and evaluation"
    }
    
    complexity_level = min(3, context.mastery_level // 3)
    
    prompt = f"""Create 3 practice questions about "{concept}" in {topic}.

Student Profile:
- Mastery Level: {context.mastery_level}/10
- Emotional State: {context.emotional_state}
- Cognitive Level: {question_complexity[complexity_level]}

Requirements:
- Question 1: {question_complexity[max(0, complexity_level-1)]}
- Question 2: {question_complexity[complexity_level]}
- Question 3: {question_complexity[min(3, complexity_level+1)]}
- Make questions thought-provoking and specific
- Questions should help solidify understanding
- If emotional state is anxious/confused, make questions supportive

Return ONLY a JSON array:
["Question 1?", "Question 2?", "Question 3?"]"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        if "```" in content:
            content = content[content.find("["):content.rfind("]")+1]
        
        questions = json.loads(content)
        return questions if isinstance(questions, list) else []
        
    except Exception as e:
        logger.error(f"Practice questions error: {e}")
        return [
            f"What are the key characteristics of {concept}?",
            f"How does {concept} apply in real-world {topic} scenarios?",
            f"What connections can you make between {concept} and other concepts?"
        ]

async def _generate_visual_aids(concept: str, topic: str, context: EducationalContext) -> List[str]:
    """Generate visual aid suggestions for visual learners"""
    
    if context.teaching_style != "visual":
        return []
    
    prompt = f"""Suggest 4 specific visual aids to understand "{concept}" in {topic}.

Requirements:
- Be specific about what each visual should show
- Include different types: diagrams, charts, infographics, models
- Make them actually helpful for understanding
- Describe what the visual would illustrate

Return ONLY a JSON array:
["Visual aid 1 description", "Visual aid 2 description", "Visual aid 3 description", "Visual aid 4 description"]"""

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        if "```" in content:
            content = content[content.find("["):content.rfind("]")+1]
        
        visuals = json.loads(content)
        return visuals if isinstance(visuals, list) else []
        
    except Exception as e:
        logger.error(f"Visual aids error: {e}")
        return [
            f"Concept map showing {concept} and its relationships",
            f"Flowchart of how {concept} works in practice",
            f"Diagram illustrating components of {concept}",
            f"Visual metaphor comparing {concept} to familiar objects"
        ]

def _generate_learning_path(concept: str, context: EducationalContext) -> List[str]:
    """Generate personalized learning path"""
    
    if context.mastery_level <= 3:
        return [
            f"Master the basic definition and terminology of {concept}",
            f"Practice identifying {concept} in simple, clear examples",
            f"Try applying {concept} to familiar situations",
            f"Gradually increase complexity with guided practice"
        ]
    elif context.mastery_level <= 6:
        return [
            f"Review and strengthen core understanding of {concept}",
            f"Explore edge cases and exceptions for {concept}",
            f"Apply {concept} to solve varied problems",
            f"Connect {concept} to related advanced topics"
        ]
    else:
        return [
            f"Research cutting-edge applications of {concept}",
            f"Analyze complex scenarios involving {concept}",
            f"Create original problems using {concept}",
            f"Teach {concept} to others to achieve mastery"
        ]

async def _generate_real_explanation(concept: str, topic: str, depth: str, 
                                     context: EducationalContext, user_info: dict) -> dict:
    """Generate complete concept explanation using multiple AI calls"""
    
    logger.info(f"Generating explanation for: {concept}")
    
    # Generate all components concurrently would be better, but sequential for clarity
    explanation = await _generate_main_explanation(concept, topic, depth, context, user_info)
    logger.info(f"Generated main explanation")
    
    examples = await _generate_real_examples(concept, topic, context, user_info)
    logger.info(f"Generated {len(examples)} examples")
    
    related_concepts = await _generate_related_concepts(concept, topic, context)
    logger.info(f"Generated {len(related_concepts)} related concepts")
    
    practice_questions = await _generate_practice_questions(concept, topic, context)
    logger.info(f"Generated {len(practice_questions)} practice questions")
    
    visual_aids = await _generate_visual_aids(concept, topic, context)
    logger.info(f"Generated {len(visual_aids)} visual aids")
    
    learning_path = _generate_learning_path(concept, context)
    
    # Determine complexity
    complexity = "simplified" if context.mastery_level <= 3 or context.emotional_state in ["anxious", "confused"] else \
                 "advanced" if context.mastery_level >= 8 and context.emotional_state == "focused" else \
                 "standard"
    
    return {
        "concept": concept,
        "topic_context": topic,
        "explanation": explanation,
        "examples": examples,
        "related_concepts": related_concepts,
        "visual_aids": visual_aids,
        "practice_questions": practice_questions,
        "educational_adaptations": {
            "original_depth_requested": depth,
            "adapted_depth": depth,
            "complexity_level": complexity,
            "teaching_approach": context.teaching_style,
            "emotional_state_considerations": context.emotional_state,
            "mastery_level": context.mastery_level
        },
        "learning_path_suggestions": learning_path,
        "personalization_note": f"This explanation has been tailored for {user_info.get('name', 'you')} based on your {context.teaching_style} learning style and current understanding level."
    }

@app.post("/invoke")
async def invoke_tool(request: ConceptRequest) -> ConceptResponse:
    try:
        logger.info(f"Processing concept explanation for {request.user_info.get('name')}")
        logger.info(f"Received parameters: {request.extracted_parameters}")
        
        context = request.educational_context
        
        # Safely extract parameters
        concept, topic, requested_depth = _safe_extract_params(request.extracted_parameters)
        
        # Adapt depth based on context
        adapted_depth = _adapt_depth(requested_depth, context)
        
        logger.info(f"Adapted depth: {requested_depth} -> {adapted_depth}")
        
        # Generate comprehensive explanation
        explanation_data = await _generate_real_explanation(
            concept, topic, adapted_depth, context, request.user_info
        )
        
        logger.info(f"Successfully generated explanation for {concept}")
        return ConceptResponse(success=True, data=explanation_data)
        
    except Exception as e:
        logger.error(f"Concept explanation error: {e}", exc_info=True)
        return ConceptResponse(
            success=False,
            data={},
            error=f"Concept explanation failed: {str(e)}"
        )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)