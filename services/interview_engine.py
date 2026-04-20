"""
Interview Engine — LLM-generated dynamic question sets per candidate.
MAX_QUESTIONS = 14 for thorough Cuemath screening.
"""
from __future__ import annotations
from typing import Optional, List
from dataclasses import dataclass, field
from services.llm_client import structured_completion, json_completion
import json, re, random

MAX_QUESTIONS = 14


@dataclass
class Question:
    id: str
    text: str
    category: str       # warm_up|math_explain|empathy|methodology|engagement|advanced|simulation
    difficulty: str     # easy|standard|hard
    follow_up_probe: str
    teaching_focus: str = ""   # what this reveals about the candidate


# ── Static fallback bank ──────────────────────────────────────────────────────

STATIC_BANK: List[Question] = [
    Question("q_intro",
        "Tell me about yourself and what draws you to teaching children math.",
        "warm_up", "easy",
        "Which age group do you find most rewarding to work with, and why?",
        "motivation and self-awareness"),

    Question("q_fractions",
        "Explain the concept of fractions to a 9-year-old — speak to me as if I'm the child.",
        "math_explain", "standard",
        "Can you bring in a real-life example the child would instantly relate to — pizza, chocolate bar, or folding paper?",
        "ability to simplify + use of analogy"),

    Question("q_negative_numbers",
        "How would you explain negative numbers to a 7-year-old who's never heard of them? Make it feel natural, not scary.",
        "math_explain", "standard",
        "Can you build a small story or real-world moment that makes negative numbers feel obvious to that child?",
        "creativity in explanation + age-appropriateness"),

    Question("q_multiplication",
        "A child understands addition but can't grasp why multiplication works. How do you bridge that gap — without just saying 'it's repeated addition'?",
        "math_explain", "standard",
        "Can you demonstrate with a specific visual or real-world example that would make multiplication feel intuitive?",
        "conceptual depth + teaching sequence"),

    Question("q_percentages",
        "A student says: 'Why do I even need to learn percentages? I'll never use this in real life.' What do you say?",
        "engagement", "standard",
        "Can you make it even more concrete — give a moment in a child's actual life where percentages genuinely matter?",
        "relevance-making + student motivation"),

    Question("q_geometry",
        "How would you make geometry feel exciting to a 10-year-old who thinks it's just memorising shapes?",
        "engagement", "standard",
        "Walk me through a specific activity or analogy you'd use to make angles or area feel real.",
        "creativity + engagement strategies"),

    Question("q_stuck_student",
        "A student has been staring at the same problem for five minutes. They say 'I just don't get it' and look like they're about to give up. What do you do right now?",
        "empathy", "standard",
        "Walk me through exactly what you'd say to that child — word for word — in that moment.",
        "empathy + immediate response under pressure"),

    Question("q_same_mistake",
        "A student keeps making the same mistake on subtraction problems — even after you've explained it three different ways. How do you approach it the fourth time?",
        "methodology", "standard",
        "Describe a completely different, creative approach — something unexpected — that might finally make it click.",
        "patience + pedagogical flexibility"),

    Question("q_crying_child",
        "During an online session, a child starts crying because they feel they're 'too dumb for math'. How do you handle the next 60 seconds?",
        "empathy", "hard",
        "What specific words or actions would you use to rebuild their confidence before returning to the lesson?",
        "emotional intelligence + warmth under pressure"),

    Question("q_disengaged",
        "Halfway through a session, the child has completely zoned out — not listening anymore. What do you do to bring them back?",
        "engagement", "standard",
        "What's the most creative technique you've used — or would use — to re-spark a child's curiosity about math?",
        "engagement recovery + creativity"),

    Question("q_simulation",
        "I'm going to play a confused 10-year-old student right now. Teach me what multiplication means — I'm genuinely confused. Ready?",
        "simulation", "hard",
        "How did you decide to break it down that way? What signals were you looking for from me?",
        "live teaching ability + responsiveness"),

    Question("q_parent_complaint",
        "A parent messages you after the session saying their child told them they didn't understand anything today. How do you respond?",
        "methodology", "hard",
        "How do you proactively prevent that from happening in the first place?",
        "professionalism + parent communication"),

    Question("q_online_challenges",
        "What's the hardest part of teaching math online compared to in-person, and how do you specifically overcome it?",
        "methodology", "standard",
        "Give me a concrete strategy you use to maintain engagement in an online setting.",
        "self-awareness + adaptation"),

    Question("q_adaptive_strong",
        "Tell me about a time you had to completely change how you were explaining a concept mid-session because it clearly wasn't working. What happened?",
        "advanced", "hard",
        "How do you know in real time that your explanation isn't landing? What specific signals do you watch for?",
        "real-time adaptability + metacognition"),

    Question("q_adaptive_weak",
        "What does patience really mean to you when a child keeps struggling with the same problem? How does it show up in how you actually teach?",
        "methodology", "easy",
        "Share a specific moment — real or imagined — where your patience made a real difference for a child who was stuck.",
        "patience + self-reflection"),

    Question("q_make_fun",
        "If you had to turn a boring math drill into a game for an 8-year-old right now — what would you do? Be specific.",
        "engagement", "standard",
        "How do you keep that energy going session after session without the novelty wearing off?",
        "gamification + sustained engagement"),

    Question("q_philosophy",
        "What do you think separates a great math tutor from someone who's just smart and knows math well?",
        "advanced", "standard",
        "Can you give me a concrete example that illustrates that difference?",
        "self-awareness + teaching philosophy"),
]

