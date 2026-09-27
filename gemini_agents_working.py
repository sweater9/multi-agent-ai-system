#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY not found in .env")
    exit(1)

genai.configure(api_key=api_key)

class GeminiAgent:
    def __init__(self, name, system_prompt):
        self.name = name
        self.system_prompt = system_prompt
        self.model = genai.GenerativeModel('gemini-3.8-flash')
    
    def run(self, task, context=""):
        print(f"\n{'='*60}\nRunning {self.name.upper()} Agent...\n{'='*60}")
        
        if context:
            prompt = f"{self.system_prompt}\n\nContext:\n{context}\n\nTask: {task}"
        else:
            prompt = f"{self.system_prompt}\n\nTask: {task}"
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=2048,
                    temperature=0.7,
                )
            )
            result = response.text
            print(f"\n✅ {self.name} Complete\n{result[:300]}...\n")
            return result
        except Exception as e:
            print(f"❌ Error: {e}")
            raise

def main():
    agents = {
        "research": GeminiAgent("research", "You are a Research Agent. Gather information and best practices."),
        "analysis": GeminiAgent("analysis", "You are an Analysis Agent. Analyze findings and provide insights."),
        "development": GeminiAgent("development", "You are a Development Agent. Plan architecture and solution."),
        "coding": GeminiAgent("coding", "You are a Coding Agent. Write complete, production-ready code."),
        "qa": GeminiAgent("qa", "You are a QA Agent. Review code and ensure quality."),
    }
    
    user_request = "Build a water intake tracker web app with React"
    
    print("\n" + "="*60)
    print("MULTI-AGENT AI SYSTEM (Gemini 3.8 Flash)")
    print("="*60 + f"\nRequest: {user_request}\n")
    
    results = {}
    research_output = agents["research"].run(user_request)
    results["research"] = research_output
    
    analysis_output = agents["analysis"].run("Analyze the research", context=research_output[:800])
    results["analysis"] = analysis_output
    
    development_output = agents["development"].run("Create development plan", context=analysis_output[:800])
    results["development"] = development_output
    
    coding_output = agents["coding"].run("Write the code", context=development_output[:800])
    results["coding"] = coding_output
    
    qa_output = agents["qa"].run("Review and provide feedback", context=coding_output[:800])
    results["qa"] = qa_output
    
    os.makedirs("projects/water_tracker", exist_ok=True)
    for name, output in results.items():
        with open(f"projects/water_tracker/{name}.md", "w") as f:
            f.write(f"# {name.upper()} Agent Output\n\n{output}")
        print(f"✅ Saved: projects/water_tracker/{name}.md")
    
    print(f"\n{'='*60}")
    print("✅ WORKFLOW COMPLETE")
    print(f"{'='*60}")
    print(f"\n📁 Check outputs at: projects/water_tracker/")

if __name__ == "__main__":
    main()
