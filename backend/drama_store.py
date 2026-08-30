"""Private local storage for the Fortitudo drama adjudication companion."""
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from config import DATA_ROOT as _DATA_ROOT

DATA_ROOT = Path(__import__("os").environ.get("FORTITUDO_DRAMA_DATA_DIR") or _DATA_ROOT / "drama")
PROGRAMMES_DIR = Path(__import__("os").environ.get("FORTITUDO_DRAMA_PROGRAMMES_DIR", r"C:\Werk\Fortitudostudios-Drama\Programmes"))
ONTOLOGY_PATH = Path(__import__("os").environ.get("FORTITUDO_DRAMA_ONTOLOGY_PATH", r"C:\Werk\Fortitudostudios-Drama\Drama_Visual_Arts_Adjudication_Ontology_v2.json"))
DB_PATH = DATA_ROOT / "adjudications.db"
REPORTS_DIR = DATA_ROOT / "reports"

DOMAINS = {
    "Speech & Drama": [
        ("Voice & Speech", "Vocal control, articulation, resonance and breath support.", "02", 
         ["Articulation", "Resonance", "Projection", "Modulation", "Diaphragmatic support", "Plosives", "Fricatives", "Tone quality"],
         ["Practice vowel elongation", "Use humming to find resonance", "Record and listen to breath pauses"]),
        ("Body & Physicality", "Embodied representation, alignment, and physical control.", "03",
         ["Kinesics", "Proxemics", "Alignment", "Gestural clarity", "Centering", "Tension release", "Muscle memory"],
         ["Mirror work for alignment", "Isolate movements in slow motion", "Check for unnecessary tension"]),
        ("Space & Composition", "Use of space, levels, facings, and staging logic.", "04",
         ["Blocking", "Upstaging", "Focus points", "Triangulation", "Dynamic levels", "Traversing the space"],
         ["Map the stage into grids", "Vary height levels for status", "Maintain audience sightlines"]),
        ("Character & Action", "Social-cognitive modeling and behavioral strategy.", "05",
         ["Subtext", "Objective", "Obstacle", "Tactics", "Inner monologue", "Emotional truth", "Motivation"],
         ["Identify the 'Big Want'", "List 3 tactics to get what you want", "Write a character biography"]),
        ("Interpretation & Meaning", "Subtext, goal representation, and thematic clarity.", "06",
         ["Theme", "Symbolism", "Metaphor", "Genre consistency", "Narrative arc", "Climax", "Nuance"],
         ["Identify the central question", "Vary the tempo to highlight meaning", "Find the 'turn' in the piece"]),
        ("Relationship & Ensemble", "Responsive interaction and interpersonal synchrony.", "07",
         ["Listening", "Reactive energy", "Ensemble cohesion", "Spatial awareness", "Give and take", "Shared breath"],
         ["Exercises in eye contact", "Group breathing exercises", "Practice blind ensemble cues"]),
        ("Rhythm & Attention", "Temporal control and audience engagement.", "08",
         ["Pacing", "Pause", "Staccato", "Legato", "Beat", "Cadence", "Audience connection"],
         ["Count beats for comic timing", "Vary sentence length for impact", "Hold the silence for tension"]),
        ("Improvisation & Spontaneity", "Real-time predictive adaptation and presence.", "09",
         ["Accepting the offer", "Yes, and...", "Active listening", "Impulse", "Flow state", "Risk-taking"],
         ["Practice 'Yes, and' drills", "Focus on the partner's eyes", "Don't plan the next line"]),
        ("Style & Convention", "Adherence to theatrical modes and stylistic logic.", "10",
         ["Naturalism", "Abstract", "Brechtian", "Epic", "Absurdism", "Melodrama", "Classical"],
         ["Research the historical period", "Identify key stylistic markers", "Consistent use of convention"]),
    ],
    "Visual Arts": [
        ("Context & Brief", "Understanding of the task, prompt or thematic framework.", "13",
         ["Conceptual framing", "Contextual research", "Brief adherence", "Thematic depth"],
         ["Brainstorm lateral associations", "Document the ideation process", "Review the original prompt"]),
        ("Visual Language", "Use of formal elements like line, shape, color, and texture.", "14",
         ["Chiaroscuro", "Sfumato", "Color theory", "Tonal range", "Mark-making", "Line weight"],
         ["Practice value scales", "Limit palette to study harmony", "Experiment with textured tools"]),
        ("Composition & Design", "Application of design principles such as balance, rhythm, and emphasis.", "15",
         ["Rule of thirds", "Negative space", "Golden ratio", "Visual weight", "Symmetry", "Focal point"],
         ["Thumbnail sketches for layout", "Check balance with a mirror", "Simplify the main shapes"]),
        ("Drawing & Sketching", "Technical control, observation, and mark-making in dry media.", "16",
         ["Hatching", "Cross-hatching", "Contour line", "Gesture drawing", "Perspective", "Proportion"],
         ["Daily life studies", "Blind contour exercises", "Use a viewfinder for framing"]),
        ("Painting & Surface", "Handling of wet media, surface quality, and tonal modelling.", "17",
         ["Impasto", "Glazing", "Scumbling", "Wash", "Underpainting", "Palette knife work"],
         ["Layer thin to thick", "Mix colors on the palette, not the canvas", "Study brushstroke direction"]),
        ("Photography", "Technical control of exposure, framing, and digital/analog process.", "18",
         ["Aperture", "Shutter speed", "ISO", "Depth of field", "Bokeh", "Rule of thirds", "Dynamic range"],
         ["Manual mode practice", "Study lighting at 'golden hour'", "Review histogram for exposure"]),
        ("Concept & Narrative", "Depth of meaning, subtext, and visual storytelling.", "19",
         ["Metaphor", "Allegory", "Narrative arc", "Semiotic meaning", "Visual metaphor"],
         ["Write a concept statement", "Critique the symbols used", "Seek multiple layers of meaning"]),
        ("Process & Research", "Evidence of experimentation, research, and conceptual development.", "20",
         ["Iterative design", "Visual journal", "Material exploration", "Comparative study"],
         ["Annotate your sketchbook", "Document failed experiments", "Keep a material log"]),
        ("Materiality & Craft", "Choice and handling of materials, finish, and presentation.", "21",
         ["Medium specificity", "Craftsmanship", "Mounting", "Finish", "Structural integrity"],
         ["Test material compatibility", "Clean edges and presentation", "Consider the display environment"]),
        ("Sculpture & 3D", "Mass, volume, structural integrity, and use of three-dimensional space.", "22",
         ["Armature", "Maquette", "Positive/Negative space", "Subtractive/Additive", "Kinetic"],
         ["Build a strong internal structure", "Walk around the piece constantly", "Consider shadows and light"]),
        ("Perception & Impact", "Audience engagement, visual psychology, and communicative impact.", "23",
         ["Aesthetic arrest", "Cognitive dissonance", "Emotive response", "Visual hierarchy"],
         ["Get feedback from observers", "Simplify the visual 'hook'", "Test readability from a distance"]),
        ("Ethics & Validity", "Adherence to ethical standards and interpretive validity.", "24",
         ["Originality", "Appropriation", "Integrity", "Representation", "Sustainability"],
         ["Check source material", "Cite influences clearly", "Ensure original contribution"]),
    ],
    "Music": [
        ("Technique", "Intonation, tone quality, articulation, and technical fluency.", None,
         ["Legato", "Staccato", "Vibrato", "Embouchure", "Fingering", "Breath control", "Double tonguing"],
         ["Slow practice with metronome", "Long tone exercises", "Scales and arpeggios"]),
        ("Interpretation", "Phrasing, dynamic control, and musical narrative.", None,
         ["Rubato", "Crescendo", "Diminuendo", "Agogic accent", "Musical arc", "Phrasing"],
         ["Sing the melody to find phrasing", "Mark the dynamic climax", "Research historical performance practice"]),
        ("Performance Psychology", "Attentional focus, anxiety regulation, and stage presence.", None,
         ["Flow state", "Centering", "Mental rehearsal", "Visualisation", "Performance anxiety"],
         ["Practice mindful breathing", "Perform for a small mock audience", "Positive self-talk"]),
        ("Rhythm & Pacing", "Temporal precision, ensemble synchrony, and rhythmic vitality.", None,
         ["Syncopation", "Polyrhythm", "Subdivision", "Tempo rubato", "Groove", "Pulse"],
         ["Clap complex rhythms", "Use a metronome for subdivision", "Foot tapping for pulse"]),
        ("Communication", "Audience engagement, emotional authenticity, and shared intentionality.", None,
         ["Expressive projection", "Eye contact", "Shared intent", "Stage persona"],
         ["Record and watch yourself", "Focus on the story of the music", "Imagine the performance space"]),
        ("Relationship & Ensemble", "Interpersonal synchrony, balance, and group communication.", None,
         ["Listening", "Balance", "Intonation", "Eye contact", "Cues", "Unified attack"],
         ["Rehearse without the conductor", "Record group rehearsals", "Focus on the bass line/foundation"]),
        ("Developmental Craft", "Integration of technical skill with artistic purpose.", None,
         ["Repertoire choice", "Artistic growth", "Technical maturity", "Style mastery"],
         ["Listen to diverse recordings", "Analyze the score structure", "Seek feedback from peers"]),
    ],
    "Dance": [
        ("Technique", "Body alignment, strength, flexibility, and technical precision.", None,
         ["Turnout", "Extension", "Core stability", "Plie", "Tendu", "Alignment", "Isolation"],
         ["Focus on floor work for core", "Consistent barre work", "Stretch after every session"]),
        ("Musicality", "Rhythmic awareness, phrasing, and relationship between movement and sound.", None,
         ["On the beat", "Syncopation", "Dynamics of movement", "Phrasing", "Accent"],
         ["Listen to the music without moving", "Clap the accents", "Vary movement quality with tempo"]),
        ("Performance Psychology", "Spatial command, focus, flow, and anxiety management.", None,
         ["Projection", "Focus", "Spatial awareness", "Confidence", "Flow"],
         ["Practice spot-fixing in turns", "Visualization of the routine", "Controlled breathing"]),
        ("Artistry & Expression", "Emotional truth, narrative clarity, and causal coherence.", None,
         ["Face expression", "Emotional range", "Narrative arc", "Characterization"],
         ["Use a mirror to check facial cues", "Understand the 'why' behind movement", "Watch yourself on video"]),
        ("Composition & Line", "Use of space, geometry of form, and choreographic understanding.", None,
         ["Arabesque", "Attitude", "Shapes", "Symmetry", "Levels", "Floor patterns"],
         ["Film from different angles", "Simplify transitions", "Check geometric clarity"]),
        ("Relationship & Ensemble", "Synchrony, spatial awareness between dancers, and ensemble impact.", None,
         ["Unison", "Canon", "Partnering", "Contact improvisation", "Trust", "Spatial proximity"],
         ["Mirroring exercises", "Practice weight-sharing", "Ensemble breathing"]),
        ("Engagement", "Stage presence, projection, and communicative impact.", None,
         ["Audience connection", "Energy levels", "Energy flow", "Stage presence"],
         ["Perform to a far point in the room", "Imagine the stage lights", "Focus on big energy"]),
    ],
    "Choirs / Vir kore": [
        ("Vocal Quality", "Vocal control, blend, balance, and tonal warmth.", None,
         ["Homogeneity", "Vowel matching", "Resonance", "Choral tone", "Balance"],
         ["Practice section tuning", "Vowel unification drills", "Listen for the overtones"]),
        ("Intonation & Musicality", "Pitch accuracy, harmonic detail, and active listening.", None,
         ["Pitch center", "Just intonation", "Harmonic clarity", "Listening"],
         ["Practice acappella tuning", "Staggered breathing for sustain", "Solfege training"]),
        ("Dynamics & Expression", "Musical contrast, character, and expressive phrasing.", None,
         ["Piano/Forte", "Nuance", "Expressive text", "Crescendo", "Diminuendo"],
         ["Exaggerate dynamics in rehearsal", "Discuss the poem/text meaning", "Vary vocal color"]),
        ("Diction & Articulation", "Coordination of consonants and clarity of text.", None,
         ["Consonants", "Vowels", "Diphthongs", "Textual clarity", "Articulation"],
         ["Tongue twisters for speed", "Practice text without pitch", "Check final consonants"]),
        ("Ensemble & Discipline", "Response to conductor, coordination, and stage presence.", None,
         ["Attack and release", "Conductor focus", "Deportment", "Focus", "Unified stance"],
         ["Practice silent attacks", "Unified turning of pages", "Stand in performance posture"]),
        ("Encouraging Closing Remarks", "Summarizing the performance and providing future direction.", None,
         ["Summary", "Positive reinforcement", "Next steps", "Growth mindset"],
         ["Find one specific highlight", "Encourage group identity", "Propose one goal for next year"]),
    ]
}

