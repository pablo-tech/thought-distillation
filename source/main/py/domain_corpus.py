import os, json
import uuid

from collections import defaultdict

from langchain.chat_models import ChatOpenAI

from helper_index import JsonFlatner


class JsonReader():

    def read_file(file_name, dir_path):
        try:
            print("READING=" + dir_path + file_name)
            f = open(dir_path + file_name)
            corpus_json = json.load(f)
            print("SUCCESS=" + str(file_name) + " COUNT=" + str(len(corpus_json)))
            f.close()
            return corpus_json
        except Exception as e:
            print("JSON_READER_ERROR=" + str(e))

    def list_files(dir_path):
        files = []
        for listed_item in os.listdir(dir_path):
            if "json" in listed_item:
                item_path = os.path.join(dir_path, listed_item)
                if os.path.isfile(item_path):
                    files.append(listed_item)        
        return files


class DomainDataset():

    def __init__(self, dir_path):
        file_names = JsonReader.list_files(dir_path)
        self.corpus = self.read_corpus(dir_path, file_names)

    def read_corpus(self, dir_path, file_names):
        print("\n\n" + "|| ")
        print("|| READ CORPUS")
        print("||")
        print("dir_path=" + str(dir_path) + "\t" + "file_names=" + str(file_names))

        corpus = {}
        for file_name in sorted(file_names):
            file_corpus = JsonReader.read_file(file_name, dir_path)
            corpus[file_name] = file_corpus
        return corpus
    
    def get_subdomains(self):
        return self.corpus.keys()
    
    def subdomain_corpus(self, domain_name):
        return self.corpus[domain_name]
    

class GiftDataset(DomainDataset):

    def __init__(self, dir_path):
        super().__init__(dir_path)
    
    def get_corpus(self, domain_name):
        corpus = {}
        for item in self.subdomain_corpus(domain_name)['results']:
            corpus[str(uuid.uuid1())] = item
        return corpus     

    def is_valid_json(self, dict):
        try:
            eval(json.loads(json.dumps(str(dict))))       
            return True
        except Exception as e:
            print("INVALID_DICT=" + str(dict))
        return False
    

class TvDataset(DomainDataset):

    def __init__(self, dir_path):
        super().__init__(dir_path)
    
    def get_corpus(self, domain_name):
        return { str(k): str(v) for k, v 
                in self.subdomain_corpus(domain_name)
                if self.is_valid_json(v) }


class AcDataset(DomainDataset):

    def __init__(self, dir_path):
        super().__init__(dir_path)

    def get_corpus(self, domain_name):
        return self.subdomain_corpus(domain_name)


class DomainDatasets():

    def __init__(self):
        gift_data = GiftDataset(dir_path="/content/drive/MyDrive/StanfordLLM/gift_qa/")
        tv_data = TvDataset(dir_path="/content/drive/MyDrive/StanfordLLM/tv_qa/")
        ac_data = AcDataset(dir_path="/content/drive/MyDrive/StanfordLLM/ac_qa/")
        self.data_sets = [gift_data, tv_data, ac_data]

    def get_data_sets(self):
        return self.data_sets
    
    
class DomainIngestion(DomainDatasets):

    def __init__(self, n, completion_llm, is_verbose):
        super().__init__()
        self.n = n
        self.completion_llm = completion_llm
        self.is_verbose = is_verbose
        self.raw_data = {}
        self.domain_raw = defaultdict(list)
        self.domain_clean = defaultdict(list)
        for dataset in self.get_data_sets():
            self.ingest_dataset(dataset)

    def ingest_dataset(self, dataset):
        i = 0
        for subdomain_name in dataset.get_subdomains():
            subdomain_corpus = dataset.get_corpus(subdomain_name)
            for key, item in subdomain_corpus.items():
                if self.n is not None and i >= self.n:
                    return
                self.raw_data[key] = item
                self.domain_raw[subdomain_name].append(item)
                try:
                    flat = self.flatten_json(item)
                    validated = eval(json.loads(json.dumps(str(flat))))
                    self.domain_clean[subdomain_name].append(validated)
                    i += 1
                    print("...")
                except Exception as e:
                    print("FLATEN_ERROR=" + str(e) + " " + str(item))

    def flatten_json(self, item):
        flatner = JsonFlatner(self.completion_llm, self.is_verbose)
        clean = flatner.item_summary(str(item))
        if isinstance(self.completion_llm, ChatOpenAI):
            clean = clean.content
        return json.loads(clean)
    
    def get_raw(self):
        return self.raw_data

    def get_product(self, key):
        return self.get_raw()[key]

    def get_domain_raw(self):
        return self.domain_raw

    def get_domain_clean(self):
        return self.domain_clean