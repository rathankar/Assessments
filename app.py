# app.py
import re, textwrap, streamlit as st, google.generativeai as genai

# ─────────────────────────────────────  1.  CONFIG
CHAPTERS = {
    "Mechanics": ["Kinematics", "Dynamics", "Work/Energy", "Momentum",
                  "Circular Motion"],
    "Waves": ["Wave Basics", "Interference", "Doppler Effect"],
    "Thermal Physics": ["Temperature & Heat", "Ideal Gases"],
    "Electricity & Magnetism": ["Electric Fields", "Circuits", "Induction"],
    "Modern Physics": ["Quantum Theory", "Relativity"]
}

DIFF = {
  "1": ("IGCSE 6-8",   "Checkpoint-style one-sentence conceptual question (no maths)."),
  "2": ("MYP 5",       "Real-world conceptual question that needs critical thinking."),
  "3": ("IGCSE 9-10",  "Short, straightforward core-paper question. Avoid algebra."),
  "4": ("IB DP 11-12", "Quantitative IB DP problem requiring calculation and units."),
  "5": ("CBSE 10",     "CBSE Class-10 board-paper style conceptual/numerical question."),
  "6": ("CBSE 11",     "CBSE Class-11 question – mostly conceptual with light maths."),
  "7": ("CBSE 12",     "CBSE Class-12 board-style numerical / reasoning question."),
  "8": ("ICSE 10",     "ICSE Class-10 physics past-paper style conceptual question."),
  "9": ("AS Level",    "Cambridge AS-Level structured calculation question."),
  "10":("A Level",     "Full A-Level Paper-2 multi-step question with explanation.")
}

MCQ_RE = re.compile(
 r"\d+\.\s*Question:\s*(.*?)\s*A\)\s*(.*?)\s*B\)\s*(.*?)\s*C\)\s*(.*?)"
 r"\s*D\)\s*(.*?)\s*Answer:\s*([A-D])\s*Explanation:\s*([\s\S]*?)(?:---|$)",
 re.S)

genai.configure(api_key=st.secrets["GEMINI_KEY"])

# ─────────────────────────────────────  2.  PAGE META
st.set_page_config(page_title="Physics Spark", page_icon="⚡", layout="centered")

# ─────────────────────────────────────  3.  SESSION STATE
if "stage" not in st.session_state:
    st.session_state.update(stage="login", q=0, score=0,
                            asked=set(), mcq=[], results=[])

# ─────────────────────────────────────  4.  HELPERS
@st.cache_data(show_spinner=False)
def call_gemini(prompt, t=0.7):
    return genai.GenerativeModel("gemini-1.5-flash-latest")\
               .generate_content(prompt, temperature=t).text.strip()

def parse_mcqs(text):
    out=[]
    for m in MCQ_RE.finditer(text):
        out.append(dict(q=m[1].strip(),
                        opts=[m[2].strip(),m[3].strip(),m[4].strip(),m[5].strip()],
                        key=m[6], expl=m[7].strip()))
    return out

def parse_grade(txt, level):
    pts=int(re.search(r"SCORE:\s*(\d)",txt).group(1))
    model=txt.split("MODEL:",1)[-1].strip()
    if level=="3" and pts<3: pts=min(3,pts+1)          # lenient bump
    return pts, model

def colour_block(label, text, colour):
    st.markdown(f'<div style="background:{colour};padding:8px 12px;border-radius:6px">'
                f'{label}: {text}</div>', unsafe_allow_html=True)

# ─────────────────────────────────────  5.  LOGIN
if st.session_state.stage=="login":
    st.title("Physics Spark Diagnostic")
    key = st.text_input("Google AI API Key", type="password")
    if st.button("Login") and key:
        st.secrets["GEMINI_KEY"]=key
        st.session_state.stage="setup"
        st.experimental_rerun()

