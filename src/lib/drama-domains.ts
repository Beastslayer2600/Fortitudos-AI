import type { DramaDomain } from "./types.ts";

export type Criterion = {
  name: string;
  description: string;
  ontologyDomain: string | null;
  vocabulary: string[];
  techniques: string[];
};

export const DOMAIN_LIST: DramaDomain[] = [
  "Speech & Drama",
  "Visual Arts",
  "Music",
  "Dance",
  "Choirs / Vir kore",
];

export const DOMAINS: Record<DramaDomain, Criterion[]> = {
  "Speech & Drama": [
    {
      name: "Voice & Speech",
      description: "Vocal control, articulation, resonance and breath support.",
      ontologyDomain: "02",
      vocabulary: [
        "Articulation",
        "Resonance",
        "Projection",
        "Modulation",
        "Diaphragmatic support",
        "Plosives",
        "Fricatives",
        "Tone quality",
      ],
      techniques: [
        "Practice vowel elongation",
        "Use humming to find resonance",
        "Record and listen to breath pauses",
      ],
    },
    {
      name: "Body & Physicality",
      description: "Embodied representation, alignment, and physical control.",
      ontologyDomain: "03",
      vocabulary: [
        "Kinesics",
        "Proxemics",
        "Alignment",
        "Gestural clarity",
        "Centering",
        "Tension release",
        "Muscle memory",
      ],
      techniques: [
        "Mirror work for alignment",
        "Isolate movements in slow motion",
        "Check for unnecessary tension",
      ],
    },
    {
      name: "Space & Composition",
      description: "Use of space, levels, facings, and staging logic.",
      ontologyDomain: "04",
      vocabulary: [
        "Blocking",
        "Upstaging",
        "Focus points",
        "Triangulation",
        "Dynamic levels",
        "Traversing the space",
      ],
      techniques: [
        "Map the stage into grids",
        "Vary height levels for status",
        "Maintain audience sightlines",
      ],
    },
    {
      name: "Character & Action",
      description: "Social-cognitive modeling and behavioral strategy.",
      ontologyDomain: "05",
      vocabulary: [
        "Subtext",
        "Objective",
        "Obstacle",
        "Tactics",
        "Inner monologue",
        "Emotional truth",
        "Motivation",
      ],
      techniques: [
        "Identify the Big Want",
        "List 3 tactics to get what you want",
        "Write a character biography",
      ],
    },
    {
      name: "Interpretation & Meaning",
      description: "Subtext, goal representation, and thematic clarity.",
      ontologyDomain: "06",
      vocabulary: [
        "Theme",
        "Symbolism",
        "Metaphor",
        "Genre consistency",
        "Narrative arc",
        "Climax",
        "Nuance",
      ],
      techniques: [
        "Identify the central question",
        "Vary the tempo to highlight meaning",
        "Find the turn in the piece",
      ],
    },
    {
      name: "Relationship & Ensemble",
      description: "Responsive interaction and interpersonal synchrony.",
      ontologyDomain: "07",
      vocabulary: [
        "Listening",
        "Reactive energy",
        "Ensemble cohesion",
        "Spatial awareness",
        "Give and take",
        "Shared breath",
      ],
      techniques: [
        "Exercises in eye contact",
        "Group breathing exercises",
        "Practice blind ensemble cues",
      ],
    },
    {
      name: "Rhythm & Attention",
      description: "Temporal control and audience engagement.",
      ontologyDomain: "08",
      vocabulary: [
        "Pacing",
        "Pause",
        "Staccato",
        "Legato",
        "Beat",
        "Cadence",
        "Audience connection",
      ],
      techniques: [
        "Count beats for comic timing",
        "Vary sentence length for impact",
        "Hold the silence for tension",
      ],
    },
    {
      name: "Improvisation & Spontaneity",
      description: "Real-time predictive adaptation and presence.",
      ontologyDomain: "09",
      vocabulary: [
        "Accepting the offer",
        "Yes, and...",
        "Active listening",
        "Impulse",
        "Flow state",
        "Risk-taking",
      ],
      techniques: [
        "Practice Yes, and drills",
        "Focus on the partner's eyes",
        "Don't plan the next line",
      ],
    },
    {
      name: "Style & Convention",
      description: "Adherence to theatrical modes and stylistic logic.",
      ontologyDomain: "10",
      vocabulary: [
        "Naturalism",
        "Abstract",
        "Brechtian",
        "Epic",
        "Absurdism",
        "Melodrama",
        "Classical",
      ],
      techniques: [
        "Research the historical period",
        "Identify key stylistic markers",
        "Consistent use of convention",
      ],
    },
  ],
  "Visual Arts": [
    {
      name: "Context & Brief",
      description: "Understanding of the task, prompt or thematic framework.",
      ontologyDomain: "13",
      vocabulary: [
        "Conceptual framing",
        "Contextual research",
        "Brief adherence",
        "Thematic depth",
      ],
      techniques: [
        "Brainstorm lateral associations",
        "Document the ideation process",
        "Review the original prompt",
      ],
    },
    {
      name: "Visual Language",
      description: "Use of formal elements like line, shape, color, and texture.",
      ontologyDomain: "14",
      vocabulary: [
        "Chiaroscuro",
        "Sfumato",
        "Color theory",
        "Tonal range",
        "Mark-making",
        "Line weight",
      ],
      techniques: [
        "Practice value scales",
        "Limit palette to study harmony",
        "Experiment with textured tools",
      ],
    },
    {
      name: "Composition & Design",
      description:
        "Application of design principles such as balance, rhythm, and emphasis.",
      ontologyDomain: "15",
      vocabulary: [
        "Rule of thirds",
        "Negative space",
        "Golden ratio",
        "Visual weight",
        "Symmetry",
        "Focal point",
      ],
      techniques: [
        "Thumbnail sketches for layout",
        "Check balance with a mirror",
        "Simplify the main shapes",
      ],
    },
    {
      name: "Drawing & Sketching",
      description: "Technical control, observation, and mark-making in dry media.",
      ontologyDomain: "16",
      vocabulary: [
        "Hatching",
        "Cross-hatching",
        "Contour line",
        "Gesture drawing",
        "Perspective",
        "Proportion",
      ],
      techniques: [
        "Daily life studies",
        "Blind contour exercises",
        "Use a viewfinder for framing",
      ],
    },
    {
      name: "Painting & Surface",
      description: "Handling of wet media, surface quality, and tonal modelling.",
      ontologyDomain: "17",
      vocabulary: [
        "Impasto",
        "Glazing",
        "Scumbling",
        "Wash",
        "Underpainting",
        "Palette knife work",
      ],
      techniques: [
        "Layer thin to thick",
        "Mix colors on the palette, not the canvas",
        "Study brushstroke direction",
      ],
    },
    {
      name: "Photography",
      description:
        "Technical control of exposure, framing, and digital/analog process.",
      ontologyDomain: "18",
      vocabulary: [
        "Aperture",
        "Shutter speed",
        "ISO",
        "Depth of field",
        "Bokeh",
        "Rule of thirds",
        "Dynamic range",
      ],
      techniques: [
        "Manual mode practice",
        "Study lighting at golden hour",
        "Review histogram for exposure",
      ],
    },
    {
      name: "Concept & Narrative",
      description: "Depth of meaning, subtext, and visual storytelling.",
      ontologyDomain: "19",
      vocabulary: [
        "Metaphor",
        "Allegory",
        "Narrative arc",
        "Semiotic meaning",
        "Visual metaphor",
      ],
      techniques: [
        "Write a concept statement",
        "Critique the symbols used",
        "Seek multiple layers of meaning",
      ],
    },
    {
      name: "Process & Research",
      description:
        "Evidence of experimentation, research, and conceptual development.",
      ontologyDomain: "20",
      vocabulary: [
        "Iterative design",
        "Visual journal",
        "Material exploration",
        "Comparative study",
      ],
      techniques: [
        "Annotate your sketchbook",
        "Document failed experiments",
        "Keep a material log",
      ],
    },
    {
      name: "Materiality & Craft",
      description: "Choice and handling of materials, finish, and presentation.",
      ontologyDomain: "21",
      vocabulary: [
        "Medium specificity",
        "Craftsmanship",
        "Mounting",
        "Finish",
        "Structural integrity",
      ],
      techniques: [
        "Test material compatibility",
        "Clean edges and presentation",
        "Consider the display environment",
      ],
    },
    {
      name: "Sculpture & 3D",
      description:
        "Mass, volume, structural integrity, and use of three-dimensional space.",
      ontologyDomain: "22",
      vocabulary: [
        "Armature",
        "Maquette",
        "Positive/Negative space",
        "Subtractive/Additive",
        "Kinetic",
      ],
      techniques: [
        "Build a strong internal structure",
        "Walk around the piece constantly",
        "Consider shadows and light",
      ],
    },
    {
      name: "Perception & Impact",
      description:
        "Audience engagement, visual psychology, and communicative impact.",
      ontologyDomain: "23",
      vocabulary: [
        "Aesthetic arrest",
        "Cognitive dissonance",
        "Emotive response",
        "Visual hierarchy",
      ],
      techniques: [
        "Get feedback from observers",
        "Simplify the visual hook",
        "Test readability from a distance",
      ],
    },
    {
      name: "Ethics & Validity",
      description: "Adherence to ethical standards and interpretive validity.",
      ontologyDomain: "24",
      vocabulary: [
        "Originality",
        "Appropriation",
        "Integrity",
        "Representation",
        "Sustainability",
      ],
      techniques: [
        "Check source material",
        "Cite influences clearly",
        "Ensure original contribution",
      ],
    },
  ],
  Music: [
    {
      name: "Technique",
      description: "Intonation, tone quality, articulation, and technical fluency.",
      ontologyDomain: null,
      vocabulary: [
        "Legato",
        "Staccato",
        "Vibrato",
        "Embouchure",
        "Fingering",
        "Breath control",
        "Double tonguing",
      ],
      techniques: [
        "Slow practice with metronome",
        "Long tone exercises",
        "Scales and arpeggios",
      ],
    },
    {
      name: "Interpretation",
      description: "Phrasing, dynamic control, and musical narrative.",
      ontologyDomain: null,
      vocabulary: [
        "Rubato",
        "Crescendo",
        "Diminuendo",
        "Agogic accent",
        "Musical arc",
        "Phrasing",
      ],
      techniques: [
        "Sing the melody to find phrasing",
        "Mark the dynamic climax",
        "Research historical performance practice",
      ],
    },
    {
      name: "Performance Psychology",
      description: "Attentional focus, anxiety regulation, and stage presence.",
      ontologyDomain: null,
      vocabulary: [
        "Flow state",
        "Centering",
        "Mental rehearsal",
        "Visualisation",
        "Performance anxiety",
      ],
      techniques: [
        "Practice mindful breathing",
        "Perform for a small mock audience",
        "Positive self-talk",
      ],
    },
    {
      name: "Rhythm & Pacing",
      description: "Temporal precision, ensemble synchrony, and rhythmic vitality.",
      ontologyDomain: null,
      vocabulary: [
        "Syncopation",
        "Polyrhythm",
        "Subdivision",
        "Tempo rubato",
        "Groove",
        "Pulse",
      ],
      techniques: [
        "Clap complex rhythms",
        "Use a metronome for subdivision",
        "Foot tapping for pulse",
      ],
    },
    {
      name: "Communication",
      description:
        "Audience engagement, emotional authenticity, and shared intentionality.",
      ontologyDomain: null,
      vocabulary: [
        "Expressive projection",
        "Eye contact",
        "Shared intent",
        "Stage persona",
      ],
      techniques: [
        "Record and watch yourself",
        "Focus on the story of the music",
        "Imagine the performance space",
      ],
    },
    {
      name: "Relationship & Ensemble",
      description: "Interpersonal synchrony, balance, and group communication.",
      ontologyDomain: null,
      vocabulary: [
        "Listening",
        "Balance",
        "Intonation",
        "Eye contact",
        "Cues",
        "Unified attack",
      ],
      techniques: [
        "Rehearse without the conductor",
        "Record group rehearsals",
        "Focus on the bass line/foundation",
      ],
    },
    {
      name: "Developmental Craft",
      description: "Integration of technical skill with artistic purpose.",
      ontologyDomain: null,
      vocabulary: [
        "Repertoire choice",
        "Artistic growth",
        "Technical maturity",
        "Style mastery",
      ],
      techniques: [
        "Listen to diverse recordings",
        "Analyze the score structure",
        "Seek feedback from peers",
      ],
    },
  ],
  Dance: [
    {
      name: "Technique",
      description: "Body alignment, strength, flexibility, and technical precision.",
      ontologyDomain: null,
      vocabulary: [
        "Turnout",
        "Extension",
        "Core stability",
        "Plie",
        "Tendu",
        "Alignment",
        "Isolation",
      ],
      techniques: [
        "Focus on floor work for core",
        "Consistent barre work",
        "Stretch after every session",
      ],
    },
    {
      name: "Musicality",
      description:
        "Rhythmic awareness, phrasing, and relationship between movement and sound.",
      ontologyDomain: null,
      vocabulary: [
        "On the beat",
        "Syncopation",
        "Dynamics of movement",
        "Phrasing",
        "Accent",
      ],
      techniques: [
        "Listen to the music without moving",
        "Clap the accents",
        "Vary movement quality with tempo",
      ],
    },
    {
      name: "Performance Psychology",
      description: "Spatial command, focus, flow, and anxiety management.",
      ontologyDomain: null,
      vocabulary: ["Projection", "Focus", "Spatial awareness", "Confidence", "Flow"],
      techniques: [
        "Practice spot-fixing in turns",
        "Visualization of the routine",
        "Controlled breathing",
      ],
    },
    {
      name: "Artistry & Expression",
      description: "Emotional truth, narrative clarity, and causal coherence.",
      ontologyDomain: null,
      vocabulary: [
        "Face expression",
        "Emotional range",
        "Narrative arc",
        "Characterization",
      ],
      techniques: [
        "Use a mirror to check facial cues",
        "Understand the why behind movement",
        "Watch yourself on video",
      ],
    },
    {
      name: "Composition & Line",
      description: "Use of space, geometry of form, and choreographic understanding.",
      ontologyDomain: null,
      vocabulary: [
        "Arabesque",
        "Attitude",
        "Shapes",
        "Symmetry",
        "Levels",
        "Floor patterns",
      ],
      techniques: [
        "Film from different angles",
        "Simplify transitions",
        "Check geometric clarity",
      ],
    },
    {
      name: "Relationship & Ensemble",
      description:
        "Synchrony, spatial awareness between dancers, and ensemble impact.",
      ontologyDomain: null,
      vocabulary: [
        "Unison",
        "Canon",
        "Partnering",
        "Contact improvisation",
        "Trust",
        "Spatial proximity",
      ],
      techniques: [
        "Mirroring exercises",
        "Practice weight-sharing",
        "Ensemble breathing",
      ],
    },
    {
      name: "Engagement",
      description: "Stage presence, projection, and communicative impact.",
      ontologyDomain: null,
      vocabulary: [
        "Audience connection",
        "Energy levels",
        "Energy flow",
        "Stage presence",
      ],
      techniques: [
        "Perform to a far point in the room",
        "Imagine the stage lights",
        "Focus on big energy",
      ],
    },
  ],
  "Choirs / Vir kore": [
    {
      name: "Vocal Quality",
      description: "Vocal control, blend, balance, and tonal warmth.",
      ontologyDomain: null,
      vocabulary: [
        "Homogeneity",
        "Vowel matching",
        "Resonance",
        "Choral tone",
        "Balance",
      ],
      techniques: [
        "Practice section tuning",
        "Vowel unification drills",
        "Listen for the overtones",
      ],
    },
    {
      name: "Intonation & Musicality",
      description: "Pitch accuracy, harmonic detail, and active listening.",
      ontologyDomain: null,
      vocabulary: ["Pitch center", "Just intonation", "Harmonic clarity", "Listening"],
      techniques: [
        "Practice acappella tuning",
        "Staggered breathing for sustain",
        "Solfege training",
      ],
    },
    {
      name: "Dynamics & Expression",
      description: "Musical contrast, character, and expressive phrasing.",
      ontologyDomain: null,
      vocabulary: [
        "Piano/Forte",
        "Nuance",
        "Expressive text",
        "Crescendo",
        "Diminuendo",
      ],
      techniques: [
        "Exaggerate dynamics in rehearsal",
        "Discuss the poem/text meaning",
        "Vary vocal color",
      ],
    },
    {
      name: "Diction & Articulation",
      description: "Coordination of consonants and clarity of text.",
      ontologyDomain: null,
      vocabulary: [
        "Consonants",
        "Vowels",
        "Diphthongs",
        "Textual clarity",
        "Articulation",
      ],
      techniques: [
        "Tongue twisters for speed",
        "Practice text without pitch",
        "Check final consonants",
      ],
    },
    {
      name: "Ensemble & Discipline",
      description: "Response to conductor, coordination, and stage presence.",
      ontologyDomain: null,
      vocabulary: [
        "Attack and release",
        "Conductor focus",
        "Deportment",
        "Focus",
        "Unified stance",
      ],
      techniques: [
        "Practice silent attacks",
        "Unified turning of pages",
        "Stand in performance posture",
      ],
    },
    {
      name: "Encouraging Closing Remarks",
      description: "Summarizing the performance and providing future direction.",
      ontologyDomain: null,
      vocabulary: ["Summary", "Positive reinforcement", "Next steps", "Growth mindset"],
      techniques: [
        "Find one specific highlight",
        "Encourage group identity",
        "Propose one goal for next year",
      ],
    },
  ],
};

export function scoreDescriptor(score: number) {
  if (score >= 9) return "Outstanding";
  if (score >= 8) return "Excellent";
  if (score >= 7) return "Commendable";
  if (score >= 6) return "Satisfactory";
  if (score >= 5) return "Developing";
  return "Needs attention";
}
