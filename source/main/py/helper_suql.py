from domain_knowledge import DomainSchema
from helper_parser import SummaryTagger, DataTransformer


class SchemaCreator(DomainSchema):

    def __init__(self, domain_name, domain_datasets, 
                 selected_columns, primary_key, price_column,
                 db_instance, completion_llm, is_verbose):
        super().__init__(data_sets=domain_datasets,
                         completion_llm=completion_llm,
                         is_verbose=is_verbose)
        self.domain_name = domain_name.upper()
        self.domain_datasets = domain_datasets
        self.selected_columns = selected_columns
        self.primary_key = primary_key
        self.price_column = price_column
        self.db_instance = db_instance
        self.completion_llm = completion_llm
        self.is_verbose = is_verbose

    def get_domain_name(self):
        return self.domain_name

    def create_table(self, table_name, column_names):
        self.execute_query(self.create_sql(table_name, column_names))

    def execute_query(self, create_sql):
        try:
          self.db_execute(f"DROP TABLE IF EXISTS {self.domain_name};")
          self.db_execute(create_sql)
          if self.is_verbose:
              print(create_sql)
        except Exception as e:
          print("CREATION_ERROR=" + self.domain_name + " " + str(e) + "\n" + str(create_sql))

    def db_execute(self, query):
        return self.db_instance.db_cursor.execute(query)

    def create_sql(self, table_name, column_names):
        column_txt = ""
        i = 1
        for column in sorted(column_names):
            column_txt += self.column_declaration(column)
            if i!=len(column_names):
                column_txt += ","
            column_txt += "\n"
            i += 1
        return f"""
    CREATE TABLE {table_name} (
    {column_txt}
    ) ;
    """

    def column_declaration(self, column_name):
        if column_name == self.primary_key:
            return f"""{self.primary_key} TEXT PRIMARY KEY"""
        if column_name == self.price_column:
            return f"""{self.price_column} FLOAT NOT NULL"""
        if "is_" in column_name:
            return f"""{column_name} BOOLEAN NOT NULL"""
        return f"""{column_name} TEXT NOT NULL"""

    def non_primary(self, primary_key, column_names):
        return sorted([name for name in column_names if name!=primary_key]) 
            

class DatasetLoader(SchemaCreator):

    def __init__(self, nick_name, domain_name, domain_datasets, 
                 picked_columns, primary_key, price_column,
                 db_instance, completion_llm, is_verbose=False):
        super().__init__(domain_name, domain_datasets, 
                 picked_columns, primary_key, price_column,
                 db_instance, completion_llm, is_verbose)
        self.nick_name = nick_name
        self.table_name = self.get_domain_name() + "_" + self.nick_name
        self.db_instance = db_instance

    def load_items(self):
        columns, products = self.get_columns(), self.get_products()
        products = products[:30]
        insert_sql = self.prepare_load(columns, products)
        # print("INSERT_SQL=>"+str(insert_sql))
        self.execute_load(columns, insert_sql)
        return columns, products

    def prepare_load(self, columns, products):
        # print("PRODUCTS=>" + str(products))
        print("COLUMNS=>" + str(columns))
        rows = DataTransformer.product_strs(products, columns, self.primary_key)
        for chunk in rows.split("\n"):
            print("ROW=>" + str(chunk))
        insert_sql = self.get_sql(self.table_name, rows)
        return insert_sql

    def execute_load(self, columns, insert_sql):
        self.create_table(self.table_name, columns)
        self.db_instance.get_db_cursor().execute(insert_sql)
        self.db_instance.get_db_connection().commit()
    
    def get_sql(self, table_name, table_rows):
        return f"""
INSERT INTO {table_name} VALUES {table_rows}
"""    

    def schema_sql(self):
        return self.create_sql(self.get_table_name(), 
                               self.get_columns())
        
    def get_table_name(self):
        return self.table_name

    # def get_column_products(self):
    #     return self.get_columns(), self.get_products()

    def get_enums(self):
        return sorted(list(self.get_enum_values().keys()))
 
    def get_enum_values(self):
        return self.enum_values


