A website (built during a Hackathon organized by SGU) to support learning my "Pháp Luật Đại Cương" subject more effectively: 

   - Description: A chatbot web app like Gemini that allows users to ask questions related to the 2015 Civil Code.  
   - Integrated AI Q&A using Gemini API.  
   - Supabase: Created a client with `supabaseUrl` and `supabaseKey` to interact with the database, including configurations like `autoRefreshToken`, `persistSession`, and `detectSessionInUrl` for Google Auth.  
   - Frontend built with React: login/logout interface, chat input, and history display.  
   - Backend built with Python (FastAPI): extract PDF data → JSON → FAISS (vector data) for chatbot handling. REST API connects frontend and backend.  
   - Technologies: React, Python, Supabase, Gemini API, RAG System.  
To run this application on your personal server, you need have all full requirements in .env_example file, and all lib in requirments file, then run uvicorn main:app --host 127.0.0.1 --port 8000 --reload in backend
and npm start in frontend react