CRITERIA = DOMAINS["Speech & Drama"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    performer TEXT NOT NULL,
    category TEXT,
    venue TEXT,
    event_date TEXT,
    adjudicator TEXT,
    domain TEXT,
    outcome TEXT,
    overall_note TEXT,
    programme_file TEXT,
    programme_item_no TEXT,
    images TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    criterion TEXT NOT NULL,
    score INTEGER NOT NULL,
    observation TEXT,
    interpretation TEXT,
    feedback_competence TEXT,
    feedback_agency TEXT,
    feedback_challenge TEXT,
    ontology_nodes TEXT,
    images TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(session_id, criterion)
);
CREATE INDEX IF NOT EXISTS idx_assessments_session ON assessments(session_id);
"""


def now():
    return datetime.now().isoformat(timespec="seconds")


def connect():
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Check for legacy schema and drop if incompatible
    try:
        cursor = conn.execute("PRAGMA table_info(assessments)")
        cols = {row[1]: {"notnull": row[3]} for row in cursor.fetchall()}
        if cols and ("evidence" in cols and cols["evidence"]["notnull"]):
            # Incompatible legacy schema found, need to migrate or recreate
            # For simplicity in this local tool, we'll try to add the new columns
            # but if evidence is NOT NULL and missing from our code, we have a problem.
            pass
    except sqlite3.OperationalError:
        pass

    conn.executescript(SCHEMA)
    
    # Migration: Check for legacy columns and migrate data
    cursor = conn.execute("PRAGMA table_info(assessments)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "evidence" in columns:
        # If evidence is NOT NULL, we must drop the constraint or provide a default
        # SQLite doesn't support dropping NOT NULL directly easily without recreating table, 
        # so we'll just provide a default for it in the save_assessment if it exists.
        pass

    # Migration: add domain column if missing
    try:
        conn.execute("ALTER TABLE sessions ADD COLUMN domain TEXT")
        conn.execute("UPDATE sessions SET domain = 'Speech & Drama' WHERE domain IS NULL")
    except sqlite3.OperationalError:
        pass
    
    # Ensure other session columns exist
    for col in ["images", "programme_file", "programme_item_no"]:
        try:
            conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass

    # Ensure other assessment columns exist
    for col in ["observation", "interpretation", "feedback_competence", "feedback_agency", "feedback_challenge", "ontology_nodes", "images"]:
        try:
            conn.execute(f"ALTER TABLE assessments ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    return conn


def safe_slug(value):
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    return value[:54] or "performance"


def new_id(title, performer):
    base = f"{safe_slug(performer)}_{safe_slug(title)}"
    conn = connect()
    candidate, n = base, 2
    while conn.execute("SELECT 1 FROM sessions WHERE id = ?", (candidate,)).fetchone():
        candidate, n = f"{base}_{n}", n + 1
    conn.close()
    return candidate


def create_session(values):
    title = str(values.get("title", "")).strip()
    performer = str(values.get("performer", "")).strip()
    if not title or not performer:
        raise ValueError("Production title and performer/group are required.")
    sid = new_id(title, performer)
    stamp = now()
    domain = str(values.get("domain", "Speech & Drama")).strip()
    if domain not in DOMAINS:
        domain = "Speech & Drama"
    conn = connect()
    conn.execute("""
        INSERT INTO sessions (id, title, performer, category, venue, event_date, adjudicator, 
                             domain, outcome, overall_note, programme_file, programme_item_no, 
                             images, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (sid, title, performer, str(values.get("category", "")).strip(),
          str(values.get("venue", "")).strip(), str(values.get("event_date", "")).strip(),
          str(values.get("adjudicator", "")).strip(), domain, "", "",
          str(values.get("programme_file", "")).strip(),
          str(values.get("programme_item_no", "")).strip(),
          str(values.get("images", "")).strip(),
          stamp, stamp))
    conn.commit()
    conn.close()
    return sid