class DatasetReducer():

    def __init__(self, primary_key, picked_columns):
        self.primary_key = primary_key
        self.picked_columns = picked_columns

    def columns(self, columns):
        columns = [col for col in columns if col in self.picked_columns]
        columns = list(set(columns))
        return DataTransformer.fill_cols(sorted(columns))   


class ContextParser(DatasetLoader):

    def __init__(self, domain_name, domain_datasets, 
                 picked_columns, primary_key, price_column, summarize_columns, 
                 db_instance, completion_llm, is_verbose=False):
        super().__init__("CONTEXT", domain_name, domain_datasets, 
                 picked_columns, primary_key, price_column,
                 db_instance, completion_llm, is_verbose)
        self.ds_reducer = DatasetReducer(primary_key, picked_columns)
        self.context_products = self.reduction_products()
        self.context_columns = self.reduction_columns()
        enum_exclude = [col for col in self.get_columns() 
                        if col in summarize_columns or col not in picked_columns or col == primary_key or col == price_column]
        self.enum_values = DataTransformer.set_enum_values(self.get_columns(),
                                                           self.get_products(),
                                                           enum_exclude)

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

    def __init__(self, is_run_inference,
                 column_annotation, summarize_columns, primary_key,
                 completion_llm, is_verbose):
        self.is_run_inference = is_run_inference
        self.column_annotation = column_annotation
        self.primary_key = primary_key
        self.summary_tagger = SummaryTagger(summarize_columns, primary_key,
                                            completion_llm, is_verbose)
        self.sub_domain = "sub_domain"

    def column_products(self, working_products): 
        columns, products = self.summary_column_products(working_products)
        columns, products = self.annotation_column_products(columns, products)
        columns = set(columns)
        columns.add(self.primary_key)
        columns = list(columns)
        return DataTransformer.fill_cols(sorted(columns)), products
        
    def summary_column_products(self, products, n=30): 
        if not self.is_run_inference:
            products = products[:n]
        products = self.summary_tagger.invoke(products)
        columns = self.extract_columns(products)
        return columns, products
    
    def extract_columns(self, products):
        columns = set()
        for product in products:
            columns.update(list(product.keys()))
        return list(columns)
    
    def annotation_column_products(self, columns, products):
        groupings = self.column_annotation.values()
        for grouping in groupings:
            for concept, values in grouping.items():
                concept = "is_" + concept
                columns.append(concept)
                for value in values:
                    for product in products:
                        if value in product['sub_domain']:
                            product[concept] = True
                        else:
                            product[concept] = False
        return columns, products


class InferenceParser(DatasetLoader):

    def __init__(self, is_run_inference,
                 domain_name, domain_datasets, 
                 picked_columns, primary_key, price_column, summarize_columns, column_annotation, 
                 db_instance, completion_llm, is_verbose=False): 
        super().__init__("INFERENCE", domain_name, domain_datasets, 
                 picked_columns, primary_key, price_column, 
                 db_instance, completion_llm, is_verbose)
        self.ds_augmenter = DatasetAugmenter(is_run_inference,
                                             column_annotation, summarize_columns, primary_key,
                                             completion_llm, is_verbose)        
        self.inference_columns, self.inference_products =\
                self.augmentation_column_products()
        enum_exclude = [col for col in self.get_columns() 
                        if col in summarize_columns or col == primary_key or col == price_column]
        self.enum_values = DataTransformer.set_enum_values(self.get_columns(),
                                                           self.get_products(),
                                                           enum_exclude)        
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

    def get_fewshot_examples(self):
        columns = self.get_columns()
        columns = ", ".join(columns)
        return f"""        
Question: what backpacks do you have? 
Answer: SELECT {columns} FROM {self.get_table_name()} WHERE inference.product_type = 'backpack';
Question: what 22 liter backpacks do you have?
Answer: SELECT {columns} FROM {self.get_table_name()} WHERE inference.product_size = '22 Ltrs';
Question: what color trolleys do your products have?
Answer: SELECT DISTINCT product_color FROM {self.get_table_name()} WHERE inference.product_type = 'duffle trolley bag';
"""

    def get_columns(self):
        columns = ["context.id", "context.price", "context.title"] 
        columns += ["inference."+col for col in self.inference_parser.get_enums()]
        return columns    

