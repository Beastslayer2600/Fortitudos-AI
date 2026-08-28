
import llm
import sys

def test_adjudication_assist():
    system_prompt = """You are a master drama adjudicator. 
Your task is to provide constructive feedback based on a score (1-10) and an observation.
Provide feedback in three categories:
1. Competence: What the performer did well technically.
2. Agency: How the performer took ownership or showed initiative.
3. Challenge: A specific technical goal for next time.

Keep each category to one or two concise sentences.
"""
    
    user_input = "Criterion: Voice & Speech. Score: 4. Observation: The performer was barely audible in the back row and stumbled over the plosive sounds in the first stanza."
    
    print("Testing Adjudication Assist...")
    print(f"Input: {user_input}")
    
    try:
        response = llm.chat(system_prompt, user_input)
        print("\nAI Response:")
        print(response)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_adjudication_assist()
