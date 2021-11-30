import arcpy
import itertools
import json
import os
import requests
import time

# Borrowed Heavily from:
#     https://socalgis.org/2018/03/28/extracting-more-features-from-map-services/
#     https://www.spatialtimes.com/2016/03/extract-map-service-layer-shapefile-using-python/
#     https://www.spatialtimes.com/2016/09/map-service-to-shapefile-with-python-part-2-iteration/

# a REST URL will look like the following when manually entering stuff, spaces are converted to %20 automatically
#     https://www.somesite.com/arcgis/rest/services/somesite/WebMap/MapServer/0/query?where=objectid >= 7845 and objectid <= 8915&returnGeometry=true&outFields=*&f=json

# some sites with cloudflare might push you into a redirect loop, having a user-agent solves that
#     https://developers.whatismybrowser.com/useragents/parse/    |    a dummy user agent also worked: "My App"

# Generally, these settings won't need to be changed
arcpy.env.overwriteOutput = True
json_file_iterator = 0
query_request_standard_pause = 10
record_extraction_hardcode = 30000
response_flag = True

session = requests.Session()
session.headers.update({"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.190 Safari/537.36"})
server_error_message = b'{"error":{"code":500,"message":"Error performing query operation","details":[]}}'
start_time = time.perf_counter()

# Settings - These SHOULD be changed
# service_URL should always end like /number, mostly commonly /0
service_URL = r"https://www.somesite.com/arcgis/rest/services/somesite/WebMap/FeatureServer/0"
# fields is optional and should usually be left alone, the default is * which grabs all the fields
fields = "*"
# out_json_folder and intermediate_gdb must be in different folders
# create a new folder in your project directory for each of these
# this holds the json chunks
out_json_folder = r"C:\Users\your_user\some_folder\some_new_subfolder01"
# this stores the json chunks as separate feature classes
intermediate_gdb_folder = r"C:\Users\your_user\some_folder\some_new_subfolder02"
# this is the path to your target geodatabase, it must already exist and is probably your project file geodatabase
# this is where all of the feature class chunks will be appended into a single final feature class
final_gdb = r"C:\Users\your_user\some_folder\Final_Database_Here.gdb"
# this is what you want your output feature class to be called
final_featureclass = f"The_Feature_Class"

def ServiceGetRecordExtract(ServiceURL):
    """Get record extract limit from Service URL"""
    print(f"Getting Started on REST Vector Extraction for:\n\t{ServiceURL}\n")
    response = session.get(f"{ServiceURL}?f=pjson")
    ServiceRequestMAX = response.json()["maxRecordCount"]
    return(ServiceRequestMAX)

def ServiceGetObjectIDs(ServiceURL):
    """Get sorted list of objectIDs from Service URL"""
    response = session.get(f"{ServiceURL}/query?where=1%3D1&returnIdsOnly=true&f=json")
    ObjectID_FieldName = response.json()["objectIdFieldName"]
    ObjectID_Manifest = sorted(response.json()["objectIds"])
    return(ObjectID_FieldName, ObjectID_Manifest)

