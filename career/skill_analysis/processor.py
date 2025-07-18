import json
import pandas as pd
import re
from sentence_transformers import SentenceTransformer, util
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

with open("label_role.json") as f:
    label_role = json.load(f)

with open("skills.json") as f:
    skills_dict = json.load(f)

df = pd.read_csv("extracted_data.csv")

category_map_lower = {cat.lower(): cat.lower() for cat in df['Category'].dropna().unique()}

roles = list(label_role.keys())
model = SentenceTransformer("all-MiniLM-L6-v2")
role_embeddings = model.encode(roles, convert_to_tensor=True)

def match_role(text):
    if not text or str(text).strip() == "":
        return "unknown", "unknown", 0.0
    resume_embedding = model.encode(str(text), convert_to_tensor=True)
    scores = util.cos_sim(resume_embedding, role_embeddings)[0]
    best_idx = scores.argmax().item()
    best_score = scores[best_idx].item()
    matched_role = roles[best_idx]
    matched_domain = label_role.get(matched_role, "unknown").lower()
    if best_score < 0.4:
        return "unknown", "unknown", round(best_score, 3)
    return matched_role, matched_domain, round(best_score, 3)

all_skills = set(skill for skills in skills_dict.values() for skill in skills)

def extract_skills(text):
    found_skills = []
    if isinstance(text, str):
        text_lower = text.lower()
        for skill in all_skills:
            if re.search(r'\b' + re.escape(skill.lower()) + r'\b', text_lower):
                found_skills.append(skill)
    return found_skills

def process_resume_row(row):
    resume_text = f"{row['job_title']} {row['Resume_str']}"
    matched_role, matched_domain, sim_score = match_role(resume_text)
    matched_skills = extract_skills(row['Resume_str'])
    return pd.Series({
        "Matched Role": matched_role,
        "Matched Domain": matched_domain,
        "Similarity Score": sim_score,
        "Matched Skills": ", ".join(matched_skills)
    })

results_df = df.copy()
results_df = results_df.join(results_df.apply(process_resume_row, axis=1))

results_df.to_csv("resume_skill_role_analysis.csv", index=False)
print("Output saved to: resume_skill_role_analysis.csv")

results_df['Category_mapped'] = results_df['Category'].str.lower().str.strip().map(category_map_lower)
results_df['Matched Domain_clean'] = results_df['Matched Domain'].str.lower().str.strip()

results_df = results_df[
    results_df['Category_mapped'].notnull() &
    (results_df['Matched Domain_clean'] != 'unknown')
]

accuracy = accuracy_score(results_df['Category_mapped'], results_df['Matched Domain_clean'])
print(f"\nMapped Accuracy: {accuracy:.2%}")

print("\nClassification Report:")
print(classification_report(results_df['Category_mapped'], results_df['Matched Domain_clean']))

print("\nConfusion Matrix:")
print(confusion_matrix(results_df['Category_mapped'], results_df['Matched Domain_clean']))