def get_ai_feedback_prompt(sid, criterion_name):
    session = get_session(sid)
    if not session:
        return None
    
    criterion = next((c for c in session["criteria"] if c["name"] == criterion_name), None)
    assessment = next((a for a in session["assessments"] if a["criterion"] == criterion_name), None)
    
    if not assessment:
        return None

    # Get ontology labels for the selected nodes
    ontology = get_ontology()
    node_labels = []
    if ontology and not ontology.get("error"):
        selected_ids = (assessment.get("ontology_nodes") or "").split(",")
        for node in ontology.get("nodes", []):
            if node["id"] in selected_ids:
                node_labels.append(node["label"])

    prompt = f"""You are a master adjudicator and performance psychologist specializing in {session['domain']}.
Your goal is to transform the adjudicator's raw observations into professional, developmentally supportive feedback following the "NEA Philosophy."

Performer: {session['performer']}
Performance: {session['title']}
Criterion: {criterion_name}
Score: {assessment['score']}/10

Raw Observations: {assessment.get('observation')}
Interpretation: {assessment.get('interpretation')}
Technical Evidence (Ontology): {", ".join(node_labels)}

Instructions:
1. Use the "Evidence -> Interpretation -> Recommendation" structure.
2. Apply "Psychologically Safe" language: avoid identity labels ("You are..."), focus on trainable choices ("The performance showed...").
3. Frame feedback around:
   - Competence: What was controlled and successful?
   - Agency: What specific choice did the performer make that worked?
   - Next Challenge: One specific, actionable developmental step.
4. Use technical vocabulary: {", ".join(criterion.get('vocabulary', []))}
5. Keep it concise but authoritative.

Respond with the drafted feedback in three sections: Competence, Agency, and Next Challenge.
"""
    return prompt


