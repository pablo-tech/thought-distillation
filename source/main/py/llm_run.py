import time

from llm_step import InterimStep, FinishStep


class RunJourney():

    def __init__(self):
        self.agent_scratchpad = []

    def add_run(self, agent_action, step_observation):
        if isinstance(step_observation, str):
            step_observation = step_observation.strip()
        step = (agent_action, step_observation)
        self.agent_scratchpad.append(step)

    def __str__(self, observation_prefix="Observation: "):
        thoughts = ""
        for thought_action, observation in self.agent_scratchpad:
            thought_action = thought_action.get_log().strip()
            thoughts += f"{thought_action}" + "\n"
            thoughts += f"{observation_prefix}" + str(observation) + "\n"
        return thoughts.strip()
    

class RunError():

    def __init__(self):
        self.error_log = []

    def error_input(self, error, input):
        self.error_log.append((error, input))

    def get_error_input(self):
        return self.error_log
    
    def __str__(self):
        s = ""
        for error, input in self.error_log:
          s += "\t context_values: " + str(input) + "\n"
          s += "\t exception: " + str(error)
        return s.strip()
    

class RunMeasure():

    def __init__(self):
        self.iteration_count = 0
        self.hallucination_count = 0
        self.input_len = []
        self.output_len = []
        self.model_time = []
        self.tool_time = []

    def add_run(self, is_hallucination, 
                input_len, output_len,
                model_time):
        self.iteration_count += 1
        if is_hallucination:
            self.hallucination_count += 1
        self.input_len.append(input_len)
        self.output_len.append(output_len)
        self.model_time.append(model_time)

    def get_iteration_count(self):
        return self.iteration_count
    
    def get_hallucination_count(self):
        return self.hallucination_count

    def get_min_input_len(self):
        try:
            return min(self.input_len)
        except:
            return 0

    def get_max_input_len(self):
        try:
            return max(self.input_len)
        except:
            return 0

    def get_total_input_len(self):
        try:
            return sum(self.input_len)
        except:
            return 0

    def get_min_output_len(self):
        try:
            return min(self.output_len)
        except:
            return 0

    def get_max_output_len(self):
        try:
            return max(self.output_len)
        except:
            return 0

    def get_total_output_len(self):
        try:
            return sum(self.output_len)
        except:
            return 0

    def get_min_model_time(self):
        try:
            return min(self.model_time)
        except:
            return 0

    def get_max_model_time(self):
        try:
            return max(self.model_time)
        except:
            return 0

    def get_total_model_time(self):
        try:
            return sum(self.model_time)
        except:
            return 0 

    def __str__(self):
        s = ""
        s += "\t iteration_count: " + str(self.get_iteration_count()) + "\n"
        s += "\t hallucination_count: " + str(self.get_hallucination_count()) + "\n"
        s += "\t min_input_len: " + str(self.get_min_input_len()) + "\n"        
        s += "\t max_input_len: " + str(self.get_max_input_len()) + "\n"
        s += "\t total_input_len: " + str(self.get_total_input_len()) + "\n"
        s += "\t min_output_len: " + str(self.get_min_output_len()) + "\n"        
        s += "\t max_output_len: " + str(self.get_max_output_len()) + "\n"
        s += "\t total_output_len: " + str(self.get_total_output_len()) + "\n"
        s += "\t min_model_time: " + "{:.3f}".format(self.get_min_model_time()) + "\n"        
        s += "\t max_model_time: " + "{:.3f}".format(self.get_max_model_time()) + "\n"
        s += "\t total_model_time: " + "{:.3f}".format(self.get_total_model_time()) + "\n"
        return s
    
    
class RunAnswer():

    def __init__(self, 
                run_step, run_journey, 
                run_error, run_measure):
        ### save
        self.agent_answer = None
        self.run_journey = run_journey
        self.run_error = run_error
        self.run_measure = run_measure
        ### summarize
        self.is_finish = False
        self.log = ''
        if isinstance(run_step, InterimStep):
            self.agent_answer = run_step.get_log()
        if isinstance(run_step, FinishStep):
            self.agent_answer = run_step.get_answer()
            self.log = run_step.get_log()
            self.is_finish = True

    def get_answer(self):
        return self.agent_answer
        
    def get_finish(self):
        return self.is_finish
    
    def get_thought_action(self):
        return self.log
    
    def get_run_measure(self):
        return self.run_measure

    def __str__(self):
        s = "RUN_DETAIL=>" + "\n"
        s += " - RUN_NORMAL: " + str(self.get_finish()).strip() + "\n"
        s += " - RUN_ANSWER: " + str(self.get_answer()).strip() + "\n"
        s += " - RUN_JOURNEY: " + "\n"
        s += self.run_journey.__str__().strip() + "\n"
        s += " - RUN_MEASURE => " + "\n"
        s += self.run_measure.__str__().strip() + "\n"        
        s += " - RUN_EXCEPTION => " + "\n"
        s += self.run_error.__str__().strip() + "\n"
        return s
    

class ModelRun():

    def __init__(self):
        self.run_journey = RunJourney()
        self.run_error = RunError()
        self.run_measure = RunMeasure()


class ToolRun(ModelRun):

    def __init__(self):
        super().__init__()

    def invoke(self, query, func):
        model_step = None
        try:
            is_hallucination = False
            model_start = time.time()
            answer = func(query)
            input_len, output_len = len(query), len(answer)
            model_step = FinishStep(answer, action_log="")
            model_end = time.time()        
            self.run_measure.add_run(is_hallucination, input_len, output_len, 
                                     model_end-model_start)
            self.run_journey.add_run(model_step, model_step.get_answer()) 
        except Exception as e:
                self.run_error.error_input(str(e), query)
        return RunAnswer(model_step, self.run_journey, 
                         self.run_error, self.run_measure)        