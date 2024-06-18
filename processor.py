import pandas as pd
import numpy as np
from datetime import datetime
import BCS_SSMS_connector
import logging
import csv
import PGS_connector
import json
import os


current_time = datetime.now()
fcurrent_time = current_time.strftime("%Y-%m-%d-%H-%M-%S")
log_file = os.path.join("D:\\Price_mapping_Automation\\Logging_information", f"Processor_{fcurrent_time}")
logging.basicConfig(filename=log_file, level=logging.DEBUG)


class checker:

    def reader(self, supplier_id):

        # get the query and execute it with each of the the supplier id as the inputs and save it into the dataframe
        # query = f"""select * from bcs_view_master_data_sales_dimensions where last_price_update_supplier = {supplier_id}"""
        
        # query = f"""select * from bcs_view_master_data_sales_by_class where last_price_update_supplier = {supplier_id} order by total_sales desc, no_of_lines desc """

        query = f"""select * from bcs_view_master_data_repl_review where primary_supplier_id = {supplier_id} order by location_id, supplier_name, item_id"""

        # connecting to the db and fetching in query
        df, connection = BCS_SSMS_connector.connect_db(query)

        logging.info("Read data and now returning df with connection")
        
        #  and return the dataframe
        return df, connection


    def column_initiator(self, df, prefix):

        df["discrepancy_type"] = ""
        df["Prefix_of_company"] = prefix

        
        logging.info("Columns initiated - Now returning a modified df")
        
        # returning the df
        return df


    @staticmethod
    def modifier(df):
        
        # handle all the auxilary column modifications and transformations here
        return df


    # for the logical checks
    def do_checks(self, df):

        prefix_log = ""

        # checking all the logic through each of the row
        for index, row in df.iterrows():
            
            discrepancy_flag = 0
            discrepancy_types = []

            prefix_log = df.loc[index, "Prefix_of_company"]

            if df.loc[index, "product_type"] != "R":
                discrepancy_types.append("Product type")
                discrepancy_flag = 1

            elif df.loc[index, "replenishment_location"] == df.loc[index, "location_name"]:
                discrepancy_types.append("Replenishment location")
                discrepancy_flag = 1

            elif df.loc[index, "replenishment_method"] not in ["MinMax", "upto"]:
                discrepancy_types.append("Replenishment method")
                discrepancy_flag = 1

            elif df.loc[index, "replenishment_method"] == "MinMax" and df.loc[index, "stockable"] == "Y":

                if df.loc[index, "inv_min"] == 0:
                    discrepancy_types.append("Inv_min")
                    discrepancy_flag = 1

                if df.loc[index, "inv_max"] == 0:
                    discrepancy_types.append("Inv_max")
                    discrepancy_flag = 1

            elif df.loc[index, "replenishment_method"] == "upto" and df.loc[index, "stockable"] == "Y":
                
                if df.loc[index, "inv_min"] != 0:
                    discrepancy_types.append("Inv_min")
                    discrepancy_flag = 1

                if df.loc[index, "inv_max"] != 0:
                    discrepancy_types.append("Inv_max")
                    discrepancy_flag = 1
                            
            elif df.loc[index, "buyable"] == "N":

                if df.loc[index, "stockable"] == "Y":
                    discrepancy_types.append("stockable")
                    discrepancy_flag = 1

            elif df.loc[index, "stockable"] == "Y" and df.loc[index, "track_bins"] == "Y":
                if df.loc[index, "primary_bin"] == np.nan:
                    discrepancy_types.append("Primary bin")
                    discrepancy_flag = 1

            elif df.loc[index, "stockable"] == "N" and df.loc[index, "track_bins"] == "N":
                if df.loc[index, "qty_on_hand"] != 0:
                    discrepancy_types.append("Qty on hand")
                    discrepancy_flag = 1

                elif df.loc[index, "qty_on_hand"] > 0:
                    if df.loc[index, "track_bins"] == "Y": 
                        
                        if df.loc[index, "primary_bin"] != np.nan:
                            discrepancy_types.append("Primary bin")
                            discrepancy_flag = 1
                    else:
                        discrepancy_types.append("Track bin")
                        discrepancy_flag = 1

            else:
                pass


            # assinging values to the column
            if discrepancy_flag != 1:
                df["discrepancy_type"] = "All right"

            elif discrepancy_flag == 1:
                joined_discrepany = ", ".join(discrepancy_types)

                df["discrepancy_type"] = joined_discrepany

        # check the logics and append the logics, flag on if there are any, if not then assign a "all right" value

        logging.info(f"Checking process for {prefix_log}")


        # check the values from one column to the others
        return df


    def main(self, supplier_ids):
        
        files_saved = []
        process_flag = 0
        checkerob = checker()

        # Step 1: Read the JSON data from the file
        with open(supplier_ids, 'r+') as f:
            suppliers_data = json.load(f)


        # Step 2: Iterate over each supplier and print the related prefix
        for supplier in suppliers_data:
            supplier_id = supplier['supplier_id']
            prefix = supplier['prefix']
            cname = supplier["supplier_name"]

            df, connection = checkerob.reader(supplier_id)

            df = checkerob.column_initiator(df, prefix)
            df = checker.modifier(df)
            df = checkerob.do_checks(df)

            
            # instead of saving it into csv files, do the insert command to db
            # getting the connection for pgs and not the ssms database
            conn = PGS_connector.insert_data_into_db(df)
            
            # specify the file path to save the CSV file
            csv_file_path = f"D:\\MicrosoftSQL_server_connection\\data_temp\\{prefix}_{cname}_data.csv"

            files_saved.append(csv_file_path)

            # save the df to csv files
            df.to_csv(csv_file_path)

            process_flag = 1

        # once the process is finished
        return process_flag, conn
