"""
Data Cleaner module.
Responsibility: Normalize and clean structured resume data from the resume parser.

Input:  Raw structured data — { "skills": [...], "projects": [...], "experience": [...] }
Output: Clean structured data — same keys, normalized values

Operations performed:
    1. Trim whitespace from all values
    2. Remove duplicates (case-insensitive)
    3. Apply canonical skill name mappings  (e.g. "js" → "JavaScript")
    4. Filter non-technical / noise skills  (e.g. "team player", "MS Word")
    5. Title-case project names and deduplicate
    6. Normalize common experience labels   (e.g. "intern" → "Internship")

Why this matters:
    After Day 1 parsing, raw data may contain: duplicates, inconsistent casing,
    aliases, and soft skills that confuse the Technical Agent.
    This layer ensures AI gets clean, usable intelligence.
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# ─── Skill Name Mappings ───────────────────────────────────────────────────────
# Maps common aliases / abbreviations to their canonical form.

SKILL_MAPPINGS: Dict[str, str] = {
    # JavaScript ecosystem
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "reactjs": "React",
    "react.js": "React",
    "react": "React",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "angular": "Angular",
    "angularjs": "Angular",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "express": "Express.js",
    "expressjs": "Express.js",
    # Python ecosystem
    "py": "Python",
    "python": "Python",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "sklearn": "Scikit-learn",
    "scikit-learn": "Scikit-learn",
    "scikit learn": "Scikit-learn",
    # JVM / compiled languages
    "java": "Java",
    "kotlin": "Kotlin",
    "springboot": "Spring Boot",
    "spring boot": "Spring Boot",
    "spring": "Spring",
    "cpp": "C++",
    "c++": "C++",
    "csharp": "C#",
    "c#": "C#",
    "golang": "Go",
    "go": "Go",
    "rust": "Rust",
    "swift": "Swift",
    # Web basics
    "html": "HTML",
    "html5": "HTML",
    "css": "CSS",
    "css3": "CSS",
    # Databases
    "sql": "SQL",
    "mysql": "MySQL",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    "sqlite": "SQLite",
    # DevOps / Cloud
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "git": "Git",
    "linux": "Linux",
    "bash": "Bash",
    "shell": "Shell Scripting",
    "terraform": "Terraform",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "jenkins": "Jenkins",
    "github actions": "GitHub Actions",
    # APIs / protocols
    "rest": "REST API",
    "restapi": "REST API",
    "rest api": "REST API",
    "graphql": "GraphQL",
    "websocket": "WebSocket",
    "websockets": "WebSocket",
    # Messaging / queues
    "rabbitmq": "RabbitMQ",
    "kafka": "Kafka",
    "celery": "Celery",
    # AI / ML keywords
    "ml": "Machine Learning",
    "ai": "Artificial Intelligence",
    "nlp": "NLP",
    "deep learning": "Deep Learning",
    "dl": "Deep Learning",
    "llm": "LLM",
    "openai": "OpenAI",
    # Mobile
    "android": "Android",
    "ios": "iOS",
    "react native": "React Native",
    "flutter": "Flutter",
}

# ─── Noise Skills (non-technical soft skills and basic office tools) ───────────
NOISE_SKILLS = {
    # Soft skills
    "team player", "communication", "good communication", "communication skills",
    "hard working", "hardworking", "leadership", "teamwork",
    "problem solving", "problem-solving", "critical thinking",
    "time management", "self-motivated", "self motivated",
    "detail-oriented", "detail oriented", "fast learner", "quick learner",
    "multitasking", "adaptability", "creativity", "creative thinking",
    "interpersonal skills", "interpersonal", "verbal communication",
    "written communication", "presentation skills",
    # Basic office software
    "microsoft word", "microsoft excel", "microsoft powerpoint",
    "ms word", "ms excel", "ms office", "microsoft office",
    "word", "excel", "powerpoint", "outlook", "ms outlook",
    "google docs", "google sheets", "google slides",
    # Design tools unlikely to matter in dev interviews
    "photoshop", "corel draw", "ms paint",
}

# ─── Experience Term Mappings ─────────────────────────────────────────────────

EXPERIENCE_MAPPINGS: Dict[str, str] = {
    "intern": "Internship",
    "internship": "Internship",
    "interns": "Internship",
    "trainee": "Trainee",
    "fresher": "Fresher",
    "fresh graduate": "Fresher",
    "junior developer": "Junior Developer",
    "junior": "Junior Developer",
    "senior developer": "Senior Developer",
    "senior software engineer": "Senior Software Engineer",
    "senior": "Senior Developer",
    "backend developer": "Backend Developer",
    "back-end developer": "Backend Developer",
    "frontend developer": "Frontend Developer",
    "front-end developer": "Frontend Developer",
    "full stack developer": "Full Stack Developer",
    "full-stack developer": "Full Stack Developer",
    "fullstack developer": "Full Stack Developer",
    "software engineer": "Software Engineer",
    "software developer": "Software Developer",
    "team lead": "Team Lead",
    "tech lead": "Tech Lead",
    "lead developer": "Tech Lead",
    "manager": "Manager",
    "engineering manager": "Engineering Manager",
    "architect": "Architect",
    "solutions architect": "Solutions Architect",
    "devops engineer": "DevOps Engineer",
    "data engineer": "Data Engineer",
    "data scientist": "Data Scientist",
    "machine learning engineer": "ML Engineer",
    "ml engineer": "ML Engineer",
}


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _normalize_skill(raw: str) -> str:
    """Map a raw skill string to its canonical form."""
    stripped = raw.strip()
    key = stripped.lower()
    return SKILL_MAPPINGS.get(key, stripped.title())


def _is_noise_skill(skill: str) -> bool:
    """Return True if the skill is a soft skill or irrelevant tool."""
    return skill.strip().lower() in NOISE_SKILLS


def _normalize_experience(raw: str) -> str:
    """Map raw experience label to its canonical form."""
    stripped = raw.strip()
    key = stripped.lower()
    return EXPERIENCE_MAPPINGS.get(key, stripped.title())


def _deduplicate(items: List[str]) -> List[str]:
    """
    Remove case-insensitive duplicates while preserving insertion order
    (first occurrence wins).
    """
    seen: set = set()
    result: List[str] = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


# ─── Public cleaning functions ────────────────────────────────────────────────

def clean_skills(raw_skills: List[str]) -> List[str]:
    """
    Clean a raw skills list:
      1. Strip whitespace
      2. Apply canonical name mapping
      3. Filter out noise / soft skills
      4. Deduplicate (case-insensitive)
    """
    normalized = [_normalize_skill(s) for s in raw_skills if s.strip()]
    filtered = [s for s in normalized if not _is_noise_skill(s)]
    return _deduplicate(filtered)


def clean_projects(raw_projects: List[str]) -> List[str]:
    """
    Clean project names:
      1. Strip whitespace
      2. Title-case
      3. Deduplicate (case-insensitive)
    """
    normalized = [p.strip().title() for p in raw_projects if p.strip()]
    return _deduplicate(normalized)


def clean_experience(raw_experience: List[str]) -> List[str]:
    """
    Clean experience entries:
      1. Normalize known labels (e.g. "intern" → "Internship")
      2. Deduplicate (case-insensitive)
    """
    normalized = [_normalize_experience(e) for e in raw_experience if e.strip()]
    return _deduplicate(normalized)


def clean_resume_data(raw_data: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """
    Main cleaning function — cleans all three sections in one call.

    Args:
        raw_data: Output from resume_parser.parse_resume().

    Returns:
        Clean structured data with the same keys.
        Always returns all three keys. Never returns None values.
    """
    cleaned = {
        "skills": clean_skills(raw_data.get("skills", [])),
        "projects": clean_projects(raw_data.get("projects", [])),
        "experience": clean_experience(raw_data.get("experience", [])),
    }

    logger.info(
        "Data cleaner — cleaned skills: %d, projects: %d, experience: %d",
        len(cleaned["skills"]),
        len(cleaned["projects"]),
        len(cleaned["experience"]),
    )
    return cleaned