# ─────────────────────────────────────  6.  SET-UP
if st.session_state.stage=="setup":
    st.header("Set up diagnostic")
    stu  = st.text_input("Student name")
    chap = st.selectbox("Chapter", [""]+list(CHAPTERS))
    top  = st.selectbox("Topic", [""] if not chap else CHAPTERS[chap])
    diff = st.selectbox("Difficulty band", [""]+[f"{k} – {v[0]}" for k,v in DIFF.items()])
    if st.button("Start") and "" not in (stu,chap,top,diff):
        k = diff.split(" – ")[0]
        st.session_state.update(student=stu, chapter=chap,
                                topic=top, level=k, prompt=DIFF[k][1])
        raw = call_gemini(
           f"{DIFF[k][1]}  Generate 5 distinct MCQs on '{top}'."
           " Provide A-D options, correct letter and one-sentence explanation. "
           "Format:\n1. Question: ... A) ... B) ... C) ... D) ... "
           "Answer: X Explanation: ... ---")
        st.session_state.mcq = parse_mcqs(raw)
        st.session_state.stage="quiz"
        st.experimental_rerun()

# ─────────────────────────────────────  7.  QUIZ LOOP
if st.session_state.stage=="quiz":
    q_i = st.session_state.q
    st.progress(q_i/10)
    st.markdown(f"### Question {q_i+1} / 10   |   Score {st.session_state.score}/30")

    # ---------- conceptual ----------
    if q_i < 5:
        if "currentQ" not in st.session_state:
            while True:
                q = call_gemini(f"{st.session_state.prompt}  Topic:{st.session_state.topic}. "
                                f"Do NOT repeat: {list(st.session_state.asked)}")
                if q not in st.session_state.asked: break
            st.session_state.currentQ = q
        st.info(st.session_state.currentQ)
        ans = st.text_area("Your answer:", key=q_i)
        if st.button("Submit", key=f"s{q_i}") and ans:
            grade = call_gemini(f"{st.session_state.prompt}\nQuestion:"
                                f"\"{st.session_state.currentQ}\"\nStudent:\"{ans}\""
                                "\nReturn: SCORE:[0-5] MODEL:[model]")
            pts, model = parse_grade(grade, st.session_state.level)
            st.session_state.score += pts
            st.session_state.results.append(
              dict(q=st.session_state.currentQ, s=ans, ai=model, mark=f"{pts}/5"))
            st.session_state.asked.add(st.session_state.currentQ)
            st.session_state.q +=1; del st.session_state.currentQ; st.experimental_rerun()

    # ---------- MCQ ----------
    else:
        mcq = st.session_state.mcq[q_i-5]
        st.info(mcq["q"])
        choice = st.radio("Select", [f"{chr(65+i)}) {o}" for i,o in enumerate(mcq["opts"])])
        if st.button("Submit", key=f"s{q_i}"):
            letter = choice[0]
            ok = letter==mcq["key"]
            if ok: st.session_state.score +=1
            st.session_state.results.append(
              dict(q=mcq["q"], s=choice,
                   ai=f"Correct: {mcq['key']}) {mcq['opts'][ord(mcq['key'])-65]}"
                      f"\nExplanation: {mcq['expl']}",
                   mark="1/1" if ok else "0/1"))
            st.session_state.q +=1; st.experimental_rerun()

# ─────────────────────────────────────  8.  RESULTS
if st.session_state.stage=="quiz" and st.session_state.q==10:
    st.session_state.stage="done"; st.experimental_rerun()

if st.session_state.stage=="done":
    st.header("Diagnostic complete")
    st.write(f"**Student:** {st.session_state.student}")
    st.write(f"**Topic:** {st.session_state.chapter} – {st.session_state.topic}")
    st.write(f"**Difficulty:** {DIFF[st.session_state.level][0]}")
    st.subheader(f"Final Score  {st.session_state.score}/30")

    for i,r in enumerate(st.session_state.results,1):
        colour_block(f"Q{i}", r["q"]+f"  (Marks {r['mark']})", var="var(--q)")
        colour_block("You", r["s"], var="var(--stu)")
        colour_block("AI",  r["ai"].replace("\n","<br>"), var="var(--ai)")

    st.info("Click the **ℹ️ Share** button (top-right) after deployment "
            "to get a public link.")