STANDARD_FLOW = [
    "q_intro", "q_fractions", "q_negative_numbers", "q_multiplication",
    "q_percentages", "q_stuck_student", "q_same_mistake",
    "q_disengaged", "q_simulation", "q_crying_child",
    "q_online_challenges", "q_parent_complaint",
    "q_adaptive_strong", "q_philosophy",
]
STRONG_NEXT = "q_adaptive_strong"
WEAK_NEXT   = "q_adaptive_weak"

_session_dynamic: dict[str, List[Question]] = {}

# ── Dynamic question generation ───────────────────────────────────────────────

QGEN_SYSTEM = """You are a senior hiring expert at Cuemath.
Generate a UNIQUE set of interview questions tailored to this specific tutor candidate.

Cuemath tutors work 1-on-1 with children aged 6-16. What matters most:
1. Can they explain math simply to a child — not just describe it?
2. Do they show genuine patience and empathy when a child is stuck?
3. Is their warmth natural, not performed?
4. Can they adapt mid-explanation when something isn't working?
5. Do children WANT to learn with them?

Return ONLY a JSON array of exactly 6 question objects. No preamble.
Each object:
{
  "id": "dq_1",
  "text": "<the exact question to ask>",
  "category": "<math_explain|empathy|engagement|methodology|advanced>",
  "difficulty": "<easy|standard|hard>",
  "follow_up_probe": "<deeper follow-up if answer is strong>",
  "teaching_focus": "<what this question reveals about the candidate>"
}

Rules:
- Make questions scenario-specific and concrete — not theoretical
- At least 2 must require the candidate to demonstrate an explanation live
- At least 1 must test emotional intelligence under pressure
- Avoid repeating: fractions, negative numbers, student giving up, making math fun
- Vary difficulty: 2 easy, 3 standard, 1 hard"""


async def generate_dynamic_questions(
    candidate_name: str,
    experience_years: Optional[int],
) -> List[Question]:
    ctx = (
        f"Candidate: {candidate_name}, "
        f"Experience: {experience_years or 'unknown'} years teaching. "
        f"Generate 6 fresh, unique questions for this specific candidate."
    )
    try:
        data = await json_completion(
            QGEN_SYSTEM,
            [{"role": "user", "content": ctx}],
            max_tokens=1400,
        )
        qs = []
        for i, item in enumerate(data):
            qs.append(Question(
                id=item.get("id", f"dq_{i+1}"),
                text=item["text"],
                category=item.get("category", "methodology"),
                difficulty=item.get("difficulty", "standard"),
                follow_up_probe=item.get("follow_up_probe", "Can you give a specific example?"),
                teaching_focus=item.get("teaching_focus", ""),
            ))
        return qs
    except Exception:
        pool = [q for q in STATIC_BANK if q.category != "warm_up"]
        random.shuffle(pool)
        return pool[:6]


def store_session_questions(session_id: str, questions: List[Question]):
    _session_dynamic[session_id] = questions


