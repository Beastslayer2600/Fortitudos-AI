# Fortitudo AI Maximization Guide

This guide outlines how to leverage the "Technical Authority" framework to maximize your Financial Advisory practice and the AI workspace.

---

## 1. The "Technical Authority" Workflow
Differentiate yourself from standard advisors by using your AI as a high-precision evidence engine.

### A. The Evidence Pack Strategy
Instead of sending a generic advice summary, generate an **Evidence Pack** using the AI:
1.  **Ingest** the latest product technical guides.
2.  **Generate** an "Evidence Pack" draft for the client.
3.  **Deliver:** Present this to the client as a "Technical Supplement" that maps their needs to specific, cited contract wording. 
    *   *Value:* High-income professionals trust evidence over promises.

### B. High-Precision ROA Drafting
The AI is now configured to create "Technical Rationale" in ROAs:
- Use the **ROA structure** action in the client portal.
- The AI will now leave `[EVIDENCE]` placeholders and suggest specific Liberty guide references.
- **Workflow:** Let the AI draft 70%, and you focus on the 30% that requires your professional judgment and the human connection.
- **Evidence Packs:** Generate these client-facing supplements to build trust through technical transparency.
- **Technical Posts:** Use the AI to transform product nuances into LinkedIn or blog drafts to build your technical brand online.

---

## 2. Maximizing the Local AI Workspace

### A. The "Auto-Sort DropZone" Efficiency
The classification engine has been upgraded for higher precision.
- **Batch Processing:** Drag whole client folders into the DropZone. The AI will identify the client by scanning document content (not just names) and file them by type (FICA, FNA, Quote, etc.).
- **Privacy Assurance:** Mention to clients that "My system automatically files your sensitive documents into an offline, encrypted vault—no cloud storage used."

### B. Technical Search (Live Meetings)
Use `ask.py --show "question"` during or after meetings:
- It retrieves the relevant pages **without** waiting for the LLM to think.
- Use it to find a specific waiting period or exclusion in seconds while you have the client's attention (or immediately after).

---

## 3. Website Maximization
Your website should be the "Storefront of Precision."

### C. Client / practice website mockups (AI)
In the Desk, open a client → **AI draft** → **Website mockup**.

The generator is trained on 2025–2026 advisor landing-page research:
- outcome-focused headline (not job title)
- trust strip with specific signals
- audience + problems + process + method + FAQ + single CTA
- no invented testimonials, AUM, or credentials
- privacy language near contact
- self-contained HTML (open in any browser)

Optional brief field: niche, tone, must-include lines. Training notes live in `docs/website_mockup_training.md`.

CLI: `python website_mockup.py -o preview.html --brief "..."`.

### A. Update the Footer
Ensure the copyright spacing is corrected to build a polished first impression:
- `© 2026 Gert Fourie | Financial Advisor`

### B. The "Privacy-First" Brand
Integrate the copy from `docs\website_copy_draft.md`:
- Highlight your **Offline-Only AI** as a security feature.
- Frame your practice as **"Quantamental"**—combining quantitative technical analysis with fundamental stewardship.

---

## 4. Drama Workspace (Future Roadmap)
Keep this separate but ready for a "Stage 2" launch:
- Adjudication lives in the desk at `/adjudication`; the rubric and parsing code is `backend/drama_store.py`.
- The same "Technical Rigor" applied to Liberty guides can be applied to adjudication rubrics (already started in `performance_psychology_2026.md`).
- When launching, use the subdomain `performance.fortitudostudios.site` to maintain brand clarity.

---

*Fortitudo Studios: Structure for the Disciplined.*
