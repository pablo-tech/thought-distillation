from domain_knowledge import DomainSchema
from helper_parser import SummaryTagger, DataTransformer

from collections import defaultdict


class SchemaCreator(DomainSchema):

    def __init__(self, n,
                 domain_name, domain_datasets, 
                 selected_columns, primary_key,
                 completion_llm, is_verbose):
        super().__init__(n=n, 
                         data_sets=domain_datasets,
                         completion_llm=completion_llm,
                         is_verbose=is_verbose)
        self.domain_name = domain_name.upper()
        self.domain_datasets = domain_datasets
        self.selected_columns = selected_columns
        self.primary_key = primary_key
        self.completion_llm = completion_llm
        self.is_verbose = is_verbose

    def get_domain_name(self):
        return self.domain_name

    def create_table(self, table_name, column_names):
        self.execute_query(self.create_sql(table_name, column_names))

    def execute_query(self, create_sql):
        try:
          self.db_cursor.execute(f"DROP TABLE IF EXISTS {self.domain_name};")
          self.db_cursor.execute(create_sql)
          if self.is_verbose:
              print(create_sql)
        except Exception as e:
          print("CREATION_ERROR=" + self.domain_name + " " + str(e) + "\n" + str(create_sql))

    def create_sql(self, table_name, column_names):
        column_names = self.non_primary(self.primary_key, column_names)
        column_names = [",\n" + name + " " + "TEXT NOT NULL" for name in column_names]
        column_names = " ".join(column_names)
        return f"""
    CREATE TABLE {table_name} (
    {self.primary_key} TEXT PRIMARY KEY {column_names}
    ) ;
    """

    def non_primary(self, primary_key, column_names):
        return sorted([name for name in column_names if name!=primary_key]) 
            

class DatasetLoader(SchemaCreator):

    def __init__(self, n, nick_name, domain_name, domain_datasets, 
                 picked_columns, primary_key, 
                 completion_llm, is_verbose=False):
        super().__init__(n, domain_name, domain_datasets, 
                 picked_columns, primary_key, 
                 completion_llm, is_verbose)
        self.nick_name = nick_name
        self.table_name = self.get_domain_name() + "_" + self.nick_name

    def load_items(self):
        columns, rows, insert_sql = self.prepare_load()
        self.execute_load(columns, insert_sql)
        return columns, rows

    def prepare_load(self):
        products, columns = self.get_product_columns()
        # print("PRODUCTS=>" + str(products))
        print("COLUMNS=>" + str(columns))
        rows = DataTransformer.product_strs(products, columns, self.primary_key)
        print("ROWS=>" + str(rows))
        insert_sql = self.get_sql(self.table_name, rows)
        # print("INSERT_SQL=>"+str(insert_sql))
        return columns, rows, insert_sql

    def execute_load(self, columns, insert_sql):
        self.create_table(self.table_name, columns)
        self.get_db_cursor().execute(insert_sql)
        self.get_db_connection().commit()
    
    def get_sql(self, table_name, table_rows):
        return f"""
INSERT INTO {table_name} VALUES {table_rows}
"""    

    def schema_sql(self):
        return self.create_sql(self.get_table_name(), 
                               self.get_columns())
        
    def get_table_name(self):
        return self.table_name

    def get_product_columns(self):
        return self.get_products(), self.get_columns()

    # def get_enums(self):
    #     return self.picked_enums

    def get_enums(self):
        return sorted(list(self.select_enum_values().keys()))
 
    def select_enum_values(self):
        return { k: v for k, v in self.get_enum_values().items()
                if len(v) > 1}
    
    def get_enum_values(self):
        return self.enum_values


class DatasetReducer():

    def __init__(self, primary_key, picked_columns):
        self.primary_key = primary_key
        self.picked_columns = picked_columns

    def unique_columns(self, column_names):
        return [self.primary_key] + [col for col in column_names 
                                     if col!=self.primary_key]

    def columns(self, domain_columns):
        columns = self.unique_columns(domain_columns)
        reduced = [col for col in columns if col in self.picked_columns]
        return DataTransformer.fill_cols(reduced)   