def list_sessions():
    conn = connect()
    rows = conn.execute("""
        SELECT s.*, COUNT(a.id) AS completed_criteria,
               COALESCE(ROUND(AVG(a.score), 1), 0) AS average_score
        FROM sessions s LEFT JOIN assessments a ON a.session_id = s.id
        GROUP BY s.id ORDER BY s.updated_at DESC
    """).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_session(sid):
    conn = connect()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
    if not row:
        conn.close()
        return None
    assessments = conn.execute("SELECT * FROM assessments WHERE session_id = ? ORDER BY id", (sid,)).fetchall()
    conn.close()
    result = dict(row)
    domain = result.get("domain") or "Speech & Drama"
    result["domain"] = domain
    criteria_list = DOMAINS.get(domain, DOMAINS["Speech & Drama"])
    result["assessments"] = [dict(item) for item in assessments]
    
    # Enrich criteria with technical vocabulary and techniques
    result["criteria"] = []
    for c_tuple in criteria_list:
        name, desc, ont = c_tuple[0], c_tuple[1], c_tuple[2]
        vocab = c_tuple[3] if len(c_tuple) > 3 else []
        techs = c_tuple[4] if len(c_tuple) > 4 else []
        result["criteria"].append({
            "name": name, 
            "description": desc, 
            "ontology_domain": ont,
            "vocabulary": vocab,
            "techniques": techs
        })
        
    result["average_score"] = round(sum(item["score"] for item in assessments) / len(assessments), 1) if assessments else 0
    return result


