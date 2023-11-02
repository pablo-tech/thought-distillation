import os

from langchain import Wikipedia
from langchain.agents import Tool
from langchain.agents.react.base import DocstoreExplorer

from langchain.agents import tool
from langchain.tools.render import render_text_description

from tool_search import SearchFactory
from tool_math import MathFactory
from tool_conversation import ConversationFactory


class ToolFactory():
    # https://python.langchain.com/docs/modules/agents/tools/custom_tools

    def __init__(self, is_verbose=True):
        self.is_verbose = is_verbose
        self.doc_store = DocstoreExplorer(Wikipedia())

    def tool_summaries(cls, tool_set):
        return render_text_description(tool_set)

    def tool_names(cls, tool_set):
        return ", ".join([t.name for t in tool_set])

    def basic_tools(self, completion_llm):
        return MathFactory.math_tools(completion_llm) +\
               SearchFactory.serp_search_tools(completion_llm) +\
               ConversationFactory.conversation_tools(completion_llm)
                
    def wikipedia_tools(self, completion_llm=None):
        return [
          Tool(
              name="Search",
              func=self.doc_store.search,
              description="useful to search for the truth"
          ),
          Tool(
              name="Lookup",
              func=self.doc_store.lookup,
              description="useful to lookup facts"
          )
        ]
    
    @tool
    def get_word_length(word):
        """Returns the length of a word."""
        return len(word)

    def string_tools():
        return [ToolFactory.get_word_length]


