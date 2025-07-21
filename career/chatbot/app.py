from flask import Flask, request, jsonify, render_template
import pandas as pd
from googlesearch import search
import os # Import the os module to check for file existence

app = Flask(__name__)

# --- Data Loading with Error Handling ---
CSV_FILE = "/Users/yashi/Desktop/career_consulting/career_consulting/career/skill_analysis/resume_skill_role_analysis.csv"
df_sorted = None

try:
    # Check if the CSV file exists before trying to read it
    if not os.path.exists(CSV_FILE):
        print(f"--- FATAL ERROR: The file '{CSV_FILE}' was not found. ---")
        print("--- Please make sure the CSV file is in the same directory as app.py ---")
        df_sorted = pd.DataFrame() # Create an empty DataFrame to prevent further errors
    else:
        df = pd.read_csv(CSV_FILE)
        # Check if the required column exists
        if "Similarity Score" not in df.columns:
             print(f"--- FATAL ERROR: The required column 'Similarity Score' is not in '{CSV_FILE}'. ---")
             df_sorted = pd.DataFrame()
        else:
            df_sorted = df.sort_values(by="Similarity Score", ascending=False).reset_index(drop=True)
            print("--- CSV file loaded and sorted successfully. ---")

except Exception as e:
    print(f"--- An unexpected error occurred during data loading: {e} ---")
    df_sorted = pd.DataFrame() # Ensure df_sorted is an empty DataFrame on any error

# --- Session Management ---
# Using a dictionary for the session is simple for this example
session = {"current_index": 0, "rejected_indices": []}

def format_recommendation(row):
    """Formats a DataFrame row into a readable string."""
    return (
        f"<strong>Job Title:</strong> {row.get('job_title', 'N/A')}<br>"
        f"<strong>Matched Role:</strong> {row.get('Matched Role', 'N/A')}<br>"
        f"<strong>Domain:</strong> {row.get('Matched Domain', 'N/A')}<br>"
        f"<strong>Similarity Score:</strong> {row.get('Similarity Score', 0):.2f}<br><br>"
        "You can ask: 'Why was I recommended this?', 'Show me courses', or 'Next'."
    )

@app.route("/")
def index():
    """Serves the main HTML page."""
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    """Handles the main chat logic."""
    try:
        # Check if the DataFrame is empty (due to loading errors)
        if df_sorted.empty:
            return jsonify({"response": "Sorry, I cannot provide recommendations right now. The required data file is missing or invalid. Please check the server logs."})

        data = request.get_json(silent=True)
        user_message = data.get("message", "").strip().lower() if data else ""
        
        if not user_message:
            return jsonify({"response": "Please enter a valid message."})

        # Make sure the current index is within bounds
        if not (0 <= session["current_index"] < len(df_sorted)):
            return jsonify({"response": "No more recommendations available."})

        row = df_sorted.iloc[session["current_index"]]

        if user_message in ["start", "hi", "hello", "hey"]:
            response_text = f"Hi! Here is your first recommended role:<br><br>{format_recommendation(row)}"
            return jsonify({"response": response_text})

        if "why" in user_message:
            experience = row.get("experience", "Not specified")
            matched_skills = row.get("Matched Skills", "")
            skills_list = [s.strip() for s in matched_skills.split(",") if s.strip()]
            skills_text = "<br>".join(f"- {skill}" for skill in skills_list) if skills_list else "Not specified"
            response_text = (
                "You were recommended this role because:<br><br>"
                f"<strong>Similarity Score:</strong> {row['Similarity Score']:.2f}<br>"
                f"<strong>Experience:</strong> {experience}<br>"
                f"<strong>Key Skills:</strong><br>{skills_text}"
            )
            return jsonify({"response": response_text})

        if any(word in user_message for word in ["next", "another", "not satisfied"]):
            session["rejected_indices"].append(session["current_index"])
            next_index = session["current_index"] + 1
            
            # Find the next valid index that hasn't been rejected
            while next_index < len(df_sorted) and next_index in session["rejected_indices"]:
                next_index += 1
            
            if next_index >= len(df_sorted):
                return jsonify({"response": "Sorry, there are no more recommendations available."})
            
            session["current_index"] = next_index
            new_row = df_sorted.iloc[next_index]
            return jsonify({"response": f"Understood. Here is your next recommendation:<br><br>{format_recommendation(new_row)}"})

        if "courses" in user_message or "improve" in user_message:
            try:
                query = f"online courses to become {row['Matched Role']}"
                # The 'googlesearch' library can be unreliable. This will catch issues.
                course_links = list(search(query, num_results=3))
                links_text = "<br>".join([f"- <a href='{link}' target='_blank' rel='noopener noreferrer'>{link}</a>" for link in course_links])
                return jsonify({"response": f"Here are some courses that might help:<br><br>{links_text}"})
            except Exception as e:
                print(f"Error fetching courses from Google Search: {e}")
                return jsonify({"response": "Sorry, I had trouble finding courses at the moment. Please try again later."})

        return jsonify({"response": "I didn't quite understand. You can ask 'Why?', 'Show me courses', or say 'Next'."})

    except Exception as e:
        # This is a general catch-all for any other unexpected errors.
        print(f"--- An unexpected error occurred in /chat: {e} ---")
        return jsonify({"response": "Sorry, a critical error occurred on the server. Please check the logs."}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