class ContextParser(DatasetLoader):

    def __init__(self, n, domain_name, domain_datasets, 
                 picked_columns, primary_key, price_column,  
                 completion_llm, is_verbose=False):
        super().__init__(n, "CONTEXT", domain_name, domain_datasets, 
                 picked_columns, primary_key, 
                 completion_llm, is_verbose)
        self.ds_reducer = DatasetReducer(primary_key, picked_columns)
        self.context_products = self.reduction_products()
        self.context_columns = self.reduction_columns()
        self.enum_values = DataTransformer.set_enum_values(self.get_columns(),
                                                           self.get_products(),
                                                          [self.primary_key, price_column])

    def get_fewshot_examples(self):
        columns = ", ".join(self.get_columns())
        return f"""        
Question: what ARISTOCRAT products do you have? 
Answer: SELECT {columns} FROM {self.get_table_name()} WHERE brand = 'Aristocrat';
Question: what GESTS products do you have?
Answer: SELECT {columns} FROM {self.get_table_name()} WHERE brand = 'Guess';
Question: what are the cheapest Scharf products?
Answer: SELECT {columns} FROM {self.get_table_name()} WHERE brand = 'Scharf' ORDER BY price ASC;
Question: "what are the cheapest Carpisa watches?"
Answer: SELECT {columns} FROM {self.get_table_name()} WHERE brand = 'Carpisa' AND title LIKE '%watch%' ORDER BY price ASC;
Question: "What is GW0403L2?"
Answer: SELECT {columns} FROM {self.get_table_name()} WHERE title LIKE '%GW0403L2%';
Question: "Bags for men?"
Answer: SELECT {columns} FROM {self.get_table_name()} WHERE title LIKE '%bag%' AND title NOT LIKE '%women%';
Question: "Glassses for women?"
Answer: SELECT {columns} FROM {self.get_table_name()} WHERE title LIKE '%glass%' AND title NOT LIKE '% men%';
"""
    
    def get_products(self):
        return self.context_products

    def get_columns(self):
        return self.context_columns

    def reduction_products(self):
        return self.working_products

    def reduction_columns(self):
        return self.ds_reducer.columns(self.column_names()) 


class DatasetAugmenter():

    def __init__(self, summarize_columns, primary_key,
                 completion_llm, is_verbose):
        self.summary_tagger = SummaryTagger(summarize_columns, primary_key,
                                            completion_llm, is_verbose) 

    def column_products(self, products): 
        columns, products = self.summary_tagger.invoke(products)
        columns = sorted(list(columns.keys()))
        columns = [self.summary_tagger.primary_key] + columns
        return DataTransformer.fill_cols(columns), products


class InferenceParser(DatasetLoader):

    def __init__(self, n, domain_name, domain_datasets, 
                 picked_columns, primary_key, price_column, summarize_columns,  
                 completion_llm, is_verbose=False): 
        super().__init__(n, "INFERENCE", domain_name, domain_datasets, 
                 picked_columns, primary_key,  
                 completion_llm, is_verbose)
        self.ds_augmenter = DatasetAugmenter(summarize_columns, primary_key,
                                             completion_llm, is_verbose)        
        self.inference_columns, self.inference_products =\
                self.augmentation_column_products()
        self.enum_values = DataTransformer.set_enum_values(self.get_columns(),
                                                           self.get_products(),
                                                           [self.primary_key, price_column])        

    def get_fewshot_examples(self):
        columns = ", ".join(self.get_columns())
        return f"""        
Question: what types of backpacks do you have? 
Answer: SELECT {columns} FROM {self.get_table_name()} WHERE product_types = 'backpack';
Question: what 22 litter backpacks do you have?
Answer: SELECT {columns} FROM {self.get_table_name()} WHERE product_size = '22 ltrs';
Question: what 2 wheel trolleys do your products have?
Answer: SELECT {columns} FROM {self.get_table_name()} WHERE product_wheel_type = '2 wheel';
"""

    def get_products(self):
        return self.inference_products

    def get_columns(self):
        return self.inference_columns    
    
    def augmentation_column_products(self):
        return self.ds_augmenter.column_products(self.working_products) 


class WholisticParser():

    def __init__(self, context_parser, inference_parser):
        self.context_parser = context_parser
        self.inference_parser = inference_parser

    def schema_sql(self):
        return f"""
{self.context_parser.schema_sql()}

{self.inference_parser.schema_sql()}
"""
    def get_table_name(self):
        return f"""
{self.context_parser.get_table_name()} AS context JOIN
{self.inference_parser.get_table_name()} AS inference 
ON context.id = inference.id
""".replace("\n", " ")        

    def get_enum_values(self):
        return self.inference_parser.get_enum_values()
        # return { **self.context_parser.get_enum_values(), 
        #          **self.inference_parser.get_enum_values() }

    def get_columns(self):
        columns = ["context.id", "context.id", "context.price"] 
        columns += ["inference."+col for col in self.inference_parser.get_enums()]
        return columns    

    def get_fewshot_examples(self):
        columns = ", ".join(self.get_columns())
        return f"""        
Question: what backpacks do you have? 
Answer: SELECT {columns} FROM {self.get_table_name()} WHERE inference.product_types = 'backpack';
Question: what 22 liter backpacks do you have?
Answer: SELECT {columns} FROM {self.get_table_name()} WHERE inference.product_size = '22 Ltrs';
Question: what 2 wheel trolleys do your products have?
Answer: SELECT {columns} FROM {self.get_table_name()} WHERE inference.product_wheel_type = '2 wheel';
"""

