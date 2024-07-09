from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_community.utilities import SQLDatabase
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
import streamlit as st

def init_database(user: str, password: str, host: str, port: str, database: str) -> SQLDatabase:
    db_uri = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
    return SQLDatabase.from_uri(db_uri)

def get_sql_chain(db):
    template = """
    You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
    Based on the table schema below, write a SQL query that would answer the user's question. Take the conversation history into account.
    
    <SCHEMA>{schema}</SCHEMA>
    
    Conversation History: {chat_history}
    
    Write only the SQL query and nothing else. Do not wrap the SQL query in any other text, not even backticks.
    
    For example:
    Question: which 3 artists have the most tracks?
    SQL Query: SELECT ArtistId, COUNT(*) as track_count FROM Track GROUP BY ArtistId ORDER BY track_count DESC LIMIT 3;
    Question: Name 10 artists
    SQL Query: SELECT Name FROM Artist LIMIT 10;
    
    Your turn:
    
    Question: {question}
    SQL Query:
    """
    
    prompt = ChatPromptTemplate.from_template(template)
    
    llm = ChatGroq(model="mixtral-8x7b-32768", temperature=0)
    
    def get_schema(_):
        return db.get_table_info()
    
    return (
        RunnablePassthrough.assign(schema=get_schema)
        | prompt
        | llm
        | StrOutputParser()
    )

def get_response(user_query: str, db: SQLDatabase, chat_history: list):
    sql_chain = get_sql_chain(db)
    
    template = """
    You are a data analyst at a company. You are interacting with a user who is asking you questions about the company's database.
    Based on the table schema below, question, sql query, and sql response, write a natural language response.
    <SCHEMA>{schema}</SCHEMA>

    Conversation History: {chat_history}
    SQL Query: <SQL>{query}</SQL>
    User question: {question}
    SQL Response: {response}"""
    
    prompt = ChatPromptTemplate.from_template(template)
    
    llm = ChatGroq(model="mixtral-8x7b-32768", temperature=0)
    
    chain = (
        RunnablePassthrough.assign(query=sql_chain).assign(
            schema=lambda _: db.get_table_info(),
            response=lambda vars: db.run(vars["query"]),
        )
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return chain.invoke({
        "question": user_query,
        "chat_history": chat_history,
    })

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        AIMessage(content="Hello! I'm a SQL assistant named SQLInsight. Click on the settings icon then connect to the database and start chatting."),
    ]

load_dotenv()

st.set_page_config(page_title="Chat with SQLInsight", page_icon=":speech_balloon:", layout="wide")


# Toggle sidebar visibility
if 'show_settings' not in st.session_state:
    st.session_state.show_settings = False

# Use a button with an emoji as a settings icon
if st.button("⚙️"):
    st.session_state.show_settings = not st.session_state.show_settings

# Sidebar
if st.session_state.show_settings:
  with st.sidebar:
      st.subheader("Settings")
      st.write("This is a chat application using MySQL. Click on the settings icon then connect to the database and start chatting.")
      
      st.text_input("Host", value="localhost", key="Host")
      st.text_input("Port", value="3306", key="Port")
      st.text_input("User", value="root", key="User")
      st.text_input("Password", type="password", value="passcode", key="Password")
      st.text_input("Database", value="RestaurantMenu", key="Database")
      
      if st.button("Connect"):
          with st.spinner("Connecting to database..."):
              db = init_database(
                  st.session_state["User"],
                  st.session_state["Password"],
                  st.session_state["Host"],
                  st.session_state["Port"],
                  st.session_state["Database"]
              )
              st.session_state.db = db
              st.success("Connected to database!")

# Main Title
st.title("💬 Chat with SQLInsight")  
# Display chat history
for message in st.session_state.chat_history:
    if isinstance(message, AIMessage):
        with st.chat_message("AI"):
            st.markdown(f"🟢 {message.content}")
    elif isinstance(message, HumanMessage):
        with st.chat_message("Human"):
            st.markdown(f"✍️ {message.content}")

# Define a list of specific words and their responses
specific_words_responses = {
    "ok": "Got it! Anything else I can help with?",
    "thank you": "You're welcome! Happy to assist.",
    "alright": "Okay, let me know if there's anything else.",
    # Add more words and responses as needed
}

# User input
user_query = st.chat_input("Type a message...")
if user_query:
    st.session_state.chat_history.append(HumanMessage(content=user_query))
    
    with st.chat_message("Human"):
        st.markdown(f"✍️ {user_query}")
        
    with st.chat_message("AI"):
        # Check if the user query matches any specific words
        if user_query.lower() in specific_words_responses:
            response = specific_words_responses[user_query.lower()]
        else:
            response = get_response(user_query, st.session_state.db, st.session_state.chat_history)
        st.markdown(f"💡 {response}")
        
    st.session_state.chat_history.append(AIMessage(content=response))