def get_question(session_id: str, question_id: str) -> Optional[Question]:
    if session_id in _session_dynamic:
        match = next((q for q in _session_dynamic[session_id] if q.id == question_id), None)
        if match:
            return match
    return next((q for q in STATIC_BANK if q.id == question_id), None)


def get_session_flow(session_id: str) -> List[str]:
    if session_id in _session_dynamic:
        dynamic_ids = [q.id for q in _session_dynamic[session_id]]
        flow = ["q_intro"] + dynamic_ids + [
            "q_stuck_student", "q_same_mistake", "q_simulation",
            "q_crying_child", "q_online_challenges", "q_philosophy",
        ]
        return list(dict.fromkeys(flow))[:MAX_QUESTIONS]
    return STANDARD_FLOW[:MAX_QUESTIONS]


def next_question_id(
    session_id: str,
    questions_asked: List[str],
    score_signal: float,
) -> Optional[str]:
    if len(questions_asked) >= MAX_QUESTIONS:
        return None
    for qid in get_session_flow(session_id):
        if qid not in questions_asked:
            return qid
    # Adaptive tail
    if STRONG_NEXT not in questions_asked and WEAK_NEXT not in questions_asked:
        return STRONG_NEXT if score_signal >= 0.65 else WEAK_NEXT
    return None


# ── Prompt builders ───────────────────────────────────────────────────────────

def build_system_prompt(candidate_name: str) -> str:
    return f"""You are Alex, a warm, professional AI interviewer conducting a Cuemath tutor screening.
Cuemath connects tutors with children aged 6-16 for 1-on-1 math sessions.

You are evaluating: communication clarity, patience, empathy, ability to simplify math, warmth with children, and real-time adaptability.
Candidate: {candidate_name}

BEHAVIOUR:
1. Sound like a real, friendly person — NOT a robot or corporate voice.
2. NEVER repeat a question already asked.
3. Keep YOUR responses to 2-4 sentences maximum — you are the interviewer, not the teacher.
4. Use natural transitions: "That's a great perspective.", "I love that example.", "That makes sense." — then move to the next question.
5. If an answer is vague or very short, probe gently before moving on: "Can you walk me through exactly what you'd say to the child?"
6. If the answer is strong, briefly acknowledge warmly: "That's really clear — I could picture a child getting it." then proceed.
7. During the simulation question, actually ROLEPLAY as a confused 10-year-old for 2-3 exchanges.
8. End the interview with: "Thank you so much — you've given me a lot to think about. The Cuemath team will be in touch soon. Best of luck!"
9. When the interview is fully complete (all questions asked + closing done), append exactly: [INTERVIEW_COMPLETE]

FOCUS: You are looking for tutors children will LOVE learning with. Warmth matters as much as knowledge."""


def build_turn_prompt(
    question_id: str,
    session_id: str,
    follow_up_needed: bool,
    fu_type: str,
    candidate_text: str,
) -> str:
    q = get_question(session_id, question_id)
    q_text = q.text if q else ""
    probe  = q.follow_up_probe if q else "Can you give a specific example?"

    if follow_up_needed:
        instructions = {
            "short":        "The answer was very brief. Ask warmly to elaborate — what would they actually say or do step by step?",
            "vague":        "The answer lacked concrete detail. Ask for a specific real-life example a child would understand.",
            "complex":      "The explanation was too technical. Ask them to simplify it for a 9-year-old who has never heard those terms.",
            "off_topic":    "The candidate went off-topic. Politely and warmly redirect back to the teaching question.",
            "silent":       "The candidate gave no real response. Gently encourage them — no pressure, just share their thoughts.",
            "strong_probe": f"The answer was strong — go deeper: {probe}",
        }
        instruction = instructions.get(fu_type, "Ask a warm, gentle follow-up to encourage more depth.")
    else:
        instruction = (
            f'The answer was adequate. Acknowledge it briefly and naturally. '
            f'Then ask this next question (weave it in conversationally, do NOT just blurt it): "{q_text}"'
        )

    return (
        f"INSTRUCTION: {instruction}\n\n"
        f"Do NOT repeat anything from the conversation history. "
        f"Keep response to 2-4 sentences. Speak naturally as Alex."
    )