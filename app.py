import streamlit as st
import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
from PyPDF2 import PdfReader
import pandas as pd
from datetime import datetime

# Load API key
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

LEADERBOARD_CSV = "leaderboard.csv"
PYTHON_TOPICS_CSV = "python_topics.csv"  # Your big python topics dataset

# Page config
st.set_page_config(page_title="Quiz Generator", page_icon="🧠", layout="centered")

# --- Aesthetic CSS ---
st.markdown("""
<style>
/* Your CSS styles here - same as before */
body, .css-1d391kg {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: #f5f7fa;
}
h1 {
    color: #1f2937;
    font-weight: 800;
    font-size: 3rem;
    margin-bottom: 0.1em;
    text-align: center;
    letter-spacing: 2px;
}
h2, h3 {
    color: #374151;
    font-weight: 700;
    margin-top: 1.5em;
}
[data-baseweb="radio"] {
    flex-wrap: nowrap !important;
}
.stButton > button {
    background-color: #3b82f6;
    color: white;
    width: 170px;
    height: 45px;
    border-radius: 12px;
    border: none;
    font-size: 17px;
    font-weight: 600;
    box-shadow: 0 5px 15px rgba(59,130,246,0.3);
    transition: background-color 0.3s ease;
    margin: 1rem auto;
    display: block;
}
.stButton > button:hover {
    background-color: #2563eb;
    cursor: pointer;
}
.stTextInput>div>input, .stSelectbox>div>div>div>select, .stRadio>div>div>label {
    font-size: 16px;
    padding: 8px;
    border-radius: 8px;
    border: 1.8px solid #d1d5db;
    transition: border-color 0.3s ease;
}
.stTextInput>div>input:focus, .stSelectbox>div>div>div>select:focus {
    border-color: #3b82f6;
    outline: none;
}
.stTextArea>div>textarea {
    font-size: 16px;
    border-radius: 8px;
    border: 1.8px solid #d1d5db;
    padding: 10px;
    resize: vertical;
    transition: border-color 0.3s ease;
}
.stTextArea>div>textarea:focus {
    border-color: #3b82f6;
    outline: none;
}
.quiz-card {
    background: white;
    padding: 20px 25px;
    margin: 1.2rem 0;
    border-radius: 15px;
    box-shadow: 0 8px 20px rgba(0,0,0,0.07);
    transition: box-shadow 0.3s ease;
}
.quiz-card:hover {
    box-shadow: 0 12px 30px rgba(0,0,0,0.12);
}
[data-testid="stSidebar"] {
    background: #e0e7ff;
    padding: 20px;
    border-radius: 12px;
}
thead tr th {
    background-color: #3b82f6 !important;
    color: white !important;
    font-weight: 700 !important;
    font-size: 14px !important;
}
tbody tr td {
    font-size: 13px !important;
    color: #374151 !important;
}
.center-btn {
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# Title
st.markdown("<h1>🧠 QuizLens</h1>", unsafe_allow_html=True)

# Load Python topics dataset for recommendation
try:
    python_topics_df = pd.read_csv(PYTHON_TOPICS_CSV)
except Exception as e:
    st.sidebar.error(f"Error loading Python topics dataset: {e}")
    python_topics_df = pd.DataFrame()

# Initialize session state variables
if "quiz" not in st.session_state:
    st.session_state.quiz = []
if "user_answers" not in st.session_state:
    st.session_state.user_answers = []
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "recommended_topic" not in st.session_state:
    st.session_state.recommended_topic = None
if "topic" not in st.session_state:
    st.session_state.topic = ""
if "previous_scores" not in st.session_state:
    st.session_state.previous_scores = {}  # To store previous scores by topic and difficulty
if "weak_topics" not in st.session_state:
    st.session_state.weak_topics = {}  # key=(topic,difficulty), value=lowest score

# Sidebar: Topic Recommendation and Leaderboard
with st.sidebar:
    st.markdown("<h2 style='color:#3b82f6;'>💡 Recommended Topic</h2>", unsafe_allow_html=True)
    if st.session_state.recommended_topic:
        st.markdown(f"### {st.session_state.recommended_topic}")
    else:
        st.write("No recommended topic available.")

    st.markdown("---")

    # Leaderboard Section
    st.markdown("<h2 style='color:#3b82f6;'>🏆 Leaderboard</h2>", unsafe_allow_html=True)
    try:
        leaderboard_df = pd.read_csv(LEADERBOARD_CSV)
        leaderboard_df = leaderboard_df.sort_values(by="DateTime", ascending=False).head(10)
        st.dataframe(leaderboard_df.reset_index(drop=True))
    except Exception:
        st.write("No leaderboard data available yet.")

# Tabs for Main Content
tabs = st.tabs(["Take Quiz", "Weak Topics"])

with tabs[0]:
    # Input method radio horizontal
    input_method = st.radio(
        "Choose how to provide quiz content:",
        ("Topic", "Text Notes", "PDF"),
        index=0,
        horizontal=True,
    )

    uploaded_text = ""

    user_name = st.text_input("Enter your name:")

    difficulty = st.selectbox("Select quiz difficulty:", ["Easy", "Medium", "Hard"])

    num_questions = st.selectbox("How many questions do you want?", [3, 5, 10])

    def generate_quiz_from_text(text, num_questions, difficulty):
        prompt = (
            f"Generate {num_questions} multiple-choice questions with {difficulty.lower()} difficulty based on the following content:\n"
            f"{text}\n\n"
            "Format the output as JSON with this structure:\n"
            "[\n"
            "  {\n"
            "    \"question\": \"...\",\n"
            "    \"options\": [\"Option A\", \"Option B\", \"Option C\", \"Option D\"],\n"
            "    \"answer\": \"Correct Option\"\n"
            "  },\n"
            "  ...\n"
            "]"
        )
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)

        cleaned = response.text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned.removeprefix("```json").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned.removesuffix("```").strip()

        try:
            quiz = json.loads(cleaned)
            return quiz
        except Exception:
            st.error("⚠️ Failed to parse quiz. Please try again.")
            st.text_area("Raw response from Gemini:", response.text, height=300)
            return []

    # Input fields based on method
    if input_method == "Topic":
        topic = st.text_input("Enter a topic for your quiz:")
        st.session_state.topic = topic.strip()
    elif input_method == "Text Notes":
        uploaded_text = st.text_area("Paste your notes here:")
    elif input_method == "PDF":
        uploaded_file = st.file_uploader("Upload your notes PDF:", type=["pdf"])
        if uploaded_file is not None:
            pdf = PdfReader(uploaded_file)
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            uploaded_text = text.strip()
            st.markdown("### Extracted Text from PDF:")
            st.text_area("", uploaded_text, height=300)

    def reset_quiz():
        st.session_state.quiz = []
        st.session_state.user_answers = []
        st.session_state.submitted = False
        st.session_state.topic = ""
        st.session_state.recommended_topic = None
        st.experimental_rerun()

    # --- User Performance Predictor Function ---
    def predict_score(topic, difficulty, previous_scores_dict):
        """
        Simple heuristic predictor based on previous scores.
        If no previous data, predict 3/5 by default.
        """
        key = (topic.lower(), difficulty.lower())
        scores = previous_scores_dict.get(key, [])
        if scores:
            avg_score = sum(scores) / len(scores)
            predicted = round(avg_score, 1)
        else:
            predicted = 3.0
        return predicted

    # Show User Performance Predictor before quiz start, if user has entered topic and difficulty and name
    if user_name and st.session_state.topic and difficulty:
        predicted = predict_score(st.session_state.topic, difficulty, st.session_state.previous_scores)
        st.markdown(f"### 🔮 Predicted Score for '{st.session_state.topic}' ({difficulty}): {predicted}/5")

    generate_quiz_btn = False
    if user_name.strip():
        if input_method == "Topic" and st.session_state.topic:
            generate_quiz_btn = st.button("Generate Quiz")
        elif input_method in ["Text Notes", "PDF"] and uploaded_text.strip() != "":
            generate_quiz_btn = st.button("Generate Quiz")

    if generate_quiz_btn:
        source_text = st.session_state.topic if input_method == "Topic" else uploaded_text
        st.session_state.quiz = generate_quiz_from_text(source_text, num_questions, difficulty)
        st.session_state.user_answers = []
        st.session_state.submitted = False

    # Quiz form and submission
    if st.session_state.quiz and not st.session_state.submitted:
        with st.form("quiz_form"):
            for i, q in enumerate(st.session_state.quiz):
                st.markdown(f"<div class='quiz-card'><h3>Q{i+1}. {q['question']}</h3></div>", unsafe_allow_html=True)
                user_answer = st.radio(
                    label="Select an option:",
                    options=q["options"],
                    key=f"question_{i}"
                )
                if len(st.session_state.user_answers) < len(st.session_state.quiz):
                    st.session_state.user_answers.append(user_answer)
                else:
                    st.session_state.user_answers[i] = user_answer

            submitted = st.form_submit_button("Submit Answers")

        if submitted:
            st.session_state.submitted = True
            score = 0
            st.markdown("<h2>📝 Results</h2>", unsafe_allow_html=True)
            for i, q in enumerate(st.session_state.quiz):
                correct = q["answer"]
                user = st.session_state.user_answers[i]
                if user.strip().lower() == correct.strip().lower():
                    st.success(f"✅ Q{i+1}: Correct!")
                    score += 1
                else:
                    st.error(f"❌ Q{i+1}: Incorrect! Your answer: {user} | Correct answer: {correct}")
            st.info(f"🎯 {user_name}, you scored {score} out of {len(st.session_state.quiz)}.")

            # Save to leaderboard CSV
            topic_title = st.session_state.topic if input_method == "Topic" else "Notes"
            result = pd.DataFrame([{
                "Name": user_name,
                "Score": f"{score}/{len(st.session_state.quiz)}",
                "Topic": topic_title,
                "Difficulty": difficulty,
                "DateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }])
            header = not os.path.exists(LEADERBOARD_CSV)
            result.to_csv(LEADERBOARD_CSV, mode='a', index=False, header=header)

            # Update previous scores dict for performance predictor
            key = (topic_title.lower(), difficulty.lower())
            if key in st.session_state.previous_scores:
                st.session_state.previous_scores[key].append(score)
            else:
                st.session_state.previous_scores[key] = [score]

            # --- Update Weak Topics logic ---
            # Consider score less than 60% as weak for that topic+difficulty
            threshold_score = int(len(st.session_state.quiz) * 0.6)
            if score < threshold_score:
                # Add or update weak topic with lowest score
                current_weak_score = st.session_state.weak_topics.get(key, 1000)
                if score < current_weak_score:
                    st.session_state.weak_topics[key] = score
            else:
                # If user improves on a weak topic, remove it from weak_topics
                if key in st.session_state.weak_topics:
                    del st.session_state.weak_topics[key]

            # Update recommended topic only after quiz submitted and if topics data is available
            if input_method == "Topic" and not python_topics_df.empty:
                current = st.session_state.topic
                filtered = python_topics_df[python_topics_df['Topic_Name'].str.lower() != current.lower()] if current else python_topics_df
                if not filtered.empty:
                    new_topic = filtered.sample(1)['Topic_Name'].values[0]
                    st.session_state.recommended_topic = new_topic

            st.markdown("<div class='center-btn'>", unsafe_allow_html=True)
            if st.button("🔁 Restart Quiz"):
                reset_quiz()
            st.markdown("</div>", unsafe_allow_html=True)

with tabs[1]:
    st.markdown("<h2>📉 Weak Topics</h2>", unsafe_allow_html=True)

    if not st.session_state.weak_topics:
        st.write("No weak topics yet. Keep taking quizzes to identify weak areas.")
    else:
        # Sort weak topics by lowest score ascending
        sorted_weak = sorted(st.session_state.weak_topics.items(), key=lambda x: x[1])
        # Show top 10 weak topics
        top_weak = sorted_weak[:10]

        weak_data = []
        for (topic, diff), score_val in top_weak:
            weak_data.append({
                "Topic": topic.title(),
                "Difficulty": diff.title(),
                "Lowest Score": f"{score_val} (out of quiz length varies)"
            })

        weak_df = pd.DataFrame(weak_data)
        st.dataframe(weak_df)

    st.markdown("""
    <p style='font-size:14px; color:#6b7280;'>
    *Weak topics are updated based on your quiz results. If you improve on a weak topic, it will be removed from this list automatically.*
    </p>
    """, unsafe_allow_html=True)

