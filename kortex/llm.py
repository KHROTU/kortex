import ollama
import json
import yaml
import re


class LLMClient:
    def __init__(self, tool_registry, config_path="kortex/config.yaml"):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        self.model = config['ollama_model']
        self.tool_registry = tool_registry
        print(f"LLM Client Initialized with {self.model} and native tool support.")

    def _get_tool_definitions(self):
        tool_definitions = []
        for name, func in self.tool_registry.items():
            doc_lines = func.__doc__.split('\n')
            description = doc_lines[0].strip()
            params_line = next((line for line in doc_lines if "Parameters:" in line), None)
            properties = {}
            if params_line:
                try:
                    params_str = params_line.split("Parameters:")[1].strip()
                    param_spec = json.loads(params_str)
                    for param_name, desc in param_spec.items():
                        properties[param_name] = {"type": "string", "description": desc}
                except (json.JSONDecodeError, IndexError):
                    print(f"Warning: Could not parse parameters for tool '{name}'")
            
            tool_definitions.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {"type": "object", "properties": properties}
                }
            })
        return tool_definitions

    def get_response(self, user_prompt, use_tools=True):
        print(f"LLM processing: '{user_prompt}'")
        
        system_prompt = (
            "You are Kortex, a helpful voice assistant. Your primary function is to provide direct, "
            "natural language answers. Only use a tool if the user's request *explicitly and clearly* "
            "matches one of the available tool descriptions. For simple conversational queries that do not "
            "match any tool (like 'what is your name?' or 'give me a random number'), you MUST provide a "
            "direct text-based answer and MUST NOT call a tool. When asked to 'open' something, prioritize "
            "using the `find_application` tool for application names over `open_website`."
        )
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ]
        
        tools = self._get_tool_definitions() if use_tools else []

        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
                tools=tools,
                stream=False,
                options={'temperature': 0.0}
            )

            if response['message'].get('tool_calls'):
                tool_call = response['message']['tool_calls'][0]['function']
                tool_name = tool_call['name']
                parameters = tool_call['arguments']
                
                if tool_name in self.tool_registry:
                    reformatted_call = {"tool_name": tool_name, "parameters": parameters}
                    print(f"LLM decided to call tool: {reformatted_call['tool_name']}")
                    return {"type": "tool_call", "data": reformatted_call}

            text_response = response['message']['content'].strip()
            return {"type": "text", "data": text_response}

        except Exception as e:
            error_message = f"An error occurred with the LLM: {e}"
            print(error_message)
            return {"type": "text", "data": "I'm sorry, I encountered an error."}