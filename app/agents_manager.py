

import json
from openai import OpenAI

from config import Config

from tavily import TavilyClient


class Agent:
    def __init__(self, name, initial_prompt, model="gpt-4o", description=None, metadata=None, messages=[]):
        self.name = name
        self.initial_prompt = initial_prompt
        self.model = model
        self.description = description
        self.metadata = metadata
        self.messages = messages
        self.openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)


    def ask(self, message):
        self.messages.append({"role": "user", "content": message})
        completion = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=self.messages,
        )
    
        # Here you would process the message and generate a response
        # For now, we'll just echo it back with a mock delay
        response = completion.choices[0].message.content
        self.messages.append({"role": "assistant", "content": response})
        return response


class NewsChatAgent(Agent):
    def __init__(self, name, context, model="gpt-4o", description=None, metadata=None, initial_prompt=None):
        initial_prompt =  initial_prompt or  """
You are an AI assistant. You will receive a context window containing various pieces of information
that may or may not be relevant to the user's query. The user will ask you a question. You should
answer the user's question using only the information contained in the context window. If the 
answer cannot be determined from the context, respond with: "I'm sorry, but I don't have enough
information to answer that." Do not invent details, and do not provide information that is not 
supported by the context window. If the user's question requires an explanation, use the relevant
data from the context window to support your response. You must not provide any information that
is not present or cannot be clearly inferred from the context window.
    """
        messages = [
            {"role": "system", "content": initial_prompt},
            {"role": "assistant", "content": "context window: " + context},
        ]
        super().__init__(name, initial_prompt, model, description, metadata, messages)


tools = [{
    "type": "function",
    "function": {
        "name": "search_internet",
        "description": "Search the internet for the answer to the user's question.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query to search the internet for."
                }
            },
            "required": [
                "query"
            ],
            "additionalProperties": False
        },
        "strict": True
    }
}]


class SmarterNewsChatAgent(NewsChatAgent):
    def __init__(self, name, context, model="gpt-4o", description=None, metadata=None):
        self.tavily_client = TavilyClient(api_key=Config.TAVILY_API_KEY)

        initial_prompt = """
        You are an AI assistant that follows a ReAct (Reason + Act) pattern. You have access to a function called "search_internet" that can look up additional information if the provided context is insufficient.

Your instructions:

1. You will receive a "context window" that may or may not contain relevant information about the user’s query.

2. The user will ask you a question. You must attempt to answer using **only** the information in the context window.

3. If the user’s question cannot be answered from the context, or if the user explicitly wants more information than what the context offers, you should call the "search_internet" function by outputting:
   
   Thought: ...
   Action: search_internet(query="your query here")

   Once the function’s result is returned (Observation), incorporate that new information into your reasoning.

4. If, after using the context and (if necessary) searching the internet, you still do not have enough information to answer the question, respond with:
   "I'm sorry, but I don't have enough information to answer that."

5. Never invent details that are not present in the context or found through the "search_internet" function. 
   - If the information cannot be found or clearly inferred, you **must** say you do not have enough information.

6. Format your chain-of-thought using the ReAct style:
   - Thought: A brief internal reasoning step (private).
   - Action: Any function call if needed (e.g., search_internet). 
   - Observation: The function result.
   - Thought: Updated reasoning after seeing the observation.
   - Final Answer: Your final response to the user, strictly following the rules above.

7. If you have sufficient information from the context (and do not need to search), skip the function call and produce your final answer directly.

8. Keep your final answer concise, direct, and based on the validated information from the context or from the search function.

Example Format:

Thought: I need to see if the context has the info.  
Action: search_internet(query="Additional info if needed")  
Observation: [Results returned by search_internet]  
Thought: Now I have the data I need.  
Final Answer: [Your final response to the user]
"""
        initial_prompt_v2 = """
        You are an AI assistant that follows a ReAct (Reason + Act) pattern. You have access to a function called "search_internet" that can look up additional information if the provided context is insufficient.

Your instructions:

1. You will receive a "context window" that may or may not contain relevant information about the user’s query.

2. The user will ask you a question. You must attempt to answer using **only** the information in the context window.

3. If the user’s question cannot be answered from the context, or if the user explicitly wants more information than what the context offers, you should call the "search_internet" function.:
   The result will be added to the context window and you will incorporate it into your reasoning.
  
4. If, after using the context and (if necessary) searching the internet, you still do not have enough information to answer the question, respond with:
   "I'm sorry, but I don't have enough information to answer that."

5. Never invent details that are not present in the context or found through the "search_internet" function. 
   - If the information cannot be found or clearly inferred, you **must** say you do not have enough information.

8. Keep your final answer concise, direct, and based on the validated information from the context or from the search function.

"""
        super().__init__(name, context, model, description, metadata, initial_prompt=initial_prompt_v2)

    def ask(self, message):
        self.messages.append({"role": "user", "content": message})
        counter = 0
        while counter < 20:
            counter += 1

            completion = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=self.messages,
                tools=tools,
            )
        
            if completion.choices[0].message.tool_calls:
                tool_call = completion.choices[0].message.tool_calls[0]
                args = json.loads(tool_call.function.arguments)

                result = self.search_internet(args["query"])

                self.messages.append(completion.choices[0].message)  # append model's function call message
                self.messages.append({                               # append result message
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result)
                })
                # Here you would process the message and generate a response
            else:
                response = completion.choices[0].message.content
                self.messages.append({"role": "assistant", "content": response})

                print("####", self.messages)
                return response

    def search_internet(self, query):
        response = self.tavily_client.search(query)
        return response

class AgentManager:
    def __init__(self):
        self.agents = {}

    def get_agent(self, name):
        return self.agents.get(name)

    def add_agent(self, agent):
        self.agents[agent.name] = agent

    def remove_agent(self, name):
        del self.agents[name]
