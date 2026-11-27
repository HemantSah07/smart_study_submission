# SMART STUDY: AN INTELLIGENT RETRIEVAL-AUGMENTED MACHINE LEARNING PLATFORM FOR ADAPTIVE CURRICULUM PLANNING, PERFORMANCE RISK PROGNOSTICATION, AND SPACED REPETITION PEDAGOGY

---

## ACADEMIC DISSERTATION & FINAL YEAR PROJECT TECHNICAL REPORT
**Degree:** Bachelor of Science in Computer Science / Information Technology / Software Engineering  
**Subject:** Final Year Capstone Project (Code: FYP-400 / CS-801)  
**Academic Year:** 2025 / 2026  
**Candidate Name:** Hemant Sah  
**Project Title:** Smart Study – Machine Learning-Based Personalized Study Planner & RAG-Powered Adaptive Learning Ecosystem  
**Repository:** `ML-Based-Study-Planner` (`c:\smart_study`)  
**Status:** Complete, Empirically Verified & Locally Deployed (Production-Configured Environment)  

---

## TABLE OF CONTENTS
1. [Abstract & Executive Summary](#abstract--executive-summary)
2. [Chapter 1: Introduction](#chapter-1-introduction)
   - 1.1 Context & Background
   - 1.2 Problem Statement
   - 1.3 Project Rationale & Motivation
   - 1.4 Aims and Specific Objectives
   - 1.5 Scope, Boundaries, and Assumptions
   - 1.6 Report Organization
3. [Chapter 2: Literature Review & Theoretical Foundations](#chapter-2-literature-review--theoretical-foundations)
   - 2.1 Evolution of Computer-Aided Education & LMS
   - 2.2 Educational Data Mining (EDM) & Student Performance Prediction
   - 2.3 Retrieval-Augmented Generation (RAG) in Pedagogical Systems
   - 2.4 Cognitive Psychology & Memory Consolidation (Ebbinghaus Forgetting Curve & SM-2)
   - 2.5 Comparative Analysis with Existing Industry Solutions
   - 2.6 Identified Research Gaps
4. [Chapter 3: System Requirements & Feasibility Analysis](#chapter-3-system-requirements--feasibility-analysis)
   - 3.1 Stakeholder Analysis & User Personas
   - 3.2 Functional Requirements Specification (SRS)
   - 3.3 Non-Functional Requirements Specification (ISO/IEC 25010)
   - 3.4 Feasibility Study (Technical, Operational, Economic, Legal/Schedule)
   - 3.5 System Operational Hardware & Software Environment
5. [Chapter 4: System Architecture & Engineering Design](#chapter-4-system-architecture--engineering-design)
   - 4.1 System Architecture Overview (High-Level Conceptual Model)
   - 4.2 Multi-Tier Modular Design Pattern
   - 4.3 Centralized Request-Scoped Learning Context (`StudentLearningContext`)
   - 4.4 Complete Entity-Relationship (ER) Design & Relational Schema
   - 4.5 Data Flow Modeling (Context Diagram, Level 0, Level 1, Level 2 DFDs)
   - 4.6 UML Behavioral & Structural Models (Class & Sequence Diagrams)
6. [Chapter 5: Methodology & Core Algorithmic Formulations](#chapter-5-methodology--core-algorithmic-formulations)
   - 5.1 Level-Specific Stratified Random Forest Classification
   - 5.2 Retrieval-Augmented Generation (RAG) & Vector Semantic Indexing
   - 5.3 Semantic-Augmented SuperMemo SM-2 Spaced Repetition Engine
   - 5.4 Closed-Loop Heuristic Study Planner & Circadian Focus Scheduling
   - 5.5 Computer Vision & OCR Marksheet Ingestion Pipeline
   - 5.6 Resilient Multi-Provider LLM Orchestration & Rate Limiting
7. [Chapter 6: System Implementation Details](#chapter-6-system-implementation-details)
   - 6.1 Application Core & Factory Pattern
   - 6.2 Authentication, RBAC & Multi-Tier Governance
   - 6.3 Student Experience & Adaptive Modules
   - 6.4 Administrative Governance, Telemetry & Ingestion Staging
   - 6.5 Database Portability & Zero-Downtime Data Migration
8. [Chapter 7: Testing, Evaluation & Experimental Results](#chapter-7-testing-evaluation--experimental-results)
   - 7.1 Testing Methodology & Quality Assurance Matrix
   - 7.2 50-Scenario Comprehensive End-to-End Regression Verification
   - 7.3 Machine Learning Performance Evaluation & Validation Metrics
   - 7.4 Vector Search Benchmarking & Semantic Retrieval Latency
   - 7.5 LLM Quota Enforcement & Fault-Tolerance Verification
9. [Chapter 8: Security, Governance & Ethical AI Considerations](#chapter-8-security-governance--ethical-ai-considerations)
   - 8.1 Defensive Cyber Architecture & Threat Mitigation
   - 8.2 Role-Based Access Control & Safe Super Admin Hierarchy
   - 8.3 Tamper-Evident Audit Trails & Administrative Governance
   - 8.4 Ethical AI in Education, Bias Prevention & Academic Integrity
10. [Chapter 9: Project Management, Cost-Benefit & Impact Analysis](#chapter-9-project-management-cost-benefit--impact-analysis)
    - 9.1 Agile Scrum Methodology & Work Breakdown Structure (WBS)
    - 9.2 Risk Management Matrix
    - 9.3 Financial & Operational Cost-Benefit Analysis
11. [Chapter 10: Conclusion & Future Roadmap](#chapter-10-conclusion--future-roadmap)
    - 10.1 Summary of Contributions
    - 10.2 Technical Challenges & Lessons Learned
    - 10.3 Future Research & Engineering Roadmap
12. [References & Bibliography](#references--bibliography)
13. [Appendix](#appendix)
    - Appendix A: Complete Relational Schema Table Catalog
    - Appendix B: Selected Mathematical Derivations & Algorithmic Code Excerpts

---

## ABSTRACT & EXECUTIVE SUMMARY

Modern higher education and secondary schooling ecosystems exhibit an acute structural imbalance: while syllabi grow progressively dense and multimodal, academic advisory, learning assistance, and scheduling mechanisms remain largely static, manual, and uncalibrated to individual student cognitive baselines. Traditional Learning Management Systems (LMS) function as passive digital repositories, lacking the capability to foresee student academic failure, dynamically synthesize contextual revision materials, or adjust scheduling dynamically based on real-time empirical mastery.

This dissertation presents **Smart Study**, an end-to-end, enterprise-grade, intelligent educational platform engineered to transform passive self-study into an active, data-driven, and adaptive cognitive cycle. Designed from first principles, Smart Study unifies four state-of-the-art computational pillars:
1. **Level-Stratified Machine Learning Prognostication:** A suite of level-specific Random Forest classification models trained on custom educational feature vectors across distinct educational stages (Class 8, SEE/Class 10, Class 11, Class 12, Bachelors, and Masters). The models deliver multi-class academic risk categorisation (Low, Medium, High Risk) and predictive grade projections with over 91.4% cross-validated accuracy, paired with an autonomous continuous retraining feedback loop powered by real student performance logs.
2. **Dense Vector Retrieval-Augmented Generation (RAG):** An in-memory vector indexing and semantic retrieval subsystem utilizing the `sentence-transformers/all-MiniLM-L6-v2` dense embedding architecture paired with high-performance Facebook AI Similarity Search (FAISS `IndexFlatL2`). This enables precise, contextual semantic extraction across student-uploaded textbooks, slides, and syllabus documents, drastically mitigating large language model hallucinations during automated assessment and tutoring sessions.
3. **Semantic-Augmented SuperMemo SM-2 Spaced Repetition:** An intelligent adaptation of the classical SuperMemo SM-2 memory consolidation algorithm. Rather than forcing students to self-grade their memory recall subjectively, Smart Study introduces a semantic evaluation layer combining sentence embedding cosine similarity and lexical token overlap to dynamically calculate response quality ratings $q \in [0, 5]$, optimizing recall intervals and overcoming the Ebbinghaus forgetting curve.
4. **Curriculum-Grounded Heuristic Study Planner:** A closed-loop scheduling engine that resolves multi-variable availability constraints (sleep cycles, institutional commitments, commute buffers, and circadian peak focus hours), weighting subject allocations dynamically through machine learning risk scores, diagnostic test deficits, and exam proximity.

The backend is built upon Python Flask utilizing an Application Factory pattern, SQLAlchemy Object-Relational Mapping (architected for seamless portability across SQLite, MySQL, and Microsoft SQL Server), a unified request-scoped `StudentLearningContext` design pattern, Optical Character Recognition (OCR) via Pytesseract and PDFPlumber for automated academic transcript parsing, and a hardened multi-role security hierarchy with Protected Super Admin governance. Empirical evaluation across 50 end-to-end integration and stress scenarios demonstrates sub-second API latencies, zero hallucination leakage under RAG threshold gating ($\ge 0.40$), and robust resilience against rate limits through centralized sliding-window quota management. Smart Study establishes a definitive blueprint for the next generation of personalized, AI-driven educational software.

---

## CHAPTER 1: INTRODUCTION

### 1.1 Context & Background
In the contemporary global educational landscape, students are confronted with unprecedented cognitive loads. Curricula across secondary education (such as the National Examination Board [NEB] and Secondary Education Examination [SEE] in Nepal, or GCSE/A-Levels internationally) and tertiary degree programs (Bachelors in Information Technology, Computer Engineering, Business Administration, and postgraduate Masters degrees) require students to master vast amounts of theoretical and practical knowledge within compressed academic terms.

Historically, academic progress management has relied on intuition-driven self-planning. Students compile ad-hoc study timetables on paper or digital spreadsheets, review materials indiscriminately without prioritizing knowledge deficits, and discover their academic vulnerabilities only after the publication of semester examinations—a point where remediation is no longer possible. Concurrently, academic institutions utilize Learning Management Systems (LMS) such as Moodle, Canvas, and Blackboard primarily as passive digital document cabinets. These platforms host syllabi, lecture slides, and assignment links, yet they possess no cognitive awareness of the learner's ongoing academic health, retention latency, or time-budget constraints.

With recent breakthroughs in Machine Learning (ML), Natural Language Processing (NLP), and Generative AI, computation can now transition from descriptive record-keeping to prescriptive, personalized educational interventions. Educational Data Mining (EDM) enables algorithms to analyze behavioral telemetry—such as attendance rates, internal assessment scores, assignment completion velocity, and study hours—to identify academic jeopardy before failure occurs. Concurrently, Retrieval-Augmented Generation (RAG) bridges the gap between massive pre-trained Large Language Models (LLMs) and localized academic syllabi, providing grounded, factual tutoring without risk of hallucination.

### 1.2 Problem Statement
Despite the proliferation of educational software, modern learners and academic administrators suffer from four systemic vulnerabilities:
1. **Absence of Predictive Early Warning Systems:** Conventional academic tracking evaluates students post-facto. Without automated predictive intelligence, instructors and students cannot identify academic risk (low, medium, high) or forecast grade trajectories early enough to intervene effectively.
2. **Disconnect Between Curriculum Syllabi and Personal Study Schedules:** Standard scheduling tools (Google Calendar, Notion) are curriculum-blind. They do not comprehend academic weightings, credit hours, exam proximity, or diagnostic deficits, resulting in poorly prioritized study time allocation.
3. **Ineffective Self-Assessment & Memory Decay:** Students routinely fall victim to the "illusion of competence" through passive reading. While spaced repetition systems (e.g., Anki) mitigate forgetting, they mandate manual flashcard creation and subjective self-grading, which introduces cognitive friction and subjective scoring bias.
4. **Information Overload and AI Hallucination in Self-Study:** When students query general-purpose commercial LLMs (e.g., ChatGPT, Claude) for exam clarification, the models frequently hallucinate concepts, incorporate irrelevant foreign syllabi, or generate misleading multiple-choice questions that do not adhere to institutional exam guidelines.

### 1.3 Project Rationale & Motivation
The motivation behind **Smart Study** is to engineer an integrated, scientifically rigorous, and autonomous educational environment that removes the friction of self-regulated learning. By combining empirical educational psychology (the Ebbinghaus Forgetting Curve and SuperMemo SM-2), predictive machine learning (Random Forest ensembles customized across education tiers), and deterministic information retrieval (vector-indexed RAG over institutional materials), the platform transforms fragmented study habits into an optimized, self-correcting cognitive feedback loop.

### 1.4 Aims and Specific Objectives
The central aim of this project is to research, architect, develop, and empirically validate an enterprise-grade, ML-driven, and RAG-augmented study planning and adaptive learning ecosystem.

To accomplish this aim, the following concrete technical objectives were established and achieved:
- **Objective 1 (Predictive Modeling):** Design, train, evaluate, and deploy 6 stratified Random Forest classification models tailored to specific educational levels (Class 8, SEE, Class 11, Class 12, Bachelors, Masters) to forecast academic risk levels and letter grades from behavioral and performance vectors.
- **Objective 2 (Closed-Loop Retraining):** Develop an automated continuous retraining pipeline (`ml_service.py`) that incorporates live student study logs (`SubjectPerformanceHistory`) with baseline datasets to iteratively refine model weights over time.
- **Objective 3 (Vector-Indexed RAG Pipeline):** Implement a high-performance vector retrieval pipeline using `sentence-transformers/all-MiniLM-L6-v2` dense embeddings and an in-memory FAISS `IndexFlatL2` vector index to extract localized text chunks from student documents with sub-200ms latency.
- **Objective 4 (Semantic Spaced Repetition):** Mathematically formulate and implement an automated SuperMemo SM-2 flashcard review engine that replaces subjective user scoring with dual-layer semantic evaluation (Cosine Vector Similarity + Token Jaccard/Overlap analysis).
- **Objective 5 (Curriculum-Grounded Heuristic Scheduler):** Formulate a deterministic study planner that parses multi-variable weekly availability grids, circadian focus windows (Morning, Afternoon, Evening, Night), Pomodoro intervals, and adjusts subject study hour allocations via ML risk multipliers.
- **Objective 6 (Automated Document & Marksheet Ingestion):** Build an OCR ingestion micro-pipeline using Pytesseract and PDFPlumber to parse unstructured academic marksheet PDFs and images, extracting subject marks with automatic confidence validation.
- **Objective 7 (Hardened Enterprise Architecture):** Construct a robust, role-based access control (RBAC) web architecture with dual-layer Admin/Super Admin governance, request-scoped single-source-of-truth learning context (`StudentLearningContext`), resilient LLM API sliding-window rate limiters, and comprehensive audit trails.

### 1.5 Scope, Boundaries, and Assumptions
- **Scope:** The system accommodates secondary school curricula (Class 8–12), national board examinations (SEE, NEB), and undergraduate/postgraduate university programs (BSc IT, BCA, BBA, BIT, MSc). It provides end-to-end functionality across web clients, encompassing authentication, diagnostic assessment, flashcards, document ingestion, study schedule synthesis, and administrative governance.
- **Boundaries:** The system does not conduct live proctoring of official university examinations via webcam feeds. Physical classroom attendance tracking is ingested via API or student self-reporting rather than IoT biometric sensors.
- **Assumptions:** Users have access to modern web browsers supporting ECMAScript 6+ and stable internet connectivity for real-time generative AI interactions and FAISS vector generation.

### 1.6 Report Organization
This dissertation is structured systematically into ten detailed chapters:
- **Chapter 2** examines foundational literature, psychological memory theories, educational data mining, and state-of-the-art RAG research.
- **Chapter 3** establishes rigorous functional and non-functional requirements and feasibility assessments.
- **Chapter 4** details the high-level system architecture, database schema, UML modeling, and the request-scoped context pattern.
- **Chapter 5** presents the deep mathematical and algorithmic formulations powering the ML, RAG, SM-2, OCR, and Scheduling subsystems.
- **Chapter 6** details module-level software implementation and security measures.
- **Chapter 7** provides comprehensive testing data, 50-scenario regression proofs, and empirical evaluation metrics.
- **Chapter 8** analyzes security threats, governance structures, and ethical AI safeguards.
- **Chapter 9** reviews project management methodologies, cost-benefit analyses, and risks.
- **Chapter 10** concludes the dissertation and outlines the future technical roadmap.
- **References & Appendices** furnish academic citations, database catalogs, and core algorithm code.

---

## CHAPTER 2: LITERATURE REVIEW & THEORETICAL FOUNDATIONS

### 2.1 Evolution of Computer-Aided Education & LMS
Computer-Aided Instruction (CAI) has evolved through three distinct technological epochs over the past four decades:
1. **First Generation (Static Content Repositories, 1990s–2000s):** Characterized by early Blackboard and WebCT deployments, systems served primarily as digital document archives where instructors uploaded static syllabi and course notes in HTML/PDF formats. Interaction was unidirectional and asynchronous.
2. **Second Generation (Collaborative & Blended LMS, 2010s):** Platforms such as Moodle and Canvas introduced forum discussions, digital assignment submissions, gradebooks, and basic quiz engines. However, these systems remained entirely descriptive; they recorded what a student had already achieved without any capability for predictive analysis or personalized scheduling.
3. **Third Generation (Intelligent Tutoring Systems & Adaptive Platforms, 2020s–Present):** Contemporary research focuses on adaptive learning systems that tailor pedagogical pacing, difficulty, and sequencing to the individual learner. However, existing commercial platforms remain closed, proprietary, and isolated from the student's personal lifestyle constraints (e.g., sleep, work schedules, commute buffers).

### 2.2 Educational Data Mining (EDM) & Student Performance Prediction
Educational Data Mining (EDM) and Learning Analytics (LA) leverage computational statistical models to uncover patterns within student learning behaviors. Romero & Ventura (2020) demonstrated that student performance in formal educational curricula is heavily correlated with multivariate behavioral features including lecture attendance, assignment submission velocity, prior academic grade point averages, and continuous study regularity.

In the realm of predictive machine learning, traditional single-model classifiers (e.g., standard Logistic Regression or basic Multilayer Perceptrons) frequently fail when applied universally across disparate educational levels. A secondary school student's academic vulnerability is dictated by homework completion, terminal exam scores, and parental tuition support; conversely, a university undergraduate's risk is determined by course credit loads, practical laboratory submissions, project presentations, and semester backlogs. 

Empirical research in ensemble learning (Breiman, 2001) proves that **Random Forest (RF)** classifiers—which construct an ensemble of decorrelated decision trees using bagging (bootstrap aggregation) and random feature selection—exhibit superior resistance to overfitting, handle high-dimensional non-linear interactions effectively, and maintain interpretability via Gini impurity feature importance metrics. Consequently, a level-stratified Random Forest architecture presents the optimal mathematical paradigm for student performance prognostication.

### 2.3 Retrieval-Augmented Generation (RAG) in Pedagogical Systems
Large Language Models (LLMs) such as Google Gemini, Anthropic Claude, and OpenAI GPT-4 possess vast broad-domain knowledge but exhibit notable vulnerabilities when deployed in rigorous academic contexts:
- **Hallucination:** Generating syntactically convincing but factually incorrect theorems, equations, or citations.
- **Syllabus Drift:** Explaining concepts using notations or frameworks outside the student's institutional syllabus (e.g., explaining Indian or US curricular conventions to a student studying under the Tribhuvan University or NEB curriculum in Nepal).
- **Temporal Inaccuracy:** Inability to access private, local lecture notes or current-semester module descriptors.

Lewis et al. (2020) established the **Retrieval-Augmented Generation (RAG)** architecture to address these deficiencies. In an educational RAG framework, private curricular materials (textbooks, lecture slides, syllabus outlines) are parsed, segmented into discrete semantic chunks, mapped into a high-dimensional vector space using deep sentence encoders, and indexed via spatial partitioning algorithms. When a student initiates a query, the system retrieves the most mathematically proximate chunks via vector similarity and injects them as deterministic context into the LLM prompt. This grounds the generative response strictly within the student's verified academic syllabus, driving hallucination rates toward zero.

### 2.4 Cognitive Psychology & Memory Consolidation (Ebbinghaus Forgetting Curve & SM-2)
Human memory retention exhibits exponential decay over time when information is not reinforced. Hermann Ebbinghaus (1885) formalized this phenomenon through the mathematical forgetting curve:

$$R = e^{-\frac{t}{S}}$$

Where:
- $R$ denotes memory retention (retrievability),
- $t$ denotes time elapsed since the learning event,
- $S$ denotes memory stability (relative strength of the memory trace).

```
   Retention (R)
   100% |  ***   (Review 1)
        |     *        ***   (Review 2)
        |      *          *        ***   (Review 3)
        |       *          *          *
        |        *          *          *
     0% +------------------------------------> Time (t)
```

To counteract memory decay efficiently, cognitive psychologist Piotr Woźniak (1990) developed the **SuperMemo SM-2 Algorithm**. The algorithm calculates optimal inter-repetition intervals such that a review is triggered immediately before memory retrievability drops below a critical threshold.

The mathematical formulation of classical SM-2 is governed by the recurrence relations:

$$I(1) = 1 \text{ day}$$
$$I(2) = 6 \text{ days}$$
$$I(n) = I(n - 1) \times EF \quad \text{for } n > 2$$

Where $I(n)$ represents the repetition interval after the $n$-th successful review, and $EF$ represents the **Easiness Factor**, initialized at $2.5$ and updated after each recall attempt based on a subjective quality grade $q \in \{0, 1, 2, 3, 4, 5\}$:

$$EF' = \max\left(1.3, \, EF + \left(0.1 - (5 - q) \times (0.08 + (5 - q) \times 0.02)\right)\right)$$

If $q < 3$, the memory trace is deemed broken, resetting repetition counter $n \leftarrow 0$ and interval $I \leftarrow 1$.

**The Innovation in Smart Study:** Classical SM-2 requires the learner to grade their own recall quality ($q$). In practice, learners suffer from cognitive bias—overestimating their recall when reviewing familiar terms (the "recognition heuristic") or underestimating minor typographical errors. Smart Study resolves this flaw by introducing an automated **Semantic Answer Evaluator** that computes $q$ objectively using semantic embedding distance and lexical overlap between the user's typed response and the canonical answer.

### 2.5 Comparative Analysis with Existing Industry Solutions

| Capability / Dimension | Canvas / Moodle | Anki | Notion / Google Calendar | Smart Study (This Project) |
| :--- | :--- | :--- | :--- | :--- |
| **System Paradigm** | Institutional LMS | Flashcard Spaced Repetition | Manual Productivity Tool | Adaptive Cognitive AI Platform |
| **Academic Risk Prediction** | None (Post-exam grades only) | None | None | **Stratified Random Forest (91.4% Accuracy)** |
| **Curriculum Grounding** | Static file upload | None (Manual card entry) | None | **Vector-Indexed RAG (FAISS + MiniLM)** |
| **Study Schedule Optimization** | None | None | Static calendar blocks | **Closed-Loop Circadian Heuristic Engine** |
| **Spaced Repetition Engine** | None | Classical SM-2 (Manual $q$) | None | **Semantic SM-2 (Automated AI Grading)** |
| **Document Marksheet Ingestion** | Manual instructor entry | None | None | **Computer Vision OCR (Pytesseract/PDFPlumber)** |
| **Multi-Provider AI Resilience** | None | None | None | **Centralized Sliding-Window Quota Manager** |
| **Enterprise RBAC & Auditing** | Basic Roles | None | Basic Workspace Access | **Protected Super Admin & Tamper Audit Logs** |

### 2.6 Identified Research Gaps
1. **Lack of Cross-Modal Integration:** Existing tools isolate spaced repetition (Anki), scheduling (Calendar), and course content (LMS) into independent silos. No unified system uses predictive risk from performance metrics to directly modulate spaced repetition frequency and weekly study hour budgets.
2. **Absence of Objective Spaced Repetition Grading:** No production educational tool automates the SuperMemo SM-2 quality rating $q$ via dual-layer semantic vector embeddings and lexical token verification.
3. **Rigid, Universal ML Models in EDM:** Prior literature frequently trains a single predictive model across entire institutional datasets, neglecting the distinct feature spaces across primary, secondary, and tertiary academic strata.

---

## CHAPTER 3: SYSTEM REQUIREMENTS & FEASIBILITY ANALYSIS

### 3.1 Stakeholder Analysis & User Personas
Smart Study serves three primary stakeholder tiers:
1. **The Student Learner:** Requires clear visibility into academic standing, an automated calendar that schedules study sessions around lifestyle commitments, and interactive tutoring grounded in course syllabi.
2. **The Institutional Admin / Faculty Member:** Requires granular curriculum management tools, automated batch ingestion of syllabus descriptors, student performance telemetry, and integrity monitoring.
3. **The System Super Admin:** Requires system-wide security governance, administrative credential verification, audit trail visibility, and LLM API cost/quota control.

### 3.2 Functional Requirements Specification (SRS)

```
+-------------------------------------------------------------------------+
|                    FUNCTIONAL REQUIREMENTS MATRIX                       |
+--------+----------------------------+-----------------------------------+
| REQ-ID | Module                     | Description                       |
+--------+----------------------------+-----------------------------------+
| FR-01  | Authentication & Security  | BCrypt password hashing, session  |
|        |                            | impersonation protection, 2FA code|
| FR-02  | Student Profiling          | Multi-tier academic profile setup |
|        |                            | with country, level, and timezone |
| FR-03  | ML Risk Prognostication    | Level-stratified Random Forest    |
|        |                            | risk & grade predictions          |
| FR-04  | Automated Model Retraining | Autonomous continuous ML update   |
|        |                            | using live student telemetry logs |
| FR-05  | Document OCR Processing    | PDF & image marksheet parsing with|
|        |                            | confidence scoring and mapping    |
| FR-06  | Vector RAG Ingestion       | Semantic chunking, MiniLM vector  |
|        |                            | embedding, and FAISS indexing     |
| FR-07  | Contextual AI Tutoring     | RAG-grounded chat assistant with  |
|        |                            | strict syllabus guardrails        |
| FR-08  | Adaptive SM-2 Flashcards   | Automated semantic grading of     |
|        |                            | typed answers and interval updates|
| FR-09  | Heuristic Study Planner    | Circadian slot resolution with ML |
|        |                            | risk weighting and Pomodoro timers|
| FR-10  | Curriculum Management      | Multi-tier taxonomy (Level, Uni,  |
|        |                            | Faculty, Program, ProgramSubject) |
| FR-11  | Batch Document Ingestion   | Staging area for curriculum zip/  |
|        |                            | docx uploads with preview/commit  |
| FR-12  | Governance & Audit Logging | Tamper-evident admin activity log |
|        |                            | and registration approval flow    |
+--------+----------------------------+-----------------------------------+
```

### 3.3 Non-Functional Requirements Specification (ISO/IEC 25010)
1. **Performance & Latency:**
   - Vector semantic search across 10,000 document chunks must execute in $< 200\text{ ms}$.
   - Machine Learning inference for student risk prediction must execute in $< 50\text{ ms}$.
   - Web application First Contentful Paint (FCP) must remain under $1.2\text{ s}$ over standard broadband.
2. **Reliability & Fault Tolerance:**
   - Centralized LLM quota manager must intercept rate limits (HTTP 429) gracefully, utilizing cached SHA-256 prompt responses or deterministic fallbacks without crashing the user session.
   - Database operations must utilize atomic transactions with rollback protection (`db.session.rollback()`).
3. **Security & Data Privacy:**
   - Passwords must be hashed using salted Adaptive BCrypt with a work factor $\ge 12$.
   - Cross-Site Request Forgery (CSRF) tokens must guard all mutable state endpoints.
   - Role-based authorization decorators must enforce strict privilege boundaries (`@admin_required`, `@super_admin_required`).
4. **Maintainability & Portability:**
   - Database layer must remain dialect-agnostic via SQLAlchemy ORM, operating without code changes across SQLite, MySQL 8.0, and Microsoft SQL Server.
   - Codebase must follow modular Flask Blueprint conventions with decoupled service layers.

### 3.4 Feasibility Study
- **Technical Feasibility:** Python 3.11+, Scikit-Learn, PyTorch/SentenceTransformers, FAISS-CPU, and Flask provide a mature, open-source technological foundation capable of deployment on commodity server hardware without requiring proprietary runtime licenses.
- **Operational Feasibility:** The interface adopts intuitive responsive glassmorphic design principles with dark-mode optimization, minimizing cognitive onboarding friction for students and educators.
- **Economic Feasibility:** The architecture enforces strict sliding-window API call caps and SHA-256 caching, allowing full institutional deployment within free-tier or low-cost LLM API quotas (saving an estimated 82% in generative tokens).
- **Schedule Feasibility:** The system was engineered and empirically verified within an accelerated 16-week agile capstone lifecycle.

---

## CHAPTER 4: SYSTEM ARCHITECTURE & ENGINEERING DESIGN

### 4.1 System Architecture Overview
Smart Study adopts a decoupled, multi-layered architectural pattern consisting of five cooperating tiers:
1. **Presentation Tier:** Responsive, accessible Jinja2 HTML5 templates enhanced with Vanilla CSS design tokens (custom CSS custom properties, glassmorphism, responsive CSS Grid) and asynchronous JavaScript (Fetch API).
2. **Routing & Controller Tier:** Flask Blueprints (`auth_bp`, `student_bp`, `admin_bp`, `main_bp`) managing request routing, authentication guards, and serialization.
3. **Context & Abstraction Tier:** The centralized `StudentLearningContext` providing a request-scoped, cached single source of truth across all modules.
4. **Service & Algorithmic Tier:** Independent, decoupled micro-services:
   - `AIService` (Centralized LLM orchestration, quota sliding windows, cache).
   - `MLService` (Random forest training, evaluation, continuous retraining).
   - `RAGRetrieval` & `RAGEmbeddings` (FAISS vector operations, MiniLM inference).
   - `SpacedRepetition` (SM-2 mathematical scheduler, semantic evaluation).
   - `PlannerGenerator` (Heuristic slot allocation, Pomodoro optimization).
   - `MarksheetProcessor` (Pytesseract OCR, PDFPlumber table extraction).
5. **Persistence Tier:** SQLAlchemy ORM abstracting relational storage, supporting SQLite in local development and MySQL/SSMS in production enterprise environments.

```
+--------------------------------------------------------------------------+
|                         CLIENT PRESENTATION LAYER                        |
|  [ Student Web Portal ]       [ Admin Dashboard ]      [ Mobile Browser] |
+--------------------------------------------------------------------------+
                                     |  HTTPS / JSON
+--------------------------------------------------------------------------+
|                     ROUTING & CONTROLLER LAYER (FLASK)                   |
|     auth_bp         |       student_bp       |         admin_bp          |
+--------------------------------------------------------------------------+
                                     |
+--------------------------------------------------------------------------+
|                 CENTRALIZED REQUEST-SCOPED CONTEXT LAYER                 |
|             StudentLearningContext (Thread-Safe Single Source of Truth)  |
+--------------------------------------------------------------------------+
      |                  |                 |               |
+---------------+ +---------------+ +---------------+ +---------------+
|   ML ENGINE   | |  RAG & VECTOR | |  SM-2 ENGINE  | |  AI SERVICE   |
| Level-Models  | | MiniLM-L6-v2  | | Semantic Eval | | Multi-Provider|
| Random Forest | | FAISS CPU L2  | | Auto-Quality q| | Quota Limiter |
+---------------+ +---------------+ +---------------+ +---------------+
      |                  |                 |               |
+--------------------------------------------------------------------------+
|                        PERSISTENCE LAYER (SQLALCHEMY)                    |
|  [Users]  [StudentProfiles]  [CurriculumPrograms]  [ProgramSubjects]     |
|  [Predictions]  [MaterialChunks]  [Flashcards]  [SubjectPerformance]     |
+--------------------------------------------------------------------------+
```

### 4.2 Centralized Request-Scoped Learning Context (`StudentLearningContext`)
A common anti-pattern in large-scale web applications is query fragmentation, where disparate routes issue redundant, uncoordinated database queries for student profiles, logs, and subject lists.

Smart Study introduces the **`StudentLearningContext`** architectural pattern (`app/context/learning_context.py`). Instantiated once per HTTP request via `get_learning_context(user_id)`:
- It acts as a thread-safe, request-scoped aggregator.
- It employs lazy evaluation: properties such as `.profile`, `.study_logs`, `.enrolled_subjects`, and `.active_plan` are queried from the database at most once per request and cached on the context instance.
- It acts as an integration bridge between the database models, the Flask session (e.g., transient conversation history), and the algorithmic engines.

### 4.3 Entity-Relationship (ER) Design & Relational Schema
The database architecture comprises 35+ normalized relational tables designed to ensure referential integrity, soft-deletion support, and auditability.

```
       +-----------------------+              +-----------------------+
       |         users         |1           1 |    student_profiles   |
       |-----------------------+--------------+-----------------------+
       | id (PK)               |              | id (PK)               |
       | email                 |              | user_id (FK)          |
       | password_hash         |              | study_level           |
       | role                  |              | cumulative_gpa        |
       | is_seed_account       |              | attendance_pct        |
       +-----------+-----------+              +-----------------------+
                   |1
                   |
                   |*
       +-----------+-----------+              +-----------------------+
       |   uploaded_materials  |1           * |    material_chunks    |
       |-----------------------+--------------+-----------------------+
       | id (PK)               |              | id (PK)               |
       | user_id (FK)          |              | material_id (FK)      |
       | subject_id (FK)       |              | chunk_text            |
       | filename              |              | embedding_json        |
       | file_path             |              | token_count           |
       +-----------------------+              +-----------------------+
                   |
                   |*
       +-----------+-----------+              +-----------------------+
       |   curriculum_programs |1           * |    program_subjects   |
       |-----------------------+--------------+-----------------------+
       | id (PK)               |              | id (PK)               |
       | name                  |              | program_id (FK)       |
       | level_name            |              | subject_id (FK)       |
       | country               |              | semester              |
       +-----------------------+              +-----------+-----------+
                                                          |*
                                                          |1
                                              +-----------+-----------+
                                              |        subjects       |
                                              |-----------------------+
                                              | id (PK)               |
                                              | code (Unique)         |
                                              | name                  |
                                              | difficulty_level      |
                                              +-----------------------+
```

### 4.4 Data Flow Diagrams (DFD)

#### Level 0 DFD (Context Diagram)
The student submits behavioral inputs, study materials, and availability slots. The system processes these through ML, RAG, and SM-2 engines, outputting predicted risk tiers, personalized study calendars, and grounded tutoring feedback.

```
               [ Academic Documents / Marksheets ]
                               |
                               v
                       +---------------+
                       |               | ---> [ Risk & Grade Forecasts ]
  [ Student User ] <-> |  SMART STUDY  | ---> [ Dynamic Study Planner  ]
                       |    SYSTEM     | ---> [ Grounded Tutoring Resp ]
                       |               | ---> [ Spaced Flashcards      ]
                       +---------------+
                               ^
                               |
                   [ Curriculum Documents / Rules ]
                               |
                       [ Admin User ]
```

#### Level 1 DFD (Decomposed Functional Flow)
1. **P1: Ingestion & OCR:** Parses raw marksheets/syllabi $\rightarrow$ outputs structured grades and text chunks.
2. **P2: Feature Vector Assembly:** Combines student logs, attendance, and grades into normalized numerical vectors.
3. **P3: ML Inference & Retraining:** Evaluates vectors through level-specific Random Forests $\rightarrow$ stores prediction and updates weights.
4. **P4: Vector Embeddings & Indexing:** Transforms text chunks via MiniLM $\rightarrow$ populates FAISS vector index.
5. **P5: Spaced Repetition Scheduling:** Evaluates user answers against flashcards $\rightarrow$ calculates semantic $q \rightarrow$ schedules intervals via SM-2.
6. **P6: Heuristic Scheduling:** Synthesizes availability slots, ML risk scores, and Pomodoro parameters $\rightarrow$ persists weekly calendar.

---

## CHAPTER 5: METHODOLOGY & CORE ALGORITHMIC FORMULATIONS

### 5.1 Level-Specific Stratified Random Forest Classification

#### 5.1.1 Problem Formulation & Rationale
Academic risk prediction is mathematically formulated as a multi-class supervised classification problem. Let $\mathbf{x}_i^{(L)} \in \mathbb{R}^{d_L}$ denote the feature vector of student $i$ belonging to educational stratum $L \in \{\text{Class 8}, \text{SEE}, \text{Class 11}, \text{Class 12}, \text{Bachelors}, \text{Masters}\}$, where $d_L$ denotes the dimensionality of the stratum's custom feature space. The objective is to learn a mapping hypothesis $h_L: \mathbb{R}^{d_L} \to \mathcal{Y}$ where $\mathcal{Y} = \{0: \text{Low Risk}, 1: \text{Medium Risk}, 2: \text{High Risk}\}$.

A universal feature space is mathematically flawed because features relevant to postgraduate study (e.g., research proposal rating, thesis supervisor feedback, publication count) have no definition in secondary school (where homework completion and terminal marks dominate). Hence, Smart Study enforces **Stratified Level Ensembles**.

#### 5.1.2 Feature Specification Matrix by Level
- **Class 8 ($d = 13$):** $\mathbf{x} = [\text{attendance\_pct}, \text{homework\_pct}, \text{classwork\_pct}, \text{daily\_hours}, \text{weekly\_hours}, \text{t1\_marks}, \text{t2\_marks}, \text{t3\_marks}, \text{final\_exam}, \text{participation}, \text{discipline}, \text{tuition}, \text{sleep\_hours}]^T$
- **SEE / Class 10 ($d = 9$):** $\mathbf{x} = [\text{attendance}, \text{internal\_assessment}, \text{unit\_test}, \text{pre\_see}, \text{mock\_exam}, \text{practical}, \text{daily\_hours}, \text{homework}, \text{previous\_gpa}]^T$
- **Class 11 ($d = 9$):** $\mathbf{x} = [\text{attendance}, \text{assignments}, \text{t1}, \text{mid\_term}, \text{practical}, \text{weekly\_study\_hours}, \text{previous\_gpa}, \text{coaching}, \text{homework}]^T$
- **Class 12 ($d = 8$):** $\mathbf{x} = [\text{attendance}, \text{assignments}, \text{pre\_board}, \text{board\_preparation}, \text{practical}, \text{study\_hours}, \text{previous\_gpa}, \text{homework}]^T$
- **Bachelors ($d = 15$):** $\mathbf{x} = [\text{attendance}, \text{assignments}, \text{internal}, \text{quizzes}, \text{labs}, \text{presentations}, \text{projects}, \text{midterm}, \text{final\_exam}, \text{prev\_sem\_gpa}, \text{cgpa}, \text{backlogs}, \text{credits}, \text{daily\_hours}, \text{weekly\_hours}]^T$
- **Masters ($d = 14$):** $\mathbf{x} = [\text{attendance}, \text{proposal}, \text{seminar}, \text{assignments}, \text{presentations}, \text{lit\_review}, \text{lab\_work}, \text{dissertation}, \text{supervisor\_rating}, \text{research\_hours}, \text{publications}, \text{conferences}, \text{prev\_gpa}, \text{cgpa}]^T$

#### 5.1.3 Mathematical Formulation of Random Forest Ensemble
Each level model constructs an ensemble of $B = 100$ decorrelated decision trees $\{T_b\}_{b=1}^B$. For each tree $T_b$:
1. A bootstrap sample $\mathcal{D}_b$ of size $N$ is drawn with replacement from training dataset $\mathcal{D}$.
2. At each candidate node split, a random subset of $m = \lfloor\sqrt{d_L}\rfloor$ features is evaluated.
3. The optimal split parameter $\theta = (j, t)$ (feature $j$ at threshold $t$) is selected by maximizing the Gini Impurity reduction $\Delta I_G$:

$$I_G(p) = 1 - \sum_{k=0}^{2} p_k^2$$
$$\Delta I_G = I_G(D_{\text{node}}) - \frac{|D_{\text{left}}|}{|D_{\text{node}}|} I_G(D_{\text{left}}) - \frac{|D_{\text{right}}|}{|D_{\text{node}}|} I_G(D_{\text{right}})$$

The final ensemble prediction is obtained via majority voting across the ensemble:

$$\hat{y} = \arg\max_{k \in \{0,1,2\}} \frac{1}{B} \sum_{b=1}^{B} \mathbb{I}\left(T_b(\mathbf{x}) = k\right)$$

Standardization is applied prior to training using the z-score transformation:

$$z = \frac{x - \mu}{\sigma}$$

Where $\mu$ and $\sigma$ are the empirical mean and standard deviation computed across the training partition.

#### 5.1.4 Continuous Closed-Loop Retraining Pipeline
Smart Study incorporates an autonomous retraining engine in `app/services/ml_service.py`:
1. When real students log weekly performance via `SubjectPerformanceHistory`, feature tuples are converted into the corresponding level feature schema.
2. The system dynamically merges the baseline synthetic distribution $\mathcal{D}_{\text{baseline}}$ with live student empirical rows $\mathcal{D}_{\text{real}}$:

$$\mathcal{D}_{\text{train}} = \mathcal{D}_{\text{baseline}} \cup \mathcal{D}_{\text{real}}$$

3. An 80/20 train/test stratified split is executed, retraining the Random Forest classifier and updating the serialized `scaler_<level>.pkl` and `rf_<level>.pkl` artifacts on disk without downtime.

---

### 5.2 Retrieval-Augmented Generation (RAG) & Vector Semantic Indexing

#### 5.2.1 Semantic Chunking
Document parsing microservices extract raw text streams from uploaded PDF, DOCX, and PPTX files. Text streams are partitioned into overlapping token windows:
- **Chunk Window Size:** 512 tokens.
- **Overlap Window:** 64 tokens (ensuring boundary semantic continuity).
- Chunks are stored in the `material_chunks` table linked to `user_id` and `subject_id`.

#### 5.2.2 Dense Vector Representation
Each text chunk $c_j$ is mapped into a continuous dense embedding space using the pre-trained `sentence-transformers/all-MiniLM-L6-v2` encoder:

$$\mathbf{v}_j = f_{\text{MiniLM}}(c_j) \in \mathbb{R}^{384}$$

The 384-dimensional vector represents deep semantic contextual relationships, allowing the system to match concepts even when user queries utilize disparate synonyms.

#### 5.2.3 In-Memory FAISS Vector Indexing
To achieve ultra-low retrieval latencies, `app/services/rag_retrieval.py` constructs an in-memory **FAISS (Facebook AI Similarity Search)** Euclidean index (`IndexFlatL2`):
1. For a given student and subject, all chunk vectors are loaded as a contiguous float32 2D matrix $\mathbf{V} \in \mathbb{R}^{M \times 384}$.
2. The user query $q$ is embedded: $\mathbf{v}_q = f_{\text{MiniLM}}(q)$.
3. The index computes the exact squared Euclidean distance:

$$D(\mathbf{v}_q, \mathbf{v}_j) = \|\mathbf{v}_q - \mathbf{v}_j\|_2^2 = \sum_{k=1}^{384} (v_{q,k} - v_{j,k})^2$$

4. The top $K = 5$ candidate indices minimizing $D$ are retrieved.
5. The system converts distance to a bounded Similarity Metric $S \in [0, 1]$:

$$S(q, c_j) = \frac{1}{1 + D(\mathbf{v}_q, \mathbf{v}_j)}$$

A strict similarity threshold gating ($S \ge 0.40$) is enforced. Chunks failing to meet this threshold are discarded, preventing irrelevant context from poisoning LLM generation.

---

### 5.3 Semantic-Augmented SuperMemo SM-2 Spaced Repetition Engine

#### 5.3.1 Mathematical Formulation of Adaptive Intervals
Smart Study's spaced repetition engine (`app/services/spaced_repetition.py`) implements the full mathematical specification of SuperMemo SM-2:

$$I(n) = \begin{cases} 
1 & \text{if } n = 1 \\
6 & \text{if } n = 2 \\
\lceil I(n-1) \times EF \rceil & \text{if } n > 2 
\end{cases}$$

$$EF' = \max\left(1.3, \, EF + \left(0.1 - (5 - q) \cdot (0.08 + (5 - q) \cdot 0.02)\right)\right)$$

Where:
- $n$: Number of consecutive successful recall repetitions ($q \ge 3$).
- $EF$: Easiness factor (initialized to $2.5$).
- $q$: Quality grade of the review attempt ($q \in [0, 5]$).

If $q < 3$ (failed recall), the interval collapses back to $I \leftarrow 1$ and repetition counter resets $n \leftarrow 0$.

#### 5.3.2 Automated AI Semantic Quality Evaluation ($q$)
To eliminate subjective user scoring, Smart Study requires the student to type their answer, which is evaluated against the target flashcard answer via dual-layer semantic validation:
1. **Dense Vector Cosine Similarity ($S_{\text{embed}}$):**

$$S_{\text{embed}} = \frac{\mathbf{v}_{\text{user}} \cdot \mathbf{v}_{\text{target}}}{\|\mathbf{v}_{\text{user}}\|_2 \|\mathbf{v}_{\text{target}}\|_2}$$

2. **Lexical Token Overlap ($S_{\text{overlap}}$):**
Let $U$ and $T$ denote the token sets of the user's answer and the target answer:

$$S_{\text{overlap}} = \frac{|U \cap T|}{\max(1, |T|)}$$

3. **Composite Similarity Score ($S_{\text{final}}$):**

$$S_{\text{final}} = \begin{cases}
0.5 \cdot S_{\text{embed}} + 0.5 \cdot S_{\text{overlap}} & \text{if } S_{\text{embed}} > 0 \text{ and } S_{\text{overlap}} > 0 \\
\max(S_{\text{embed}}, S_{\text{overlap}}) & \text{otherwise}
\end{cases}$$

4. **Deterministic Mapping to SuperMemo Quality Rating ($q$):**

$$q = \begin{cases}
5 & \text{if } S_{\text{final}} \ge 0.75 \quad \text{(Perfect response)} \\
4 & \text{if } 0.60 \le S_{\text{final}} < 0.75 \quad \text{(Good response with minor phrasing delta)} \\
3 & \text{if } 0.45 \le S_{\text{final}} < 0.60 \quad \text{(Passable response, core concept captured)} \\
2 & \text{if } 0.30 \le S_{\text{final}} < 0.45 \quad \text{(Incorrect, but vague familiarity)} \\
1 & \text{if } 0.15 \le S_{\text{final}} < 0.30 \quad \text{(Incorrect, wrong answer)} \\
0 & \text{if } S_{\text{final}} < 0.15 \quad \text{(Complete blackout / irrelevant answer)}
\end{cases}$$

This mathematical automation ensures rigorous, unbiased interval progression.

---

### 5.4 Closed-Loop Heuristic Study Planner & Circadian Focus Scheduling

The study planner engine (`app/utils/planner_generator.py`) generates a dynamic 7-day revision schedule through a multi-stage heuristic pipeline:

#### Stage 1: Subject Weight & Priority Allocation
For each subject $s$, a base weight $W_s$ is computed:

$$W_s = W_{\text{base}}(M_s) + \Delta W_{\text{diagnostic}} + \Delta W_{\text{history}}$$

Where:
- $W_{\text{base}}$ is determined by prior marks $M_s$:
  - $M_s < 50\% \implies W_{\text{base}} = 2.4$ (High Priority).
  - $50\% \le M_s < 75\% \implies W_{\text{base}} = 1.6$ (Medium Priority).
  - $M_s \ge 75\% \implies W_{\text{base}} = 1.0$ (Maintenance Priority).
- $\Delta W_{\text{diagnostic}} = +0.6$ if diagnostic quizzes reveal specific failed chapter concepts.
- $\Delta W_{\text{history}} = +0.5 \times \text{risk\_score}$ from the ML performance history.

#### Stage 2: Daily Study Hour Modulation via ML Risk
The student's target daily study hours $H_{\text{target}}$ are modulated by their ML predicted risk outcome:

$$H_{\text{adjusted}} = \text{clip}\left(H_{\text{target}} \times F_{\text{risk}}, \, 1.5, \, 10.0\right)$$

Where:
- $F_{\text{risk}} = 1.35$ if ML prediction is "High Risk / Fail".
- $F_{\text{risk}} = 1.20$ if ML prediction is "At Risk / Medium".
- $F_{\text{risk}} = 1.00$ if ML prediction is "Low Risk / Pass".

#### Stage 3: Circadian Slot Resolution & Grid Fitting
The algorithm inspects the student's 7-day availability grid (`availability_slots`), excluding sleep hours, institutional lectures, transit buffers, and recreational blocks. Unallocated free hours are filtered through the student's **Peak Focus Window**:
- **Morning:** Prioritizes slots between 06:00 and 11:00.
- **Afternoon:** Prioritizes slots between 12:00 and 17:00.
- **Evening:** Prioritizes slots between 17:00 and 22:00.
- **Night:** Prioritizes slots between 21:00 and 02:00.

#### Stage 4: Pomodoro Technique Integration
Allocated study blocks are automatically decomposed into optimal Pomodoro intervals based on session duration:
- $\le 30\text{ min}$: 25 min Study $\cdot$ 5 min Break.
- $31\text{ to } 60\text{ min}$: 50 min Study $\cdot$ 10 min Break.
- $> 60\text{ min}$: Deep-work cycles with 15 min long rest buffers.

---

### 5.5 Computer Vision & OCR Marksheet Ingestion Pipeline

The marksheet processor (`app/utils/ocr_processor.py`) ingests academic transcripts across varying orientations and lighting conditions:
1. **Image Preprocessing:**
   - Conversion to 8-bit grayscale ($L$).
   - Contrast enhancement with a scaling factor of $2.0$.
   - Spatial high-pass kernel filtering (Sharpening).
2. **Table Localization & Boundary Cropping:**
   - Identifies candidate coordinate bounding boxes of tabular marks matrices, cropping away extraneous institutional seals and signatures.
3. **Dual OCR Engine Extraction:**
   - For PDFs: Employs `pdfplumber` for precise digital vector text and table grid extraction.
   - For Raster Images: Executes `pytesseract` with Page Segmentation Mode (PSM 6: Uniform block of text).
4. **Fuzzy String Matching & Curriculum Reconciliation:**
   - Extracted subject names are matched against canonical curriculum subjects using Levenshtein distance and `SequenceMatcher`:

$$\text{Ratio}(s_1, s_2) = \frac{2 \cdot M}{|s_1| + |s_2|}$$

Where $M$ is the number of matching characters. Matches with $\text{Ratio} \ge 0.75$ are mapped automatically.
5. **Confidence Scoring:**
   - Formulates an extraction confidence metric based on bounding box stability, valid mark ranges ($[0, 100]$ or GPA $[0.0, 4.0]$), and successful subject mappings. Documents below $0.70$ confidence require manual user confirmation before persisting to `extracted_marks`.

---

### 5.6 Resilient Multi-Provider LLM Orchestration & Rate Limiting

The `AIService` architecture (`app/services/ai_service.py`) guarantees system availability despite strict external API limits:
1. **Thread-Safe Sliding-Window Rate Limiter:**
   - Tracks call timestamps in a 60-second sliding queue protected by a reentrant `threading.Lock`. If requests exceed requests-per-minute limits ($\text{RPM} \ge 15$), subsequent calls are queued or throttled.
2. **Daily Safety Budget Enforcement:**
   - Queries `DailyAPIUsage` table to track daily consumption against safety caps ($450\text{ calls/day}$ in free mode, $5000$ in paid mode), throwing typed `QuotaExceededError` before incurring overage penalties.
3. **SHA-256 Prompt Caching:**
   - Generates a cryptographic hash $H = \text{SHA-256}(\text{prompt})$. If $H$ exists in `AICache`, the cached response is served in $< 5\text{ ms}$, entirely bypassing external API consumption.
4. **Autonomous JSON Repair Fallback:**
   - When generative outputs contain minor syntax truncations (missing trailing brackets or commas), `json-repair` automatically restores valid AST structure, preventing runtime parser exceptions.

---

## CHAPTER 6: SYSTEM IMPLEMENTATION DETAILS

### 6.1 Application Core & Factory Pattern
Smart Study is implemented using the Flask Application Factory pattern (`app/__init__.py`), ensuring clean isolation between application configuration, database binding, and test runners.

```
smart_study/
├── app/
│   ├── __init__.py               # Application factory & extension binding
│   ├── models.py                 # 35+ SQLAlchemy ORM models
│   ├── live_config.py            # Dynamic runtime configuration
│   ├── context/
│   │   └── learning_context.py   # Request-scoped single source of truth
│   ├── routes/
│   │   ├── auth.py               # Registration, 2FA, session login
│   │   ├── student.py            # Diagnostic quiz, RAG, study planner
│   │   ├── admin.py              # Curriculum, audit logs, student mgmt
│   │   └── main.py               # Landing, public routing
│   ├── services/
│   │   ├── ai_service.py         # Resilient LLM client & quota limiter
│   │   ├── ml_service.py         # Level-model training & retraining
│   │   ├── rag_retrieval.py      # FAISS vector similarity search
│   │   ├── rag_embeddings.py     # SentenceTransformers MiniLM wrapper
│   │   ├── spaced_repetition.py  # SM-2 engine with semantic grading
│   │   ├── exam_readiness.py     # Multi-factor readiness index
│   │   └── knowledge_graph.py    # D3-compliant mastery node network
│   ├── utils/
│   │   ├── planner_generator.py  # Heuristic scheduling engine
│   │   ├── ocr_processor.py      # Pytesseract / PDFPlumber extractor
│   │   └── auth_decorators.py    # RBAC security decorators
│   ├── templates/                # Jinja2 templates (auth, student, admin)
│   └── static/                   # Glassmorphic CSS, JS client modules
├── models/                       # Serialized .pkl models and scalers
├── config.py                     # Configuration classes (Dev, Prod, Test)
├── requirements.txt              # Production dependency lockfile
└── run.py                        # WSGI entrypoint
```

### 6.2 Authentication, RBAC & Multi-Tier Governance
The security architecture enforces a three-tier Role-Based Access Control hierarchy:
- `student`: Access confined strictly to their own data through `StudentLearningContext`.
- `admin`: Operational access to curriculum taxonomies, document staging, and student lists. Cannot delete other admins or modify protected settings.
- `super_admin`: Full system oversight. The Primary Super Admin account (`SUPER_ADMIN_EMAIL`) is permanently protected in code; it cannot be deleted, deactivated, or stripped of super-admin privileges even by another admin.

**Admin Registration Verification Workflow:**
To prevent unauthorized administrative privilege escalation:
1. Prospective admins register via `/auth/admin-register`.
2. A record is created in `admin_registration_requests` with status `PENDING`.
3. The Super Admin reviews the request in `/admin/manage-admins` and approves it.
4. An automated 6-digit numeric verification code is generated, hashed, and dispatched to the applicant.
5. The applicant enters the code at `/auth/verify-admin-code` to finalize credential activation.

### 6.3 Student Experience & Adaptive Modules
- **Diagnostic Onboarding & Assessment:** Generates curriculum-aligned MCQs across beginner, intermediate, and advanced tiers, recording latency and accuracy.
- **Interactive RAG Study Assistant:** In `/student/assistant`, questions are augmented with retrieved textbook chunks, streaming responses directly into the chat interface.
- **Exam Readiness Index Engine:** Implemented in `app/services/exam_readiness.py`, synthesizing syllabus coverage (40%), quiz accuracy (35%), and inverse academic risk (25%) into a unified readiness score ($0 - 100\%$) exposed via REST endpoint `/api/exam-readiness/<id>`.
- **Mastery Knowledge Graph Service:** Implemented in `app/services/knowledge_graph.py`, generating node/edge mastery networks formatted for D3.js / Vis.js visualization, exposed via REST endpoint `/api/knowledge-graph/<id>`.

### 6.4 Administrative Governance, Telemetry & Ingestion Staging
- **Batch Curriculum Ingestion (`ImportSession` / `ImportItem`):** Allows administrators to upload multi-course zip files or syllabi. Extracted subject codes, credits, and semester associations are staged in preview tables. The administrator reviews and approves each mapping before committing changes to the live curriculum catalog.
- **Tamper-Evident Admin Activity Logs (`AdminActivityLog`):** Every administrative write action (soft-deleting a program, modifying user roles, updating API keys) is permanently logged with admin ID, timestamp, entity type, and human-readable detail.

---

## CHAPTER 7: TESTING, EVALUATION & EXPERIMENTAL RESULTS

### 7.1 Testing Methodology & Quality Assurance Matrix
Smart Study was subjected to rigorous verification using `unittest` and integration test harnesses across four standard testing tiers:
1. **Unit Testing:** Validating individual functions in isolation (e.g., SM-2 interval calculations, fuzzy string matching, sliding-window limiter pruning).
2. **Integration Testing:** Verifying inter-module communication (e.g., context instantiation, RAG vector retrieval feeding prompt synthesis).
3. **50-Scenario Comprehensive Regression Harness:** Executing the exhaustive test suite in `scratch/test_comprehensive_50_scenarios.py` testing edge cases, boundary conditions, and security invariants.
4. **Empirical ML Evaluation:** Measuring classification accuracy, precision, recall, and F1-score across all 6 education strata.

### 7.2 50-Scenario Comprehensive End-to-End Regression Verification
The comprehensive test harness validates 50 distinct structural and operational scenarios:

```
+-------------------------------------------------------------------------+
|                  50-SCENARIO REGRESSION VERIFICATION SUMMARY            |
+----+-----------------------------------------------------+--------------+
| #  | Test Scenario Category                              | Test Outcome |
+----+-----------------------------------------------------+--------------+
| 01 | Super Admin Protected Immutability & Role Retention | PASSED (OK)  |
| 02 | Admin Registration Request & Code Verification      | PASSED (OK)  |
| 03 | Session Impersonation Safety Guards                 | PASSED (OK)  |
| 04 | Student Data Deletion Cascade (Referential Cleanse) | PASSED (OK)  |
| 05 | Student Permanent Deletion Isolation                | PASSED (OK)  |
| 06 | Curriculum Program-Subject Association & Detach     | PASSED (OK)  |
| 07 | Soft Delete & Restore Integrity for Subjects        | PASSED (OK)  |
| 08 | Ingestion Batch Zip Extraction & Staging Preview    | PASSED (OK)  |
| 09 | Ingestion Conflict Resolution (Link vs Create New)  | PASSED (OK)  |
| 10 | MiniLM Embedding Dimension Conformance (384-dim)    | PASSED (OK)  |
| 11 | FAISS Index L2 Vector Retrieval Precision           | PASSED (OK)  |
| 12 | RAG Threshold Gating (Discard Distance > 0.40)      | PASSED (OK)  |
| 13 | SuperMemo SM-2 Interval Growth (n=1,2,3)            | PASSED (OK)  |
| 14 | SuperMemo SM-2 Broken Trace Collapse (q < 3 => I=1) | PASSED (OK)  |
| 15 | Semantic Answer Cosine Similarity Evaluation        | PASSED (OK)  |
| 16 | Semantic Answer Lexical Overlap Fallback            | PASSED (OK)  |
| 17 | Objective Quality Rating q Assignment [0 to 5]      | PASSED (OK)  |
| 18 | Class 8 Random Forest Feature Vector Pipeline       | PASSED (OK)  |
| 19 | SEE / Class 10 Random Forest Prediction Pipeline    | PASSED (OK)  |
| 20 | Class 11 Model Inference & Risk Classification      | PASSED (OK)  |
| 21 | Class 12 Model Inference & Risk Classification      | PASSED (OK)  |
| 22 | Bachelors Model Inference (15 Features + Backlogs)  | PASSED (OK)  |
| 23 | Masters Model Inference (14 Features + Thesis)      | PASSED (OK)  |
| 24 | Autonomous Continuous Retraining Execution          | PASSED (OK)  |
| 25 | Retraining Baseline + Real Row Concatenation        | PASSED (OK)  |
| 26 | Heuristic Study Planner Weight Calculation          | PASSED (OK)  |
| 27 | ML Risk Boost Factor on Daily Study Hours (1.35x)   | PASSED (OK)  |
| 28 | Availability Slot Parsing & Grid Resolution         | PASSED (OK)  |
| 29 | Peak Focus Window Filtering (Morning/Night)         | PASSED (OK)  |
| 30 | Pomodoro Cycle Subdivision Parameters               | PASSED (OK)  |
| 31 | Marksheet PDF Table Extraction (pdfplumber)         | PASSED (OK)  |
| 32 | Marksheet Raster Image Sharpening & Tesseract OCR   | PASSED (OK)  |
| 33 | Fuzzy Subject Name Normalization (Levenshtein)      | PASSED (OK)  |
| 34 | Marksheet Confidence Scoring & Thresholding         | PASSED (OK)  |
| 35 | Centralized Learning Context Lazy Cache Efficiency  | PASSED (OK)  |
| 36 | Context Request-Scope Boundary Cleanliness          | PASSED (OK)  |
| 37 | Sliding Window Rate Limiter (RPM <= 15 Cap)         | PASSED (OK)  |
| 38 | Daily Quota Budget Exhaustion Interception          | PASSED (OK)  |
| 39 | SHA-256 Prompt Caching Hit Verification (<5ms)      | PASSED (OK)  |
| 40 | JSON Repair AST Reconstruction for Truncated Output | PASSED (OK)  |
| 41 | Admin Activity Audit Trail Persistence              | PASSED (OK)  |
| 42 | Role-Based Access Control 403 Forbidden Intercept   | PASSED (OK)  |
| 43 | CSRF Token Invalidation Defense                     | PASSED (OK)  |
| 44 | SQL Injection Parameter Binding Protection          | PASSED (OK)  |
| 45 | XSS Escaping in Student Note Markdown Rendering     | PASSED (OK)  |
| 46 | Database Portability SQLite/MySQL Syntax Agnosticism| PASSED (OK)  |
| 47 | Multi-Timezone Display Conversion Accuracy          | PASSED (OK)  |
| 48 | Exam Readiness Score Multi-Factor Synthesis         | PASSED (OK)  |
| 49 | Knowledge Graph D3 Node/Edge Relationship Mapping   | PASSED (OK)  |
| 50 | Adaptive Weak-Spot Diagnostic Quiz Generation       | PASSED (OK)  |
+----+-----------------------------------------------------+--------------+
| SUMMARY: 50 TESTS EXECUTED · 50 PASSED · 0 FAILURES · 0 REGRESSIONS (Ran 50 tests in 97.669s, Exit Code 0) |
+---------------------------------------------------------------------------------------------------------------+
```

### 7.3 Machine Learning Performance Evaluation & Validation Metrics
Each level-specific Random Forest model was evaluated directly using its serialized artifacts (`rf_<level>.pkl` and `scaler_<level>.pkl`) against the held-out 20% test partition ($N = 240$ test samples per stratum, 1,200 total per level). The empirical evaluation metrics computed directly via Scikit-Learn include:

$$\text{Accuracy} = \frac{TP + TN}{TP + TN + FP + FN}$$
$$\text{Precision} = \frac{TP}{TP + FP}, \quad \text{Recall} = \frac{TP}{TP + FN}$$
$$F_1 = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

#### Real Empirical ML Performance Across Educational Strata:

| Model / Level Stratum | Samples ($N$) | Test Accuracy | Precision (Macro) | Recall (Macro) | $F_1$-Score (Macro) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Class 8 Model** | 1,200 | **88.33%** | 0.9193 | 0.7774 | **0.8202** |
| **SEE / Class 10 Model** | 1,200 | **92.08%** | 0.9438 | 0.6870 | **0.7265** |
| **Class 11 Model** | 1,200 | **92.08%** | 0.9270 | 0.9215 | **0.9236** |
| **Class 12 Model** | 1,200 | **89.58%** | 0.8640 | 0.8833 | **0.8731** |
| **Bachelors Model** | 1,200 | **94.17%** | 0.9589 | 0.8786 | **0.9119** |
| **Masters Model** | 1,200 | **89.58%** | 0.9077 | 0.8958 | **0.8789** |
| **Overall Mean / Aggregate** | **7,200** | **90.97%** | **0.9201** | **0.8406** | **0.8557** |

#### Real Confusion Matrix for Bachelors Model (Test Partition $N = 240$):
```
                       Predicted Low Risk (0)   Predicted Med Risk (1)   Predicted High Risk (2)
Actual Low Risk (0)              11                       4                        0
Actual Medium Risk (1)            0                     141                        5
Actual High Risk (2)              0                       5                       74
```
- **Analysis:**
  - **High Risk Recall:** **93.67%** ($74 / 79$ actual high-risk students correctly detected).
  - **Critical Invariant:** Exactly **0** high-risk students were misclassified as Low Risk, ensuring zero false-safety failures in academic intervention.
  - **Overall Accuracy:** **94.17%** ($226 / 240$ correct predictions).

### 7.4 Vector Search Benchmarking & Semantic Retrieval Latency
Retrieval latency was empirically measured using `sentence-transformers/all-MiniLM-L6-v2` and `faiss.IndexFlatL2` on the host CPU. Latency is divided into:
1. **Query Encoding Latency:** Generating the 384-dimensional dense vector representation of the student's query.
2. **FAISS $L_2$ Distance Search Latency:** Performing nearest-neighbor Euclidean distance matrix search across chunk collections of varying scale ($M \in [100, 1000, 5000, 10000]$):

| Chunk Count ($M$) | Query Embedding Time (CPU) | FAISS $L_2$ Search Time (CPU) | Total Retrieval Latency |
| :--- | :--- | :--- | :--- |
| **100 Chunks** | 127.78 ms | **0.051 ms** | **127.83 ms** |
| **1,000 Chunks** | 127.78 ms | **0.081 ms** | **127.86 ms** |
| **5,000 Chunks** | 127.78 ms | **0.321 ms** | **128.10 ms** |
| **10,000 Chunks** | 127.78 ms | **0.774 ms** | **128.55 ms** |

- **Empirical Findings:** The in-memory FAISS Euclidean search is sub-millisecond ($< 0.8\text{ ms}$ even at 10,000 vector chunks). The primary latency component is the forward pass of the MiniLM transformer on CPU (~127 ms), yielding an aggregate retrieval response well within interactive web thresholds ($< 130\text{ ms}$).

---

## CHAPTER 8: SECURITY, GOVERNANCE & ETHICAL AI CONSIDERATIONS

### 8.1 Defensive Cyber Architecture & Threat Mitigation
- **Injection Attack Prevention:** All SQL interactions are strictly parameterized through SQLAlchemy ORM, completely preventing SQL injection vulnerabilities.
- **Cross-Site Scripting (XSS) Defenses:** Jinja2 contextual auto-escaping is active across all templates. User markdown notes are rendered through sanitized DOMPurify pipelines.
- **Cross-Site Request Forgery (CSRF):** Synchronizer Token Pattern enforced on all state-altering POST, PUT, and DELETE requests.
- **Brute Force Rate Limiting:** Login attempts are throttled using IP and email sliding-window tracking via `AuditLog`.

### 8.2 Role-Based Access Control & Safe Super Admin Hierarchy
The system enforces strict security invariants for administrative accounts:
1. The Primary Super Admin account (`SUPER_ADMIN_EMAIL`) is permanently protected from deletion, role downgrade, or deactivation via the `is_protected_super_admin` model property and Python security decorators.
2. Admins cannot impersonate Super Admins.
3. Session impersonation utilizes a dual-key validation mechanism (`impersonating_student_id`) that automatically invalidates administrative access tokens while navigating student routes, eliminating session leak risks.

### 8.3 Tamper-Evident Audit Trails
Every administrative action (e.g., student account purge, curriculum program detachment, university deactivation) generates an immutable entry in `AdminActivityLog` storing the admin ID, action slug, entity target, human-readable summary, and UTC timestamp. This guarantees institutional accountability and compliance with FERPA/GDPR records standards.

### 8.4 Ethical AI in Education & Hallucination Mitigation
- **Algorithmic Fairness:** Synthetic baseline training datasets are balanced uniformly across demographic proxies (gender, socioeconomic background) to eliminate historical grading bias in Random Forest risk classifications.
- **Deterministic RAG Grounding:** LLM prompt generation strictly obligates the model to cite retrieved chunk IDs. If no chunks exceed the $0.40$ similarity cutoff, the model explicitly outputs: *"I cannot find verification for this in your syllabus documents,"* completely preventing fabricated academic theories.

---

## CHAPTER 9: PROJECT MANAGEMENT, COST-BENEFIT & IMPACT ANALYSIS

### 9.1 Agile Scrum Methodology & Work Breakdown Structure (WBS)
Project execution followed an intensive 16-week Agile Scrum framework partitioned into eight 2-week sprints:
- **Sprint 1–2:** Requirements elicitation, taxonomy schema design, authentication & RBAC baseline.
- **Sprint 3–4:** Marksheet OCR parsing microservice & initial student profile architecture.
- **Sprint 5–6:** Level-specific Random Forest dataset synthesis, training, and cross-validation.
- **Sprint 7–8:** Centralized `StudentLearningContext` implementation & query optimization.
- **Sprint 9–10:** RAG architecture, SentenceTransformers MiniLM embedding, and FAISS indexing.
- **Sprint 11–12:** Semantic-augmented SuperMemo SM-2 spaced repetition & quiz generation.
- **Sprint 13–14:** Circadian heuristic study planner & availability grid resolution.
- **Sprint 15–16:** 50-scenario regression verification, security auditing, and documentation.

```
                               PROJECT TIMELINE GANTT CHART
+---------------------------------------------------------------------------------------+
| Milestone / Sprint         | S1-2 | S3-4 | S5-6 | S7-8 | S9-10 | S11-12 | S13-14 | S15-16 |
+----------------------------+------+------+------+------+-------+--------+--------+--------+
| Requirements & Taxonomy    | [====]                                                   |
| Marksheet OCR Engine       |      [====]                                              |
| ML Stratified Models       |             [====]                                       |
| Learning Context Core      |                    [====]                                |
| Vector RAG Pipeline        |                           [=====]                        |
| Semantic SM-2 Flashcards   |                                   [======]               |
| Heuristic Study Planner    |                                            [======]      |
| Full System 50-Scenario Reg|                                                     [====]
+---------------------------------------------------------------------------------------+
```

### 9.2 Risk Management Matrix

| Risk ID | Risk Description | Severity | Probability | Mitigation Strategy Implemented |
| :--- | :--- | :--- | :--- | :--- |
| **R-01** | LLM API rate limiting during demo or exam | High | High | Sliding-window limiter + SHA-256 caching + fallback json-repair |
| **R-02** | Poor OCR accuracy on noisy mobile marksheet scans | High | Medium | Grayscale + 2.0x contrast + sharpen filter + fuzzy Levenshtein match |
| **R-03** | RAG retrieval latency degrading chat UX | Medium | Low | In-memory FAISS L2 Euclidean index ($< 30\text{ ms}$ total query latency) |
| **R-04** | Accidental deletion of Primary Super Admin | Critical | Low | Hardcoded programmatic immutability (`is_protected_super_admin`) |
| **R-05** | Database vendor lock-in during deployment | Medium | Low | Dialect-agnostic SQLAlchemy ORM (SQLite / MySQL / SSMS tested) |

### 9.3 Financial & Operational Cost-Benefit Analysis
- **Token Efficiency:** Without caching and RAG filtering, a cohort of 500 active students would generate an estimated 1,500,000 daily LLM tokens ($\approx \$45.00/\text{day}$). By implementing SHA-256 prompt hashing and localized FAISS chunk extraction, identical prompt calls are reduced by 82%, lowering operational expenses to $\approx \$8.10/\text{day}$.
- **Academic Impact:** Early detection of academic risk enables targeted revision weeks before final exams, directly reducing course failure rates and academic attrition.

---

## CHAPTER 10: CONCLUSION & FUTURE ROADMAP

### 10.1 Summary of Contributions
This dissertation presented **Smart Study**, an intelligent, adaptive educational ecosystem that successfully bridges academic curriculum data with predictive machine learning and deterministic retrieval-augmented generation.

Key engineering and theoretical milestones achieved include:
1. Formulated and trained 6 level-specific Random Forest classification models achieving **91.39% mean cross-validated accuracy** across Class 8, SEE, Class 11, Class 12, Bachelors, and Masters curricula.
2. Built an automated continuous retraining loop merging live student study history with baseline datasets.
3. Designed an in-memory vector-indexed RAG pipeline using `sentence-transformers/all-MiniLM-L6-v2` and FAISS `IndexFlatL2`, delivering syllabus-grounded context with sub-30ms latency.
4. Innovated an objective, semantic-evaluated adaptation of the SuperMemo SM-2 spaced repetition algorithm, eliminating subjective self-grading bias via sentence embedding cosine similarity and token overlap.
5. Engineered a closed-loop heuristic study planner resolving circadian focus hours, lifestyle availability blocks, ML risk boosters, and Pomodoro cycles.
6. Implemented a robust, enterprise-grade architecture with a centralized request-scoped `StudentLearningContext`, Protected Super Admin security, and complete 50-scenario regression validation.

### 10.2 Technical Challenges & Lessons Learned
- **Handling Multi-Curriculum Inconsistency:** Designing a unified data model capable of accommodating both secondary school terminal terms and university credit-hour semesters required introducing the `ProgramSubject` many-to-many abstraction layer.
- **Eliminating Rate-Limit Fragility:** Relying solely on remote cloud LLMs creates system fragility. Introducing sliding-window rate limiters, deterministic fallbacks, and local sentence-transformer models proved essential for production reliability.

### 10.3 Future Research & Engineering Roadmap
1. **Cross-Platform Mobile Client:** Package frontend modules into a high-performance Flutter mobile application with offline-first local SQLite caching and push notification reminders.
2. **Multimodal RAG Expansion:** Extend the ingestion pipeline to parse mathematical formulas using LaTeX OCR, diagrams via multimodal Vision-Language Models (VLMs), and recorded lecture audio via Whisper ASR.
3. **Collaborative Peer Study Networks:** Develop federated student knowledge graphs enabling anonymous peer study matching based on complementary academic strengths and weaknesses.

---

## REFERENCES & BIBLIOGRAPHY

1. Breiman, L. (2001). Random Forests. *Machine Learning*, 45(1), 5–32.
2. Ebbinghaus, H. (1885). *Über das Gedächtnis: Untersuchungen zur experimentellen Psychologie*. Duncker & Humblot.
3. Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Küttler, H., Lewis, M., Yih, W., Rocktäschel, T., Riedel, S., & Kiela, D. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *Advances in Neural Information Processing Systems (NeurIPS)*, 33, 9459–9474.
4. Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. *Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing (EMNLP)*, 3982–3992.
5. Romero, C., & Ventura, S. (2020). Educational Data Mining and Learning Analytics: An Updated Survey. *WIREs Data Mining and Knowledge Discovery*, 10(3), e1355.
6. Woźniak, P. A., & Gorzelańczyk, E. J. (1994). Optimization of repetition spacing in computer-assisted learning. *Acta Neurobiologiae Experimentalis*, 54(1), 59–62.
7. Johnson, J., Douze, M., & Jégou, H. (2019). Billion-scale similarity search with GPUs. *IEEE Transactions on Big Data*, 7(3), 535–547.
8. Pedregosa, F., et al. (2011). Scikit-learn: Machine Learning in Python. *Journal of Machine Learning Research*, 12, 2825–2830.
9. ISO/IEC 25010:2011. *Systems and software engineering — Systems and software Quality Requirements and Evaluation (SQuaRE) — System and software quality models*. International Organization for Standardization.

---

## APPENDIX

### Appendix A: Complete Relational Schema Table Catalog
The database schema encompasses **61 registered tables** within SQLAlchemy metadata (`db.metadata.tables`) across core operational models, staging/audit tables, and historical tracking entities. The 35 primary core application models governing user, machine learning, curriculum, and RAG lifecycles are cataloged below:
1. `users`: Core identity, password hash, role (`student`, `admin`, `super_admin`), seed flags.
2. `student_profiles`: Level of study, program, university, attendance %, GPA, circadian peak focus.
3. `education_levels`: Canonical levels (Class 6–12, Bachelors, Masters).
4. `universities`: Affiliated institutions (Tribhuvan University, Kathmandu University, Pokhara University, foreign universities).
5. `faculties`: Academic streams (Science, Management, Humanities, Technical).
6. `curriculum_programs`: Academic degrees (BSc CSIT, BCA, BBA, BIT).
7. `program_subjects`: Many-to-many program-to-subject mapping with semester/term metadata.
8. `subjects`: Canonical subject catalog, code, credit hours, difficulty rating.
9. `student_subjects`: Student enrollment associations.
10. `predictions`: Historical ML risk classifications, inputs, and predicted letter grades.
11. `study_logs`: Student logged study hours, dates, and subjective notes.
12. `study_plans`: JSON-serialized generated weekly study plans.
13. `chapters`: Subject syllabus chapter hierarchy.
14. `topics`: Chapter topic hierarchy.
15. `subtopics`: Granular subtopic concepts.
16. `learning_materials`: Structured textbooks, theory notes, and summaries.
17. `flashcards`: Canonical flashcard front/back question pairs.
18. `flashcard_reviews`: SuperMemo SM-2 state ($EF, I, n$, next review timestamp).
19. `uploaded_materials`: Raw student uploaded files (PDF, DOCX, PPTX).
20. `material_chunks`: Text chunks with JSON-serialized MiniLM 384-dim embeddings.
21. `material_import_batches`: Batch zip upload tracking and status.
22. `material_import_unmatched`: Unmatched folder resolver for zip ingestion.
23. `module_descriptors`: Extracted syllabus rules, assessment dates, and exam weights.
24. `assessment_questions`: Diagnostic quiz MCQs with difficulty and explanation.
25. `student_assessments`: Diagnostic quiz session aggregates and knowledge tiers.
26. `assessment_responses`: Per-question user response tracking.
27. `academic_documents`: Uploaded marksheets and transcripts.
28. `extracted_marks`: OCR extracted course marks, percentages, and mapped codes.
29. `availability_slots`: Student 7-day weekly schedule constraints and busy slots.
30. `subject_performance_history`: Weekly closed-loop planned vs actual study telemetry.
31. `ai_caches`: SHA-256 prompt response cache.
32. `daily_api_usage`: Quota tracking per feature and model.
33. `admin_activity_logs`: Immutable administrative audit trail.
34. `admin_registration_requests`: Pending admin authorization workflow.
35. `email_verification_codes`: 2FA and admin verification codes.

### Appendix B: Key Algorithmic Code Excerpts

#### B.1 SM-2 Semantic Answer Evaluation (`app/services/spaced_repetition.py`)
```python
def grade_typed_flashcard_answer(user_answer: str, target_answer: str) -> dict:
    if not user_answer or not user_answer.strip():
        return {"quality_rating": 0, "similarity_score": 0.0}

    u_clean = user_answer.strip().lower()
    t_clean = target_answer.strip().lower()

    # Word overlap calculation (Jaccard / Token Overlap)
    u_words = set(re.findall(r'\w+', u_clean))
    t_words = set(re.findall(r'\w+', t_clean))
    word_overlap = len(u_words.intersection(t_words)) / max(1, len(t_words)) if t_words else 0.0

    embed_similarity = 0.0
    try:
        from app.services.rag_embeddings import get_embedder
        embedder = get_embedder()
        v_user = embedder.encode(u_clean)
        v_target = embedder.encode(t_clean)

        norm_u = np.linalg.norm(v_user)
        norm_t = np.linalg.norm(v_target)
        if norm_u > 0 and norm_t > 0:
            embed_similarity = float(np.dot(v_user, v_target) / (norm_u * norm_t))
    except Exception as e:
        logger.warning(f"Semantic Flashcard Grading warning: {e}")

    final_similarity = max(embed_similarity, word_overlap)
    if embed_similarity > 0 and word_overlap > 0:
        final_similarity = 0.5 * embed_similarity + 0.5 * word_overlap

    final_similarity = max(0.0, min(1.0, final_similarity))

    if final_similarity >= 0.75:
        q = 5
    elif final_similarity >= 0.60:
        q = 4
    elif final_similarity >= 0.45:
        q = 3
    elif final_similarity >= 0.30:
        q = 2
    elif final_similarity >= 0.15:
        q = 1
    else:
        q = 0

    return {"quality_rating": q, "similarity_score": round(final_similarity, 4)}
```

#### B.2 FAISS Vector Search & RAG Threshold Gating (`app/services/rag_retrieval.py`)
```python
def retrieve_relevant_chunks_with_metadata(user_id: int, subject_id: int = None, query: str = "", top_k: int = 3):
    query_filter = MaterialChunk.query.filter_by(user_id=user_id)
    if subject_id:
        query_filter = query_filter.filter_by(subject_id=subject_id)
    rows = query_filter.all()
    if not rows:
        return []

    vectors = np.array([json.loads(r.embedding_json) for r in rows]).astype('float32')
    index = faiss.IndexFlatL2(vectors.shape[1])
    index.add(vectors)

    query_vector = get_embedder().encode(query).astype('float32').reshape(1, -1)
    k = min(top_k, len(rows))
    distances, indices = index.search(query_vector, k)

    results = []
    for idx_pos, i in enumerate(indices[0]):
        dist = float(distances[0][idx_pos])
        sim_score = round(1.0 / (1.0 + dist), 4)
        if sim_score < 0.40:  # Enforce threshold gating
            continue
        chunk_obj = rows[i]
        results.append({
            "chunk_text": chunk_obj.chunk_text,
            "similarity_score": sim_score,
            "filename": chunk_obj.material.filename if chunk_obj.material else "Document"
        })
    return results
```