def save_assessment(sid, criterion, score, observation, interpretation, competence, agency, challenge, ontology_nodes="", images=""):
    session = get_session(sid)
    if not session:
        raise ValueError("Adjudication session not found.")
    domain = session.get("domain") or "Speech & Drama"
    allowed = {name for name, _, _ in DOMAINS.get(domain, DOMAINS["Speech & Drama"])}
    if criterion not in allowed:
        raise ValueError(f"Unknown criterion '{criterion}' for domain '{domain}'.")
    score = max(1, min(int(score), 10))
    conn = connect()
    
    # Handle legacy NOT NULL columns if they exist
    cursor = conn.execute("PRAGMA table_info(assessments)")
    cols = [row[1] for row in cursor.fetchall()]
    
    extra_cols = []
    extra_vals = []
    update_vals = ""
    
    if "evidence" in cols:
        extra_cols.append("evidence")
        extra_vals.append(str(observation).strip())
        update_vals += ", evidence=excluded.evidence"
        
    if "next_step" in cols:
        extra_cols.append("next_step")
        extra_vals.append(str(challenge).strip())
        update_vals += ", next_step=excluded.next_step"

    col_names = ["session_id", "criterion", "score", "observation", "interpretation", 
                 "feedback_competence", "feedback_agency", "feedback_challenge", 
                 "ontology_nodes", "images", "updated_at"] + extra_cols
                 
    placeholders = ",".join(["?"] * len(col_names))
    insert_sql = f"INSERT INTO assessments ({','.join(col_names)}) VALUES ({placeholders})"
    
    conn.execute(f"""
        {insert_sql}
        ON CONFLICT(session_id, criterion) DO UPDATE SET 
        score=excluded.score,
        observation=excluded.observation, 
        interpretation=excluded.interpretation,
        feedback_competence=excluded.feedback_competence,
        feedback_agency=excluded.feedback_agency,
        feedback_challenge=excluded.feedback_challenge,
        ontology_nodes=excluded.ontology_nodes,
        images=excluded.images,
        updated_at=excluded.updated_at
        {update_vals}
    """, (sid, criterion, score, str(observation).strip(), str(interpretation).strip(),
          str(competence).strip(), str(agency).strip(), str(challenge).strip(), str(ontology_nodes).strip(), 
          str(images).strip(), now()) + tuple(extra_vals))
    conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now(), sid))
    conn.commit()
    conn.close()


