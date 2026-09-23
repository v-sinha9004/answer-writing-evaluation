# Autonomous UPSC Mains Answer Evaluation & Feedback Engine

An autonomous, multi-stage evaluation engine designed to assess UPSC Mains handwritten answer copies, generate grounded scores, and provide actionable feedback.

The system is built on a modular architecture designed to support all General Studies papers (**GS-1 to GS-4**), with development starting on **GS-1 as our initial working pilot** to keep the initial build lean, fast, and simple.

---

## Sequential Implementation Roadmap

We will build the system step by step, keeping things simple and functional at each stage.

```
[Milestone 1: Core Engine & GS-1 Pilot]
  ├── Step 1: Core Evaluation Rubric & Schemas
  ├── Step 2: Benchmark Test Data (GS-1)
  ├── Step 3: Input Intake & Extraction
  ├── Step 4: Multi-Step State Machine
  ├── Step 5: Report & Feedback Generation
  └── Step 6: Testing & Calibration
                │
                ▼
[Milestone 2: Generalization & Advanced Features]
  ├── Step 7: Expand to GS-2, GS-3, GS-4
  ├── Step 8: Visual Handwriting Annotations
  ├── Step 9: Observability & Tracing
  └── Step 10: CI/CD & Deployment
```

---

### Milestone 1: Core Engine (Piloting on GS-1)
*Goal: Build a working end-to-end evaluation pipeline using GS-1 (History, Geography, Society) as our first baseline.*

#### Step 1: Core Evaluation Rubric & Schemas
- [ ] Define the general evaluation criteria for UPSC Mains:
  - Question demand fulfillment and directive adherence (`Discuss`, `Critically Examine`, `Evaluate`, etc.).
  - Structure and presentation (Intro, Body structuring, Conclusion).
  - Subject depth and dimensional coverage (starting with GS-1 domains).
  - Scoring scales for 10-markers (150 words) and 15-markers (250 words).
- [ ] Define clean data schemas for:
  - Input: Question text, paper type, marks, candidate answer.
  - Intermediate state: Parsed sub-parts, detected structure, evaluated dimensions.
  - Final Output: Scores, rubric breakdown, strengths, gaps, and specific value additions.

#### Step 2: Benchmark Sample Dataset
- [ ] Collect 3-4 representative GS-1 questions (History, Culture, Geography, Society).
- [ ] Prepare test answers of varying quality (Good, Average, Poor) to use for evaluation benchmarks.

#### Step 3: Input Intake & Answer Extraction
- [ ] Accept candidate submission (scanned image / PDF).
- [ ] Extract written text and separate key document segments (Question, Intro, Body, Conclusion).

#### Step 4: Multi-Step State Machine
- [ ] **Node 1: Question & Directive Parser**
  - Break question into core sub-demands and identify analytical posture required by the directive.
- [ ] **Node 2: Structural & Format Inspector**
  - Verify introduction, subheadings, bullet points, legibility/flow, and conclusion.
- [ ] **Node 3: Knowledge & Dimension Validator**
  - Check presence of key subject dimensions, facts, examples, and relevant conceptual references.
- [ ] **Node 4: Rubric-Based Scorer & Self-Check**
  - Award dimensional marks and total score based on the rubric.
  - Verify score consistency (ensuring score matches the feedback and tone).

#### Step 5: Feedback & Report Generation
- [ ] Generate structured evaluation summary:
  - Overall marks and parameter-wise score breakdown.
  - Strengths and what was done well.
  - Missing dimensions and critical gaps.
  - High-impact value additions (recommended examples, diagrams, or points).

#### Step 6: End-to-End Testing & Calibration
- [ ] Test the pipeline on our sample answers.
- [ ] Calibrate scoring thresholds to ensure realistic marks (e.g., 5.5-6.5/10 for top-tier answers).

---

### Milestone 2: Generalization & Advanced Capabilities
*Goal: Broaden paper support across the UPSC syllabus and add production features.*

#### Step 7: Expand to GS-2, GS-3, and GS-4
- [ ] Add **GS-2** domain logic (Polity, Constitution, Governance, International Relations - Articles, Case laws, Committee reports).
- [ ] Add **GS-3** domain logic (Economy, Environment, Science & Tech, Internal Security - Schemes, Economic data, Reports).
- [ ] Add **GS-4** domain logic (Ethics, Integrity, Aptitude - Philosophers, Ethical frameworks, Case studies).

#### Step 8: Visual Feedback Overlay
- [ ] Map evaluation feedback to spatial coordinates on the original handwritten pages.
- [ ] Generate visually marked PDF copies with color-coded callouts and margin annotations.

#### Step 9: Observability, Traceability & Logging
- [ ] Log multi-node execution traces and reasoning steps for auditability and transparency.

#### Step 10: CI/CD & Deployment
- [ ] Automated testing pipeline (unit & integration tests).
- [ ] Continuous Integration / Continuous Deployment workflows.
- [ ] Containerization and hosting.