def IterableChunk(ServiceRequestMAX, ObjectIDManifest):
    """Divide the ObjectIDs into chunks for processing"""
    args = [iter(ObjectIDManifest)] * ServiceRequestMAX
    final_iterator = 0
    if (len(ObjectIDManifest) % ServiceRequestMAX) > 0:
        final_iterator = 1
    total_iterations = (len(ObjectIDManifest) // ServiceRequestMAX) + final_iterator
    print(f"The server has an extraction limit of {ServiceRequestMAX} and a total of {len(ObjectIDManifest)} records")
    print(f"\tThis will take {total_iterations} iterations")
    print(f"\tThe minimum processing time will be {((total_iterations * query_request_standard_pause) / 60):.2f} minutes\n")
    return([item for item in chunk if item != None] for chunk in itertools.zip_longest(*args))

def QueryExtractionRequest(ObjectID_MIN, ObjectID_MAX, ObjectID_FieldName, Out_JSON_Folder, ServiceURL):
    """Construct URL for Extraction in Chunks"""
    global response_flag
    fields = "*"
    where = f"{ObjectID_FieldName} >= {ObjectID_MIN} and {ObjectID_FieldName} <= {ObjectID_MAX}"
    queryURL = f"{ServiceURL}/query?where={where}&returnGeometry=true&outFields={fields}&f=json"
    response = session.get(f"{queryURL}")
    if server_error_message in response.content:
        print(f"\t\tServer had Response Code: {response.status_code}, but returned query was empty")
        print(queryURL)
        response_flag = False
    time.sleep(query_request_standard_pause)
    sleep_timer = 30
    while not response.ok or response_flag == False:
        sleep_timer = sleep_timer * 2
        print(f"\tResponse not OK, {response.status_code}.\n\t\tSleeping for {sleep_timer} seconds")
        time.sleep(sleep_timer)
        print(f"\tTrying Query URL:\n\t\t{queryURL}")
        response = session.get(f"{queryURL}")
        if server_error_message in response.content:
            print(f"\t\tServer had Response Code: {response.status_code}, but returned query was empty")
            print(queryURL)
            response_flag = False
        else:
            response_flag = True
    with open(f"{Out_JSON_Folder}\{str(json_file_iterator).zfill(6)}.json", "wb") as file:
        file.write(response.content)

def CleanUpJSONsFolder(Out_JSON_Folder):
    """Empty Previous JSON Files from Intermediate Folder Location"""
    print(f"Removing old files from {Out_JSON_Folder}\n")
    for file in os.listdir(Out_JSON_Folder):
        os.remove(f"{Out_JSON_Folder}\{file}")

def ConvertJSONstoFeatureClasses(Out_JSON_Folder, Intermediate_GDB_Folder):
    """Convert JSON files to an Intermediate File Geodatabase Location"""
    if arcpy.Exists(f"{Intermediate_GDB_Folder}\Intermediate_gdb_JSON.gdb"):
        arcpy.management.Delete(f"{Intermediate_GDB_Folder}\Intermediate_gdb_JSON.gdb")
    arcpy.management.CreateFileGDB(Intermediate_GDB_Folder, "Intermediate_gdb_JSON.gdb")
    arcpy.env.workspace = f"{Intermediate_GDB_Folder}\Intermediate_gdb_JSON.gdb"
    list_fc = arcpy.ListFeatureClasses()
    for fc in list_fc:
        arcpy.management.Delete(fc)    
    print(f"\nSaving features...")
    for file in os.listdir(Out_JSON_Folder):
        file_name = file.split(".")
        print(f"\tTransferring {file} to {arcpy.env.workspace}")
        arcpy.JSONToFeatures_conversion(f"{Out_JSON_Folder}\{file}", f"chunk_{file_name[0]}", "POLYGON")

def ReplaceFinalFeatureClassWithIntermediateFeatureClasses(Final_GDB, Final_FeatureClass):
    """Fully Replace the Final Location Feature Class with the Intermediate Feature Classes"""
    if arcpy.Exists(f"{Final_GDB}\{Final_FeatureClass}"):
        arcpy.management.Delete(f"{Final_GDB}\{Final_FeatureClass}")
    list_fc = arcpy.ListFeatureClasses()
    describe_fc = arcpy.Describe(list_fc[0])
    arcpy.management.CreateFeatureclass(Final_GDB, Final_FeatureClass, describe_fc.shapeType, template=list_fc[0], spatial_reference=list_fc[0])
    arcpy.management.Append(list_fc, f"{Final_GDB}\{Final_FeatureClass}", "NO_TEST")


CleanUpJSONsFolder(out_json_folder)
service_request_MAX = ServiceGetRecordExtract(service_URL)
objectID_Field_Name, objectID_Manifest = ServiceGetObjectIDs(service_URL)
# The Server response was poor using the 250k default, so it is hard-coded below; a reasonable extraction limit won't need that
#objectID_Groups = list(IterableChunk(service_request_MAX, objectID_Manifest))
objectID_Groups = list(IterableChunk(record_extraction_hardcode, objectID_Manifest))

for objectID_group in objectID_Groups:
    objectID_MIN = str(objectID_group[0])
    objectID_MAX = str(objectID_group[-1])
    json_file_iterator = json_file_iterator + len(objectID_group)
    print(f"\tWorking on {str(json_file_iterator).zfill(6)} out of {len(objectID_Manifest)} records")
    QueryExtractionRequest(objectID_MIN, objectID_MAX, objectID_Field_Name, out_json_folder, service_URL)

ConvertJSONstoFeatureClasses(out_json_folder, intermediate_gdb_folder)
ReplaceFinalFeatureClassWithIntermediateFeatureClasses(final_gdb, final_featureclass)

print(f"\nDone!\n\tThis routine took {((time.perf_counter() - start_time) / 60):.2f} minutes")