def update_session(sid, values):
    if not get_session(sid):
        raise ValueError("Adjudication session not found.")
    conn = connect()
    conn.execute("UPDATE sessions SET outcome = ?, overall_note = ?, images = ?, updated_at = ? WHERE id = ?",
                 (str(values.get("outcome", "")).strip(), str(values.get("overall_note", "")).strip(), 
                  str(values.get("images", "")).strip(), now(), sid))
    conn.commit()
    conn.close()


def report_markdown(session):
    lines = [
        "# Adjudication report",
        "",
        f"**Production:** {session['title']}",
        f"**Performer / group:** {session['performer']}",
        f"**Category:** {session.get('category') or '[not recorded]'}",
        f"**Venue:** {session.get('venue') or '[not recorded]'}",
        f"**Date:** {session.get('event_date') or '[not recorded]'}",
        f"**Adjudicator:** {session.get('adjudicator') or '[not recorded]'}",
        f"**Domain:** {session.get('domain') or '[not recorded]'}",
        f"**Outcome:** {session.get('outcome') or '[not recorded]'}",
        "",
        "## Overall note",
        session.get("overall_note") or "[No overall note recorded]",
        "",
    ]
    if session.get("images"):
        lines.append("### Session Images")
        for img in session["images"].split("\n"):
            if img.strip():
                lines.append(f"![Image]({img.strip()})")
        lines.append("")

    lines.append("## Criteria")
    for item in session["assessments"]:
        score_val = item['score']
        # Add verbal descriptor for score
        descriptor = ""
        if score_val >= 9: descriptor = " (Outstanding)"
        elif score_val >= 8: descriptor = " (Excellent)"
        elif score_val >= 7: descriptor = " (Commendable)"
        elif score_val >= 6: descriptor = " (Satisfactory)"
        elif score_val >= 5: descriptor = " (Developing)"
        else: descriptor = " (Needs Attention)"
        
        lines.extend([
            f"### {item['criterion']} — {score_val}/10{descriptor}",
            "",
            "#### Analysis",
            f"**Observation:** {item.get('observation') or '[Not recorded]'}",
            f"**Interpretation:** {item.get('interpretation') or '[Not recorded]'}",
            f"**Ontology nodes:** {item.get('ontology_nodes') or '[None selected]'}",
            "",
        ])
        
        if item.get("images"):
            lines.append("#### Criterion Images")
            for img in item["images"].split("\n"):
                if img.strip():
                    lines.append(f"![Criterion Image]({img.strip()})")
            lines.append("")

        lines.extend([
            "#### Developmental feedback",
            f"**Competence:** {item.get('feedback_competence') or '[Not recorded]'}",
            f"**Agency:** {item.get('feedback_agency') or '[Not recorded]'}",
            f"**Next challenge:** {item.get('feedback_challenge') or '[Not recorded]'}",
            ""
        ])
    lines.extend(["---", "Internal working record. Review for accuracy and fairness before sharing."])
    return "\n".join(lines)


def get_ontology():
    if not ONTOLOGY_PATH.exists():
        return {"error": "Ontology file not found."}
    try:
        with ONTOLOGY_PATH.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}


def save_report(sid):
    session = get_session(sid)
    if not session:
        raise ValueError("Adjudication session not found.")
    filename = f"{safe_slug(session['performer'])}_{safe_slug(session['title'])}.md"
    path = REPORTS_DIR / filename
    path.write_text(report_markdown(session), encoding="utf-8")
    return str(path)


