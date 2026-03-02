# Enterprise AI Knowledge Platform (Upwork Portfolio Description)

**The Challenge:**
If you've tried deploying standard RAG (LangChain + VectorDB) for complex corporate data—like 40-hour engineering video lectures or deep technical threads—you probably know the pain. It chops context, gets "lost in the middle", and eventually hallucinate answers. In an enterprise environment, a confident AI that invents facts is not just useless; it's dangerous.

**My Architectural Approach:**
I didn't build another standard chatbot. I architected this platform as an automated **"Research Laboratory"**—a highly controlled, 8-phase asynchronous pipeline (Map-Resolve-Reduce) where the AI is strictly orchestrated to provide psychologically safe, zero-hallucination answers.

**--- Solving the "Lost Context" Problem (Parent-Child Indexing).**
Instead of feeding the LLM an unreadable "salad" of chunks, I engineered a bridging system. The AI receives the critical video segment in full detail, while the surrounding 15 minutes are compressed into tight summaries. The LLM gets a perfect, continuous storyline without losing focus.

**--- Cost-Effective Multi-Model Routing.**
To keep API costs reasonable, the system uses a strict "Scout & Thinker" pattern. A fast, cheap model (Gemini 2.5 Flash Lite) rapidly churns through hundreds of posts to discard the noise. Only the top 5% verified facts are passed to the heavy model (Gemini 3 Pro) for final synthesis.

**--- Community Reality-Check (The Reddit Sidecar).**
I built a parallel microservice that acts like a smart human researcher. It translates user queries into 5 different search strategies (hunting for "Tutorials", "Comparisons", etc.) across targeted technical subreddits, filtering out clickbait before the main AI ever sees it.

**--- Building B2B Trust (UX).**
Corporate users don't trust "black box" algorithms. I implemented Server-Sent Events (SSE) streaming. As the AI searches, the user sees a transparent, live log of the pipeline's thought process ("Scoring segments...", "Analyzing threads..."). It turns a waiting screen into a collaborative experience.

**The Bottom-Line Impact:**
By tackling LLM flaws structurally—including hardcoded, mandatory citations `[post:ID]` for every claim—the hallucination rate is zero. The system acts as a predictable, secure research partner that replaces hours of manual L2/L3 support digging with verified answers in under 120 seconds.

**Tech Stack:** Python (FastAPI), React 18 (Vite/Tailwind), SQLite, SSE Streaming, Multi-LLM Orchestration (Gemini).
