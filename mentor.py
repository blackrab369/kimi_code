import time
from collections import deque
from builder import client  # Reuse the configured OpenAI/Moonshot client

class MentorAgent:
    def __init__(self):
        self.recent_events = deque(maxlen=20) # Keep last 20 events
        self.last_tip_time = 0
        self.tip_cooldown = 45 # Seconds between tips
        
    def sanitize_event(self, text):
        import re
        # Redact OpenAI/Sk keys
        text = re.sub(r'sk-[a-zA-Z0-9]{20,}', 'sk-[REDACTED]', text)
        # Redact generic bearer tokens
        text = re.sub(r'Bearer [a-zA-Z0-9\-\._~]+', 'Bearer [REDACTED]', text)
        return text
    
    def log_event(self, event):
        """Log an event (e.g., 'Build started', 'User edited main.py')"""
        timestamp = time.strftime("%H:%M:%S")
        safe_event = self.sanitize_event(str(event))
        self.recent_events.append(f"[{timestamp}] {safe_event}")
        
    def generate_tip(self, project_name):
        """
        Decide if a tip is needed based on recent events.
        Returns: tip_string or None
        """
        now = time.time()
        if now - self.last_tip_time < self.tip_cooldown:
            return None
            
        if not self.recent_events:
            return None
            
        # Context for LLM
        events_str = "\n".join(list(self.recent_events))
        
        prompt = f"""
        You are a helpful Senior Software Engineer Mentor watching a developer work on project '{project_name}'.
        
        Recent Activity Log:
        {events_str}
        
        Task:
        - Analyze the user's recent actions.
        - If they are doing well, offer brief encouragement.
        - If they seem stuck (repeated errors), offer a specific specific tip.
        - If nothing notable is happening, return "NO_TIP".
        - KEEP IT SHORT. One sentence only. Casual and friendly.
        
        Response:
        """
        
        try:
            response = client.chat.completions.create(
                model="kimi-k2-0905-preview",
                messages=[
                    {"role": "system", "content": "You are a helpful coding mentor. Output only the tip text or NO_TIP."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=60
            )
            
            tip = response.choices[0].message.content.strip()
            
            if "NO_TIP" in tip or len(tip) < 5:
                # Random chance to say something generic if idle? No, let's stay quiet to avoid annoyance.
                return None
            
            self.last_tip_time = now
            # Clear events so we don't comment on them again? 
            # Or keep them for context but maybe clear half?
            # Let's keep them, the time window filters relevance.
            
            return tip
            
        except Exception as e:
            print(f"Mentor Error: {e}")
            return None

# Global Instance
mentor = MentorAgent()