def list_programmes():
    if not PROGRAMMES_DIR.exists():
        return []
    
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    today_alt = today.strftime("%d-%m-%Y")
    today_short = today.strftime("%d %b") # e.g., 21 Aug

    def get_sort_key(f):
        name = f.name
        # Prioritize files containing today's date
        is_today = (today_str in name or today_alt in name or today_short in name)
        # Use mtime as secondary sort
        return (not is_today, -f.stat().st_mtime)

    files = sorted(PROGRAMMES_DIR.glob("*.pdf"), key=get_sort_key)
    return [{"name": f.name, "path": str(f), "is_today": (today_str in f.name or today_alt in f.name or today_short in f.name)} for f in files]


def export_all_sessions_csv():
    import csv
    import io
    
    conn = connect()
    # Get all sessions with their assessments
    sessions = conn.execute("SELECT * FROM sessions ORDER BY event_date DESC, created_at DESC").fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    headers = [
        "Session ID", "Title", "Performer", "Category", "Venue", "Event Date", 
        "Adjudicator", "Domain", "Outcome", "Overall Note", "Average Score",
        "Criterion", "Score", "Observation", "Interpretation", 
        "Feedback Competence", "Feedback Agency", "Feedback Challenge", "Ontology Nodes"
    ]
    writer.writerow(headers)
    
    for s_row in sessions:
        sid = s_row["id"]
        assessments = conn.execute("SELECT * FROM assessments WHERE session_id = ?", (sid,)).fetchall()
        
        avg_score = 0
        if assessments:
            avg_score = round(sum(a["score"] for a in assessments) / len(assessments), 2)
        
        # If no assessments, still write one row for the session
        if not assessments:
            writer.writerow([
                s_row["id"], s_row["title"], s_row["performer"], s_row["category"], 
                s_row["venue"], s_row["event_date"], s_row["adjudicator"], 
                s_row["domain"], s_row["outcome"], s_row["overall_note"], avg_score,
                "", "", "", "", "", "", "", ""
            ])
        else:
            for a in assessments:
                writer.writerow([
                    s_row["id"], s_row["title"], s_row["performer"], s_row["category"], 
                    s_row["venue"], s_row["event_date"], s_row["adjudicator"], 
                    s_row["domain"], s_row["outcome"], s_row["overall_note"], avg_score,
                    a["criterion"], a["score"], a["observation"], a["interpretation"],
                    a["feedback_competence"], a["feedback_agency"], a["feedback_challenge"], a["ontology_nodes"]
                ])
                
    conn.close()
    return output.getvalue()


def parse_programme(filename):
    import pdfplumber
    path = PROGRAMMES_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Programme not found: {filename}")
    
    entries = []
    current_venue = ""
    current_date = ""
    
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            # Look for Venue: and Date: in the text
            v_match = re.search(r"Venue:\s*(.*)", text)
            if v_match:
                current_venue = v_match.group(1).strip()
            d_match = re.search(r"Date:\s*(.*)", text)
            if d_match:
                current_date = d_match.group(1).strip()

            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue
                
                headers = [str(h or "").strip() for h in table[0]]
                # Look for a header row if the first row doesn't look like one
                if "Name and Surname" not in headers:
                    for i, row in enumerate(table):
                        if any("Name" in str(cell) and "Surname" in str(cell) for cell in row):
                            headers = [str(h or "").strip() for h in row]
                            table = table[i:]
                            break
                    else:
                        continue # No header found in this table

                for row in table[1:]:
                    if not row or len(row) < len(headers):
                        continue
                    entry = {headers[i]: str(row[i] or "").strip() for i in range(len(headers)) if i < len(row)}
                    # Basic validation: must have at least Name and Item or No
                    name = entry.get("Name and Surname")
                    if name and (entry.get("Item") or entry.get("No")):
                        if name not in ["Name and Surname", "Results", "Tuck Shop Break", "Name and Surname School Grade Time Duration Percentage Symbol Showcase/Gala No Item"]:
                            if not name.startswith("Venue:") and not name.startswith("Date:"):
                                # Inject discovered venue/date if not in the row itself
                                if not entry.get("Venue") and current_venue:
                                    entry["Venue"] = current_venue
                                if not entry.get("Date") and current_date:
                                    entry["Date"] = current_date
                                entries.append(entry)
    return entries
